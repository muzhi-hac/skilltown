# 无头集成冒烟：用真实 GDScript 客户端跑一遍真实 FastAPI，不需要浏览器。
#
# 先起后端：.venv/bin/python -m uvicorn server.main:app
# 再运行：/Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
#			 res://tests/headless_flow.tscn
extends Node

const DIALOGUE_UI := preload("res://scenes/dialogue_ui.tscn")

var failures: Array[String] = []
var ui: CanvasLayer = null

func _ready() -> void:
	get_tree().create_timer(40.0).timeout.connect(_on_timeout)
	APIClient.api_error.connect(_on_api_error)
	_run()

func _on_timeout() -> void:
	print("BAD	超时：40 秒内没有跑完流程（后端没起？）")
	get_tree().quit(1)

func _on_api_error(code: String, message: String, _retryable: bool) -> void:
	print("		API 错误 ", code, "：", message)

func _check(label: String, ok: bool, detail: String = "") -> void:
	if ok:
		print("	 ok	 ", label)
	else:
		failures.append(label)
		print("	 BAD  ", label, " — ", detail)

func _choice_button(choice_id: String) -> Button:
	for child in ui.choice_container.get_children():
		if child is Button and str(child.get_meta("choice_id", "")) == choice_id:
			return child
	return null

func _press(choice_id: String) -> Dictionary:
	var button := _choice_button(choice_id)
	if button == null:
		_check("找得到选项 " + choice_id, false, "选项按钮未渲染")
		return {}
	_check("选项 %s 可点击" % choice_id, not button.disabled)
	button.pressed.emit()
	return await APIClient.attempt_received

func _press_action(fragment: String) -> void:
	for child in ui.choice_container.get_children():
		if child is Button and not child.has_meta("choice_id") and child.text.contains(fragment):
			child.pressed.emit()
			return
	_check("找得到动作按钮「%s」" % fragment, false, "按钮未渲染")

func _npc_states(town: Dictionary) -> Dictionary:
	var states := {}
	for npc in town.get("npcs", []):
		if npc is Dictionary:
			states[str(npc.get("id", ""))] = str(npc.get("recommendation_state", ""))
	return states

func _node_id(payload: Dictionary) -> String:
	var node = payload.get("node")
	return str(node.get("id", "")) if typeof(node) == TYPE_DICTIONARY else ""

