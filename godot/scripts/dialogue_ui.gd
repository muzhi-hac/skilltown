# 对话 UI：只负责展示与输入。任务分支、判定和学习状态全部由 FastAPI 决定。
extends CanvasLayer

# Emitted when a lesson panel closes, carrying the NPC it belonged to ("" if none).
signal closed(npc_name: String)

const FEEDBACK_MODE_LABELS := {
	"scripted": "scripted feedback",
	"ai": "live AI feedback",
	"fallback": "model unavailable, fell back to scripted feedback",
}
const SKILL_LABELS := {
	"clarify_context": "Gather key context",
	"conflict_awareness": "Spot conflicts of interest",
	"communicate_boundary": "Communicate a boundary",
}
const STATE_LABELS := {
	"unseen": "Not yet verified",
	"needs_practice": "Practice suggested",
	"practiced": "Practiced",
	"demonstrated": "Passed independently",
}

@onready var panel: Panel = $Panel
@onready var npc_name_label: Label = $Panel/NPCName
@onready var npc_title_label: Label = $Panel/NPCTitle
@onready var task_label: Label = $Panel/TaskLabel
@onready var progress_label: Label = $Panel/ProgressLabel
@onready var dialogue_text: RichTextLabel = $Panel/DialogueText
@onready var choice_container: VBoxContainer = $Panel/ChoiceContainer
@onready var player_input: LineEdit = $Panel/PlayerInput
@onready var send_button: Button = $Panel/SendButton
@onready var close_button: Button = $Panel/CloseButton
@onready var hint_button: Button = $Panel/HintButton
@onready var rewind_button: Button = $Panel/RewindButton
@onready var passport_button: Button = $Panel/PassportButton
@onready var status_label: Label = $Panel/StatusLabel

var current_npc_name := ""
var current_scenario_id := ""
var current_task_title := ""
var current_mode := ""
var current_minutes := ""
var attempt_id := ""
var revision := 0
var allow_text := false
var is_complete := false
var waiting := false
var _activity_attempt := ""
var _heartbeat: Timer = null

func _ready() -> void:
	add_to_group("dialogue_system")
	visible = false
	_style_dialogue_panel()
	send_button.pressed.connect(_on_send_pressed)
	close_button.pressed.connect(_on_close_pressed)
	hint_button.pressed.connect(_on_hint_pressed)
	rewind_button.pressed.connect(_on_rewind_pressed)
	passport_button.pressed.connect(_on_passport_pressed)
	player_input.text_submitted.connect(_on_text_submitted)
	APIClient.attempt_received.connect(_on_attempt_received)
	APIClient.hint_received.connect(_on_hint_received)
	APIClient.passport_received.connect(_on_passport_received)
	APIClient.recommendations_received.connect(_on_recommendations_received)
	APIClient.api_error.connect(_on_api_error)
	_heartbeat = Timer.new()
	_heartbeat.wait_time = 15.0
	_heartbeat.timeout.connect(_on_heartbeat)
	add_child(_heartbeat)
	_reset_controls()
	Config.log_info("对话 UI 初始化完成")

func _style_dialogue_panel() -> void:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.04, 0.045, 0.055, 0.94)
	style.border_color = Color(0.90, 0.74, 0.32, 0.9)
	style.set_border_width_all(2)
	style.set_corner_radius_all(10)
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	panel.add_theme_stylebox_override("panel", style)
	npc_name_label.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	npc_name_label.add_theme_font_size_override("font_size", 30)
	npc_title_label.add_theme_font_size_override("font_size", 21)
	npc_title_label.add_theme_color_override("font_color", Color(0.78, 0.84, 0.90, 1))
	dialogue_text.add_theme_color_override("default_color", Color(0.92, 0.94, 0.96, 1))
	dialogue_text.add_theme_font_size_override("normal_font_size", 28)
	player_input.add_theme_font_size_override("font_size", 25)
	status_label.add_theme_font_size_override("font_size", 21)
	for button in [send_button, close_button, hint_button, rewind_button, passport_button]:
		button.add_theme_font_size_override("font_size", 22)

