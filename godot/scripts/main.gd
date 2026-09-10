# SkillTown main scene bootstrap. Session and town data come from FastAPI.
extends Node2D

var _reauth_attempted := false
var _welcome_resolved := false
var _hud_goal_label: Label = null
var _hud_progress_label: Label = null
var _hud_next_label: Label = null

func _ready() -> void:
	Config.log_info("SkillTown scene ready")
	_build_mission_hud()
	APIClient.session_created.connect(_on_session_created)
	APIClient.town_received.connect(_on_town_received)
	APIClient.passport_received.connect(_on_passport_received)
	APIClient.recommendations_received.connect(_on_recommendations_received)
	APIClient.api_error.connect(_on_api_error)
	_set_hud(
		"Goal: train answer gaps.",
		"Progress: starting guest session…",
		"Next: load town, then click NPC / press E.",
	)
	if APIClient.has_session():
		APIClient.get_town()
	else:
		APIClient.create_session("Demo learner")

func _on_session_created(_payload: Dictionary) -> void:
	_reauth_attempted = false
	APIClient.get_town()

func _on_town_received(payload: Dictionary) -> void:
	var npcs = payload.get("npcs", [])
	if typeof(npcs) != TYPE_ARRAY:
		return
	Config.log_info("Town loaded: %d NPCs" % npcs.size())
	for entry in npcs:
		if not entry is Dictionary:
			continue
		var node := _find_npc(str(entry.get("name", "")))
		if node and node.has_method("apply_town_data"):
			node.apply_town_data(entry)
	_update_hud_from_town(payload)
	if not _welcome_resolved:
		APIClient.get_passport()

# 只有还没留下任何证据的新访客才看到欢迎卡；老访客直接回到小镇。
func _on_passport_received(payload: Dictionary) -> void:
	if _welcome_resolved:
		_update_hud_from_passport(payload, false)
		return
	var skills = payload.get("skills", [])
	var has_evidence := false
	if typeof(skills) == TYPE_ARRAY:
		for skill in skills:
			if not skill is Dictionary:
				continue
			var evidence = skill.get("evidence", [])
			if typeof(evidence) == TYPE_ARRAY and evidence.size() > 0:
				has_evidence = true
	_update_hud_from_passport(payload, has_evidence)
	_welcome_resolved = true
	if has_evidence:
		if not _dialogue_is_visible():
			APIClient.get_recommendations(1)
		return
	var screening = APIClient.town.get("screening")
	if typeof(screening) != TYPE_DICTIONARY:
		return
	var ui := get_tree().get_first_node_in_group("dialogue_system")
	if ui and ui.has_method("show_welcome"):
		ui.show_welcome(screening)

func _find_npc(npc_name: String) -> Node:
	if npc_name.is_empty():
		return null
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.npc_name == npc_name:
			return npc
	return null

func _on_api_error(code: String, message: String, _retryable: bool) -> void:
	Config.log_error("API %s: %s" % [code, message])
	# 过期或无效的本地 token：清掉并重新建一个游客会话。
	if code == "unauthorized" and not _reauth_attempted:
		_reauth_attempted = true
		APIClient.session_token = ""
		APIClient.create_session("Demo learner")

func _build_mission_hud() -> void:
	var layer := CanvasLayer.new()
	layer.name = "MissionHUD"
	layer.layer = 5
	add_child(layer)

	var panel := Panel.new()
	panel.name = "Panel"
	panel.offset_left = 16
	panel.offset_top = 16
	panel.offset_right = 650
	panel.offset_bottom = 190
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.035, 0.04, 0.05, 0.88)
	style.border_color = Color(0.90, 0.74, 0.32, 0.85)
	style.set_border_width_all(2)
	style.set_corner_radius_all(10)
	panel.add_theme_stylebox_override("panel", style)
	layer.add_child(panel)

	var title := Label.new()
	title.name = "Title"
	title.offset_left = 14
	title.offset_top = 10
	title.offset_right = 610
	title.offset_bottom = 42
	title.text = "SkillTown Mission"
	title.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	title.add_theme_font_size_override("font_size", 26)
	panel.add_child(title)

	_hud_goal_label = _make_hud_label("Goal", 52, Color(0.94, 0.86, 0.48, 1))
	panel.add_child(_hud_goal_label)
	_hud_progress_label = _make_hud_label("Progress", 90, Color(0.62, 0.82, 1, 1))
	panel.add_child(_hud_progress_label)
	_hud_next_label = _make_hud_label("Next", 128, Color(0.78, 0.88, 0.72, 1))
	panel.add_child(_hud_next_label)