func _run() -> void:
	print("1) 会话与小镇数据")
	APIClient.session_token = ""
	APIClient.create_session("Headless smoke")
	var session = await APIClient.session_created
	_check("会话已签发", not str(session.get("session_token", "")).is_empty())
	APIClient.get_town()
	var town = await APIClient.town_received
	_check("小镇返回 4 名 NPC", town.get("npcs", []).size() == 4, str(town))

	print("2) 点击 Alex 进入龙虾任务")
	ui = DIALOGUE_UI.instantiate()
	add_child(ui)
	ui.start_dialogue("Alex")
	var start = await APIClient.attempt_received
	_check("进入 dinner_invite", _node_id(start) == "dinner_invite", _node_id(start))
	_check("渲染出 3 个选项", ui.choice_container.get_child_count() == 3)
	_check("本节点允许自由回答", ui.player_input.editable)
	_check("NPC 抬头带分类", ui.npc_title_label.text.contains("伦理与合规"), ui.npc_title_label.text)

	print("3) 先补齐信息，再答错触发后果预演")
	var risk = await _press("ask_context")
	_check("推进到 dinner_risk", _node_id(risk) == "dinner_risk", _node_id(risk))
	var updates = risk.get("learning_updates", [])
	_check("记录 clarify_context 证据",
		updates.size() == 1 and str(updates[0].get("skill_id", "")) == "clarify_context",
		str(updates))
	_check("反馈已显示在对话框", ui.dialogue_text.get_parsed_text().contains("学习反馈"))
	var consequence = await _press("accept_hidden")
	_check("进入 dinner_consequence", _node_id(consequence) == "dinner_consequence", _node_id(consequence))
	_check("effect 为 consequence_preview", str(consequence.get("effect", "")) == "consequence_preview")
	_check("倒带按钮已点亮", not ui.rewind_button.disabled)

	print("4) 倒回决策点并重答")
	ui.rewind_button.pressed.emit()
	var rewound = await APIClient.attempt_received
	_check("回到 dinner_risk（不是剧情开头）", _node_id(rewound) == "dinner_risk", _node_id(rewound))
	var done = await _press("pause_consult")
	_check("任务完成", bool(done.get("is_complete", false)))
	_check("完成后禁用输入", ui.send_button.disabled and ui.player_input.editable == false)
	_check("状态栏提示完成", ui.status_label.text.contains("完成"), ui.status_label.text)

	print("5) 学习护照")
	ui.passport_button.pressed.emit()
	var passport = await APIClient.passport_received
	var states := {}
	for skill in passport.get("skills", []):
		states[str(skill.get("skill_id", ""))] = str(skill.get("state", ""))
	_check("clarify_context 已练习", states.get("clarify_context", "") == "practiced", str(states))
	_check("conflict_awareness 已练习", states.get("conflict_awareness", "") == "practiced", str(states))
	var plan = await APIClient.recommendations_received
	_check("方案给出可去的任务", plan.get("items", []).size() > 0, str(plan))
	_check("方案已显示在对话框", ui.dialogue_text.get_parsed_text().contains("学习方案"))

	print("6) 换 Jo 走自由回答支线，验证跨 NPC 会话延续")
	ui.hide_dialogue()
	ui.start_dialogue("Jo")
	var boundary = await APIClient.attempt_received
	_check("进入 boundary_intro", _node_id(boundary) == "boundary_intro", _node_id(boundary))
	_check("该节点只接受自由回答",
		ui.choice_container.get_child_count() == 0 and ui.player_input.editable)
	ui.player_input.text = "我暂时不接受这个安排，需要先确认谁付款以及是否涉及续约审批，下一步我按内部渠道咨询。"
	ui.send_button.pressed.emit()
	var written = await APIClient.attempt_received
	_check("自由回答被接受并完成", bool(written.get("is_complete", false)), _node_id(written))
	_check("反馈标注了来源模式",
		["scripted", "ai", "fallback"].has(str(written.get("feedback_mode", ""))),
		str(written.get("feedback_mode", "")))

	print("7) 找 Mira 复盘：辅导内容应来自本人证据")
	ui.hide_dialogue()
	ui.start_dialogue("Mira")
	var coaching = await APIClient.attempt_received
	var coaching_node := _node_id(coaching)
	_check("按缺口选辅导节点，而不是说没有记录",
		coaching_node != "review_no_evidence" and coaching_node.begins_with("review_"),
		coaching_node)

	print("8) 找 Sam 验证迁移：必须经过反例，一律拒绝要被纠正")
	ui.hide_dialogue()
	ui.start_dialogue("Sam")
	var gift = await APIClient.attempt_received
	_check("进入 gift_intro", _node_id(gift) == "gift_intro", _node_id(gift))
	var benign = await _press("reject_all_gifts")
	_check("一律拒绝被判为待练习",
		str(benign.get("learning_updates", [{}])[0].get("state", "")) == "needs_practice",
		str(benign.get("learning_updates", [])))
	_check("进入反例节点 gift_benign", _node_id(benign) == "gift_benign", _node_id(benign))
	var refused = await _press("refuse_anyway")
	_check("在无风险情境里仍拒绝 → 留在原节点", _node_id(refused) == "gift_benign", _node_id(refused))
	var migrated = await _press("accept_documented")
	_check("说明条件差异后完成", bool(migrated.get("is_complete", false)), _node_id(migrated))

	print("9) 新访客：欢迎卡 → 三题筛查 → 地图按证据标记")
	ui.hide_dialogue()
	APIClient.session_token = ""
	APIClient.create_session("Screening smoke")
	await APIClient.session_created
	APIClient.get_town()
	var fresh_town = await APIClient.town_received
	var screening = fresh_town.get("screening")
	_check("服务端下发筛查任务（客户端不硬编码 id）", typeof(screening) == TYPE_DICTIONARY, str(screening))
	var fresh_states := _npc_states(fresh_town)
	_check("新访客四名 NPC 都标为 recommended",
		fresh_states.values().count("recommended") == 4, str(fresh_states))
	ui.show_welcome(screening)
	_check("欢迎卡给出两个入口", ui.choice_container.get_child_count() == 2)
	_press_action("先试试")
	var q1 = await APIClient.attempt_received
	_check("第 1 题 screen_clarify", _node_id(q1) == "screen_clarify", _node_id(q1))
	var q2 = await _press("who_pays_pending")
	_check("第 2 题 screen_conflict", _node_id(q2) == "screen_conflict", _node_id(q2))
	var q3 = await _press("small_amount_ok")
	_check("第 3 题 screen_boundary", _node_id(q3) == "screen_boundary", _node_id(q3))
	_check("第 3 题标为个人发展分类",
		str(q3.get("node", {}).get("category", "")) == "personal_development",
		str(q3.get("node", {}).get("category", "")))
	var screened = await _press("reason_and_next")
	_check("三题筛查完成", bool(screened.get("is_complete", false)), _node_id(screened))
	APIClient.get_town()
	var marked_town = await APIClient.town_received
	var marked := _npc_states(marked_town)
	_check("答错的能力把 Alex 标为 review", str(marked.get("alex", "")) == "review", str(marked))
	_check("答对的能力让 Jo 不再高亮", str(marked.get("jo", "")) == "none", str(marked))

	print("10) 学习方案可点击")
	ui.passport_button.pressed.emit()
	await APIClient.passport_received
	await APIClient.recommendations_received
	_press_action("去找")
	var from_plan = await APIClient.attempt_received
	_check("方案按钮直接开出对应任务", not _node_id(from_plan).is_empty(), _node_id(from_plan))

	print("")
	if failures.is_empty():
		print("HEADLESS SMOKE OK — 欢迎卡/筛查/点击/选择/后果/倒带/完成/护照/可点击方案/支线/按缺口辅导/迁移反例/地图标记")
		get_tree().quit(0)
	else:
		print("HEADLESS SMOKE FAILED（%d 项）：" % failures.size())
		for item in failures:
			print("	 - ", item)
		get_tree().quit(1)