# 对话框可见时拦截移动与交互按键，避免输入文字时角色跑动。
func _input(event: InputEvent) -> void:
	if not visible:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_ESCAPE:
			hide_dialogue()
			get_viewport().set_input_as_handled()
			return
		if event.keycode == KEY_ENTER or event.keycode == KEY_KP_ENTER:
			if player_input.has_focus():
				return
			_submit_text()
			get_viewport().set_input_as_handled()
			return
		if event.keycode in [KEY_E, KEY_SPACE, KEY_W, KEY_A, KEY_S, KEY_D]:
			get_viewport().set_input_as_handled()

func start_dialogue(npc_name: String) -> void:
	current_npc_name = npc_name
	current_scenario_id = ""
	current_task_title = ""
	current_mode = ""
	current_minutes = ""
	attempt_id = ""
	revision = 0
	allow_text = false
	is_complete = false
	var npc = get_npc_by_name(npc_name)
	if npc and npc.has_method("set_interacting"):
		npc.set_interacting(true)
	var npc_data := APIClient.npc_by_name(npc_name)
	npc_name_label.text = str(npc_data.get("name", npc_name))
	npc_title_label.text = _npc_subtitle(npc_data, npc_name)
	dialogue_text.clear()
	_clear_choices()
	player_input.text = ""
	_reset_controls()
	show_dialogue()
	if not APIClient.has_session():
		_set_status("Session not ready yet, please try again shortly")
		_append_line("[color=gray]No server session yet. Please click the NPC again in a moment.[/color]")
		return
	if npc_data.is_empty():
		_set_status("Town data not loaded")
		_append_line("[color=gray]Town data (GET /town) hasn't loaded yet, please try again shortly.[/color]")
		return
	var task := _pick_task(npc_data)
	if task.is_empty():
		_set_status("No tasks available")
		_append_line("[color=gray]This NPC has no available tasks right now.[/color]")
		return
	start_scenario(
		str(task.get("scenario_id", "")),
		_pick_mode(task),
		str(task.get("title", "")),
		str(task.get("estimated_minutes", "?")),
	)

# 由 NPC 任务、开场筛查或学习方案共用：只认服务端下发的 scenario_id。
func start_scenario(scenario_id: String, mode: String, title: String, minutes: String) -> void:
	if scenario_id.is_empty():
		_set_status("Task id is missing")
		return
	current_scenario_id = scenario_id
	current_task_title = title if not title.is_empty() else scenario_id
	current_mode = mode
	current_minutes = minutes
	attempt_id = ""
	revision = 0
	is_complete = false
	allow_text = false
	_clear_choices()
	_set_task_summary(
		"Current mission: %s · %s min · %s" % [current_task_title, current_minutes, _mode_label(current_mode)],
		"Next action: loading the first decision point…",
	)
	_append_line("[color=gray]Task: %s · about %s min · mode %s[/color]" % [
		current_task_title,
		minutes,
		mode,
	])
	_set_waiting(true, "Creating task…")
	APIClient.start_attempt(scenario_id, mode)

# 开场欢迎卡：先摸底还是直接逛，由学习者决定。
func show_welcome(screening: Dictionary) -> void:
	current_npc_name = ""
	current_scenario_id = ""
	attempt_id = ""
	is_complete = false
	allow_text = false
	npc_name_label.text = "SkillTown"
	npc_title_label.text = "Compliance learning · Personal development"
	_set_task_summary(
		"Current mission: start with a quick skill check or explore the town",
		"Progress: no evidence yet · Recommended route starts with 3 questions",
	)
	dialogue_text.clear()
	_clear_choices()
	_reset_controls()
	show_dialogue()
	_append_line("[color=gray]All scenarios are fictional training cases and the policy is a fictional training policy; nothing here is legal advice. Your record belongs only to this guest session and can be cleared at any time.[/color]")
	_append_line("Spend about %s min on a 3-question skill check first, or explore the town directly?" % str(screening.get("estimated_minutes", "2")))
	_add_action_button("Quick skill check (3 questions)", _on_welcome_screening.bind(screening))
	_add_action_button("Explore the town", hide_dialogue)
	_update_text_input()

func _on_welcome_screening(screening: Dictionary) -> void:
	var modes = screening.get("available_modes", [])
	var mode := "screening"
	if typeof(modes) == TYPE_ARRAY and not modes.is_empty():
		mode = str(modes[0])
	dialogue_text.clear()
	start_scenario(
		str(screening.get("scenario_id", "")),
		mode,
		str(screening.get("title", "")),
		str(screening.get("estimated_minutes", "?")),
	)

func show_dialogue() -> void:
	visible = true
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_interacting"):
		player.set_interacting(true)