func _make_hud_label(label_name: String, top: float, color: Color) -> Label:
	var label := Label.new()
	label.name = label_name
	label.offset_left = 14
	label.offset_top = top
	label.offset_right = 610
	label.offset_bottom = top + 32
	label.add_theme_color_override("font_color", color)
	label.add_theme_font_size_override("font_size", 20)
	label.clip_text = true
	return label

func _set_hud(goal: String, progress: String, next: String) -> void:
	if _hud_goal_label == null:
		return
	_hud_goal_label.text = goal
	_hud_progress_label.text = progress
	_hud_next_label.text = next

func _update_hud_from_town(payload: Dictionary) -> void:
	var npcs = payload.get("npcs", [])
	var recommended := 0
	var review := 0
	var next_npc := ""
	var next_task := ""
	if typeof(npcs) == TYPE_ARRAY:
		for entry in npcs:
			if not entry is Dictionary:
				continue
			var state := str(entry.get("recommendation_state", "none"))
			if state == "recommended":
				recommended += 1
			elif state == "review":
				review += 1
			if next_npc.is_empty() and state in ["review", "recommended"]:
				next_npc = str(entry.get("name", ""))
				var tasks = entry.get("tasks", [])
				if typeof(tasks) == TYPE_ARRAY and not tasks.is_empty() and tasks[0] is Dictionary:
					next_task = str(tasks[0].get("title", ""))
	var goal := "Goal: finish compliance + personal development."
	var progress := "Map: %d review NPCs · %d recommended NPCs" % [review, recommended]
	var next := "Next: click highlighted NPC / press E."
	if not next_npc.is_empty():
		next = "Next: visit %s for %s." % [next_npc, next_task if not next_task.is_empty() else "the next task"]
	_set_hud(goal, progress, next)

func _update_hud_from_passport(payload: Dictionary, has_evidence: bool) -> void:
	var skills = payload.get("skills", [])
	var total := 0
	var done := 0
	var gaps: Array[String] = []
	if typeof(skills) == TYPE_ARRAY:
		for skill in skills:
			if not skill is Dictionary:
				continue
			total += 1
			var state := str(skill.get("state", "unseen"))
			var label := str(skill.get("label", skill.get("skill_id", "")))
			if state in ["practiced", "demonstrated"]:
				done += 1
			elif gaps.size() < 2:
				gaps.append(label)
	var progress := "Progress: %d/%d skills practiced or demonstrated" % [done, total]
	var next := "Next: take the 3-question quick check."
	if has_evidence and not gaps.is_empty():
		next = "Next gap: %s." % ", ".join(gaps)
	elif has_evidence:
		next = "Next: open Passport for the personalized route."
	_set_hud(
		"Goal: train answer gaps only.",
		progress,
		next,
	)

func _on_recommendations_received(payload: Dictionary) -> void:
	var items = payload.get("items", [])
	if typeof(items) != TYPE_ARRAY or items.is_empty() or not items[0] is Dictionary:
		return
	var first: Dictionary = items[0]
	var npc_name := APIClient.npc_name_by_id(str(first.get("npc_id", "")))
	var title := APIClient.task_title(str(first.get("scenario_id", "")))
	_hud_next_label.text = "Next: go to %s for %s." % [npc_name, title]

func _dialogue_is_visible() -> bool:
	var ui := get_tree().get_first_node_in_group("dialogue_system")
	return ui != null and bool(ui.visible)