func hide_dialogue() -> void:
	_end_activity()
	var was_with := current_npc_name
	visible = false
	if current_npc_name != "":
		var npc = get_npc_by_name(current_npc_name)
		if npc and npc.has_method("set_interacting"):
			npc.set_interacting(false)
	current_npc_name = ""
	current_scenario_id = ""
	attempt_id = ""
	_clear_choices()
	var player = get_tree().get_first_node_in_group("player")
	if player and player.has_method("set_interacting"):
		player.set_interacting(false)
	# Lets a scene controller know the lesson ended, so the visitor can leave.
	closed.emit(was_with)

func _npc_subtitle(npc_data: Dictionary, npc_name: String) -> String:
	var title := str(npc_data.get("title", Config.NPC_TITLES.get(npc_name, "")))
	var category := str(npc_data.get("category", ""))
	if category.is_empty():
		return title
	return "%s · %s" % [title, APIClient.category_label(category)]

func _pick_task(npc_data: Dictionary) -> Dictionary:
	var tasks = npc_data.get("tasks", [])
	if typeof(tasks) != TYPE_ARRAY or tasks.is_empty():
		return {}
	var task = tasks[0]
	return task if task is Dictionary else {}

func _pick_mode(task: Dictionary) -> String:
	var modes = task.get("available_modes", [])
	if typeof(modes) != TYPE_ARRAY or modes.is_empty():
		return "practice"
	for mode in modes:
		if str(mode) == "practice":
			return "practice"
	return str(modes[0])

func _on_attempt_received(payload: Dictionary) -> void:
	if not visible:
		return
	if current_scenario_id != "" and str(payload.get("scenario_id", "")) != current_scenario_id:
		return
	attempt_id = str(payload.get("attempt_id", ""))
	revision = int(payload.get("revision", 0))
	is_complete = bool(payload.get("is_complete", false))
	_track_activity()
	_set_waiting(false, "")
	_update_task_progress(payload)
	_render_feedback(payload.get("feedback"))
	_render_learning_updates(payload.get("learning_updates", []))
	_render_node(payload.get("node"))
	_apply_effect(str(payload.get("effect", "none")), str(payload.get("feedback_mode", "scripted")))

# 学习时长由服务端按活动事件聚合；客户端只上报 start / heartbeat / end。
func _track_activity() -> void:
	if attempt_id.is_empty():
		return
	if _activity_attempt != attempt_id:
		_activity_attempt = attempt_id
		APIClient.record_activity(attempt_id, "start")
		_heartbeat.start()
	if is_complete:
		_end_activity()

func _on_heartbeat() -> void:
	if visible and not _activity_attempt.is_empty() and not is_complete:
		APIClient.record_activity(_activity_attempt, "heartbeat")

func _end_activity() -> void:
	if _activity_attempt.is_empty():
		return
	APIClient.record_activity(_activity_attempt, "end")
	_activity_attempt = ""
	if _heartbeat != null:
		_heartbeat.stop()

func _render_feedback(feedback) -> void:
	if typeof(feedback) != TYPE_DICTIONARY:
		return
	var mode := str(feedback.get("mode", "scripted"))
	_append_line("[color=orange]%s[/color] (%s): %s" % [
		str(feedback.get("title", "Learning feedback")),
		str(FEEDBACK_MODE_LABELS.get(mode, mode)),
		str(feedback.get("message", "")),
	])
	var clauses = feedback.get("policy_clauses", [])
	if typeof(clauses) == TYPE_ARRAY:
		for clause in clauses:
			if clause is Dictionary:
				_append_line("[color=aqua]Fictional training policy %s · %s[/color]: %s" % [
					str(clause.get("clause_id", "")),
					str(clause.get("title", "")),
					str(clause.get("text", "")),
				])

func _render_learning_updates(updates) -> void:
	if typeof(updates) != TYPE_ARRAY:
		return
	for update in updates:
		if not update is Dictionary:
			continue
		var skill := str(update.get("skill_id", ""))
		var state := str(update.get("state", ""))
		var suffix := " (completed after a hint, not counted as independent verification)" if bool(update.get("assisted", false)) else ""
		_append_line("[color=lightgreen]Learning evidence recorded: %s → %s%s[/color]" % [
			str(SKILL_LABELS.get(skill, skill)),
			str(STATE_LABELS.get(state, state)),
			suffix,
		])

func _render_node(node) -> void:
	_clear_choices()
	if typeof(node) != TYPE_DICTIONARY:
		allow_text = false
		_update_text_input()
		return
	_update_node_next_action(node)
	_append_line("[color=yellow]%s:[/color] %s" % [
		npc_name_label.text,
		str(node.get("text", "")),
	])
	var choices = node.get("choices", [])
	if typeof(choices) == TYPE_ARRAY:
		for choice in choices:
			if choice is Dictionary:
				_add_choice_button(str(choice.get("id", "")), str(choice.get("label", "")))
	allow_text = bool(node.get("allow_text", false))
	_update_text_input()
	var cards = node.get("policy_cards", [])
	if typeof(cards) == TYPE_ARRAY:
		for card in cards:
			if card is Dictionary:
				_append_line("[color=aqua]Fictional training policy %s: %s[/color]" % [
					str(card.get("clause_id", "")),
					str(card.get("text", "")),
				])
	if choice_container.get_child_count() == 0 and not allow_text and not is_complete:
		_append_line("[color=gray]This node has no interactive content right now.[/color]")

func _add_choice_button(choice_id: String, label: String) -> void:
	if choice_id.is_empty():
		return
	var button := Button.new()
	button.text = label
	button.clip_text = true
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.custom_minimum_size = Vector2(0, 50)
	button.add_theme_font_size_override("font_size", 23)
	button.set_meta("choice_id", choice_id)
	button.disabled = waiting or is_complete
	button.pressed.connect(_on_choice_pressed.bind(choice_id, label))
	choice_container.add_child(button)

func _add_action_button(label: String, handler: Callable) -> void:
	var button := Button.new()
	button.text = label
	button.clip_text = true
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.custom_minimum_size = Vector2(0, 50)
	button.add_theme_font_size_override("font_size", 23)
	button.pressed.connect(handler)
	choice_container.add_child(button)

func _clear_choices() -> void:
	for child in choice_container.get_children():
		choice_container.remove_child(child)
		child.queue_free()

func _on_choice_pressed(choice_id: String, label: String) -> void:
	if waiting or attempt_id.is_empty() or is_complete:
		return
	_append_line("[color=cyan]Your choice:[/color] %s" % label)
	_set_waiting(true, "Submitting choice…")
	APIClient.respond_choice(attempt_id, revision, choice_id)

func _on_send_pressed() -> void:
	_submit_text()

func _on_text_submitted(_text: String) -> void:
	_submit_text()

func _submit_text() -> void:
	if waiting or attempt_id.is_empty() or is_complete:
		return
	var message := player_input.text.strip_edges()
	if message.is_empty():
		return
	if not allow_text:
		_set_status("This node only accepts multiple-choice answers")
		return
	player_input.text = ""
	_append_line("[color=cyan]Your answer:[/color] %s" % message)
	_set_waiting(true, "Evaluating your answer…")
	APIClient.respond_text(attempt_id, revision, message)

func _on_hint_pressed() -> void:
	if waiting or attempt_id.is_empty() or is_complete:
		return
	_set_waiting(true, "Getting a hint…")
	APIClient.request_hint(attempt_id, revision)

func _on_hint_received(payload: Dictionary) -> void:
	if not visible:
		return
	revision = int(payload.get("revision", revision))
	_set_waiting(false, "This task is now marked as hint-assisted")
	_append_line("[color=violet]Hint:[/color] %s" % str(payload.get("hint", "")))
	var card = payload.get("policy_card")
	if typeof(card) == TYPE_DICTIONARY:
		_append_line("[color=aqua]Fictional training policy %s · %s[/color]: %s" % [
			str(card.get("clause_id", "")),
			str(card.get("title", "")),
			str(card.get("text", "")),
		])

func _on_rewind_pressed() -> void:
	if waiting or attempt_id.is_empty():
		return
	_set_waiting(true, "Rewinding to the decision point…")
	APIClient.rewind_attempt(attempt_id, revision)

func _on_passport_pressed() -> void:
	if waiting:
		return
	_set_waiting(true, "Loading learning passport…")
	APIClient.get_passport()

func _on_passport_received(payload: Dictionary) -> void:
	if not visible:
		return
	_set_waiting(false, "")
	_append_line("[color=gray]—— Learning Passport ——[/color]")
	var skills = payload.get("skills", [])
	if typeof(skills) == TYPE_ARRAY:
		var completed_count := 0
		var total_count := 0
		for skill in skills:
			if not skill is Dictionary:
				continue
			total_count += 1
			var evidence = skill.get("evidence", [])
			var count := 0
			if typeof(evidence) == TYPE_ARRAY:
				count = evidence.size()
			var state := str(skill.get("state", "unseen"))
			if state in ["practiced", "demonstrated"]:
				completed_count += 1
			_append_line("[color=gray]%s: %s (%d evidence)[/color]" % [
				str(skill.get("label", skill.get("skill_id", ""))),
				str(STATE_LABELS.get(state, state)),
				count,
			])
		_set_task_summary(
			"Current mission: review your learning passport",
			"Progress: %d/%d skills practiced or demonstrated · next plan below" % [completed_count, total_count],
		)
	_append_line("[color=gray]Active time %d s, model wait %d s.[/color]" % [
		int(payload.get("total_active_seconds", 0)),
		int(payload.get("total_model_wait_seconds", 0)),
	])
	# 方案由服务端按缺口选任务，客户端只负责显示去哪找谁。
	_set_waiting(true, "Generating a learning plan…")
	APIClient.get_recommendations(3)

func _on_recommendations_received(payload: Dictionary) -> void:
	if not visible:
		return
	_set_waiting(false, "")
	var items = payload.get("items", [])
	if typeof(items) != TYPE_ARRAY or items.is_empty():
		_append_line("[color=gray]No learning suggestions yet.[/color]")
		return
	_append_line("[color=gray]—— Learning Plan ——[/color]")
	for item in items:
		if not item is Dictionary:
			continue
		var scenario_id := str(item.get("scenario_id", ""))
		var evidence = item.get("evidence_ids", [])
		var count := 0
		if typeof(evidence) == TYPE_ARRAY:
			count = evidence.size()
		var npc_name := APIClient.npc_name_by_id(str(item.get("npc_id", "")))
		var title := APIClient.task_title(scenario_id)
		_append_line("[color=gray]%s: %s (based on %d evidence)[/color]" % [
			title,
			str(item.get("reason", "")),
			count,
		])
		_add_action_button("Go to %s for \"%s\"" % [npc_name, title],
			_on_plan_pressed.bind(scenario_id, title))

func _on_plan_pressed(scenario_id: String, title: String) -> void:
	if waiting:
		return
	var mode := "practice"
	var task := _task_by_scenario(scenario_id)
	if not task.is_empty():
		mode = _pick_mode(task)
	dialogue_text.clear()
	start_scenario(scenario_id, mode, title, str(task.get("estimated_minutes", "?")))

func _task_by_scenario(scenario_id: String) -> Dictionary:
	var npcs = APIClient.town.get("npcs", [])
	if typeof(npcs) != TYPE_ARRAY:
		return {}
	for npc in npcs:
		if not npc is Dictionary:
			continue
		var tasks = npc.get("tasks", [])
		if typeof(tasks) != TYPE_ARRAY:
			continue
		for task in tasks:
			if task is Dictionary and str(task.get("scenario_id", "")) == scenario_id:
				return task
	return {}

func _on_close_pressed() -> void:
	hide_dialogue()

func _on_api_error(code: String, message: String, retryable: bool) -> void:
	if not visible:
		return
	_set_waiting(false, "")
	if code == "revision_conflict" and not attempt_id.is_empty():
		_append_line("[color=gray]Progress is out of sync, fetching the latest state…[/color]")
		_set_waiting(true, "Syncing progress…")
		APIClient.restore_attempt(attempt_id)
		return
	_append_line("[color=red]Error: %s (%s)[/color]" % [message, code])
	_set_status("You can retry" if retryable else "Please adjust and try again")

func _apply_effect(effect: String, feedback_mode: String) -> void:
	rewind_button.disabled = effect != "consequence_preview"
	var status := ""
	match effect:
		"consequence_preview":
			status = "Consequence preview: a teaching simulation, not a real penalty. You can rewind to the decision point and retry."
		"rewind_available":
			status = "Rewound to the decision point, you can answer again."
		"completed":
			status = "Task complete, you can view the learning passport."
		_:
			status = str(FEEDBACK_MODE_LABELS.get(feedback_mode, "")) if feedback_mode != "scripted" else ""
	if is_complete:
		_set_controls_enabled(false)
		rewind_button.disabled = true
		if status.is_empty():
			status = "Task complete, you can view the learning passport."
	_set_status(status)

func _mode_label(mode: String) -> String:
	match mode:
		"screening":
			return "quick check"
		"practice":
			return "practice"
		"challenge":
			return "challenge"
		_:
			return mode

func _category_label(category_id: String) -> String:
	if category_id.is_empty():
		return ""
	return APIClient.category_label(category_id)

func _screening_step(node_id: String) -> String:
	match node_id:
		"screen_clarify":
			return "Question 1/3"
		"screen_conflict":
			return "Question 2/3"
		"screen_boundary":
			return "Question 3/3"
		"screen_complete":
			return "Screening complete"
		_:
			return "Screening"

func _set_task_summary(title: String, progress: String) -> void:
	task_label.text = title
	progress_label.text = progress

func _update_task_progress(payload: Dictionary) -> void:
	var node = payload.get("node")
	var category := ""
	var node_id := ""
	if typeof(node) == TYPE_DICTIONARY:
		category = _category_label(str(node.get("category", "")))
		node_id = str(node.get("id", ""))
	var title := current_task_title if not current_task_title.is_empty() else APIClient.task_title(str(payload.get("scenario_id", current_scenario_id)))
	var mission := "Current mission: %s" % title
	if not category.is_empty():
		mission += " · " + category
	if not current_minutes.is_empty():
		mission += " · %s min" % current_minutes
	if is_complete:
		_set_task_summary(mission, "Progress: complete · open Passport for verified skills and next task")
	elif current_mode == "screening":
		_set_task_summary(mission, "Progress: %s · answer to update your personal memory" % _screening_step(node_id))
	else:
		_set_task_summary(mission, "Progress: step %d · choose or type a response to create evidence" % (revision + 1))

func _update_node_next_action(node: Dictionary) -> void:
	if is_complete:
		progress_label.text = "Progress: complete · open Passport for verified skills and next task"
		return
	var choices = node.get("choices", [])
	var choice_count: int = choices.size() if typeof(choices) == TYPE_ARRAY else 0
	var can_type := bool(node.get("allow_text", false))
	var prefix := progress_label.text
	var action := ""
	if choice_count > 0 and can_type:
		action = "Next action: pick one of %d choices, or write your own answer" % choice_count
	elif choice_count > 0:
		action = "Next action: pick the best of %d choices" % choice_count
	elif can_type:
		action = "Next action: write your answer in the input box"
	else:
		action = "Next action: read the feedback, then open Passport"
	if current_mode == "screening":
		var node_id := str(node.get("id", ""))
		progress_label.text = "%s · %s" % [_screening_step(node_id), action]
	else:
		progress_label.text = "%s · %s" % [prefix, action]

func _update_text_input() -> void:
	player_input.editable = allow_text and not is_complete
	send_button.disabled = not player_input.editable
	player_input.placeholder_text = "Write your answer…" if allow_text else "This node only accepts multiple-choice answers"
	if player_input.editable:
		player_input.grab_focus()

func _set_waiting(value: bool, status: String) -> void:
	waiting = value
	_set_controls_enabled(not value)
	if not status.is_empty() or not value:
		_set_status(status)

func _set_controls_enabled(enabled: bool) -> void:
	for child in choice_container.get_children():
		if not child is Button:
			continue
		if child.has_meta("choice_id"):
			child.disabled = not enabled or is_complete
		else:
			# 动作按钮（去做某个任务、欢迎卡选择）在任务完成后仍然可用。
			child.disabled = not enabled
	send_button.disabled = not enabled or not allow_text or is_complete
	hint_button.disabled = not enabled or attempt_id.is_empty() or is_complete
	passport_button.disabled = not enabled

func _reset_controls() -> void:
	waiting = false
	rewind_button.disabled = true
	hint_button.disabled = true
	send_button.disabled = true
	passport_button.disabled = false
	player_input.editable = false
	_set_status("")

func _set_status(text: String) -> void:
	status_label.text = text

func _append_line(bbcode: String) -> void:
	dialogue_text.append_text(bbcode + "\n")
	dialogue_text.scroll_to_line(maxi(dialogue_text.get_line_count() - 1, 0))

# 通过名字找到场景中的 NPC 节点。
func get_npc_by_name(npc_name: String) -> Node:
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.npc_name == npc_name:
			return npc
	return null
