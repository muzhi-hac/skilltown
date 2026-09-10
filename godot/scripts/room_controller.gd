# Room mode: the learner stays in one room and teachers come to them.
#
# One visitor at a time knocks, is let in, teaches through the existing dialogue
# panel, then leaves. The order is not hard-coded here: it comes from
# GET /api/v1/town, where the server marks each NPC "review" (a skill this
# learner answered wrong), "recommended" (no evidence yet) or "none". So the
# queue is a view of the learner's own record, not a script.
extends Node2D

# The room is one small screen: visitors wait above the door, step through it,
# and stop beside the table where the learner is.
const OFFSCREEN_POSITION := Vector2(645.0, 120.0)
const DOOR_POSITION := Vector2(645.0, 285.0)
const LESSON_POSITION := Vector2(700.0, 420.0)
const WALK_IN_SECONDS := 1.0
const WALK_OUT_SECONDS := 0.8
const BEAT_SECONDS := 0.9

@onready var status_label: Label = $RoomHUD/StatusLabel
@onready var queue_label: Label = $RoomHUD/QueueLabel
@onready var door_button: Button = $RoomHUD/DoorButton
@onready var passport_button: Button = $RoomHUD/PassportButton
@onready var clear_button: Button = $RoomHUD/ClearButton
@onready var knock_hint: Label = $RoomHUD/KnockHint
@onready var knock_sound: AudioStreamPlayer = $Knock

var order: Array = []
var current := ""
var door_action := "open"
var busy := false

var _dialogue: CanvasLayer = null
var _screening: Dictionary = {}
var _screening_pending := false
var _visitor_checked := false
var _reauth_attempted := false
var _clear_armed := false
var _door_pulse: Tween = null

func _ready() -> void:
	Config.log_info("Room scene ready")
	_dialogue = get_tree().get_first_node_in_group("dialogue_system")
	if _dialogue != null and _dialogue.has_signal("closed"):
		_dialogue.closed.connect(_on_lesson_closed)
	door_button.pressed.connect(_on_door_pressed)
	passport_button.pressed.connect(_on_passport_pressed)
	clear_button.pressed.connect(_on_clear_pressed)
	APIClient.session_created.connect(_on_session_created)
	APIClient.town_received.connect(_on_town_received)
	APIClient.passport_received.connect(_on_passport_received)
	APIClient.api_error.connect(_on_api_error)
	APIClient.session_deleted.connect(_on_session_deleted)
	for npc in get_tree().get_nodes_in_group("npcs"):
		npc.wander_enabled = false
		npc.global_position = OFFSCREEN_POSITION
		if npc.has_method("set_present"):
			npc.set_present(false)
	_style_door_button()
	knock_hint.visible = false
	_set_status("Getting the room ready…", "")
	door_button.disabled = true
	if APIClient.has_session():
		APIClient.get_town()
	else:
		APIClient.create_session("Demo learner")

# The door is the only thing to do while someone is knocking, so it should look
# like it: a wide button under the door, a prompt above it, and the E key.
func _style_door_button() -> void:
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color(0.95, 0.78, 0.32, 1.0)
	normal.set_corner_radius_all(10)
	normal.set_border_width_all(3)
	normal.border_color = Color(1, 0.92, 0.6, 1)
	var hover := normal.duplicate()
	hover.bg_color = Color(1.0, 0.86, 0.45, 1.0)
	var disabled := normal.duplicate()
	disabled.bg_color = Color(0.32, 0.30, 0.26, 1.0)
	disabled.border_color = Color(0.42, 0.40, 0.36, 1)
	door_button.add_theme_stylebox_override("normal", normal)
	door_button.add_theme_stylebox_override("hover", hover)
	door_button.add_theme_stylebox_override("pressed", hover)
	door_button.add_theme_stylebox_override("disabled", disabled)

func _unhandled_input(event: InputEvent) -> void:
	if _dialogue != null and _dialogue.visible:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_SPACE] and not door_button.disabled:
			_on_door_pressed()
			get_viewport().set_input_as_handled()

func _set_knocking(knocking: bool) -> void:
	knock_hint.visible = knocking
	if knocking:
		var pulse := create_tween().set_loops()
		pulse.tween_property(door_button, "modulate:a", 0.55, 0.45)
		pulse.tween_property(door_button, "modulate:a", 1.0, 0.45)
		_door_pulse = pulse
	else:
		if _door_pulse != null and _door_pulse.is_valid():
			_door_pulse.kill()
		_door_pulse = null
		door_button.modulate.a = 1.0

func _on_session_created(_payload: Dictionary) -> void:
	_reauth_attempted = false
	APIClient.get_town()

func _on_town_received(payload: Dictionary) -> void:
	var npcs = payload.get("npcs", [])
	if typeof(npcs) != TYPE_ARRAY:
		return
	for entry in npcs:
		if not entry is Dictionary:
			continue
		var node := _find_npc(str(entry.get("name", "")))
		if node and node.has_method("apply_town_data"):
			node.apply_town_data(entry)
	var screening = payload.get("screening")
	_screening = screening if typeof(screening) == TYPE_DICTIONARY else {}
	order = _build_order(npcs)
	if not _visitor_checked:
		# The passport tells us whether this is a first visit, which decides
		# whether the opening skill check is offered at all.
		APIClient.get_passport()
	else:
		_knock_next()

# review first (a skill was answered wrong), then never-seen, then the rest.
func _build_order(npcs: Array) -> Array:
	var review: Array = []
	var recommended: Array = []
	var rest: Array = []
	for entry in npcs:
		if not entry is Dictionary:
			continue
		var name := str(entry.get("name", ""))
		if name.is_empty():
			continue
		match str(entry.get("recommendation_state", "none")):
			"review":
				review.append(name)
			"recommended":
				recommended.append(name)
			_:
				rest.append(name)
	return review + recommended + rest

func _on_passport_received(payload: Dictionary) -> void:
	if _visitor_checked:
		return
	_visitor_checked = true
	var has_evidence := false
	var skills = payload.get("skills", [])
	if typeof(skills) == TYPE_ARRAY:
		for skill in skills:
			if not skill is Dictionary:
				continue
			var evidence = skill.get("evidence", [])
			if typeof(evidence) == TYPE_ARRAY and evidence.size() > 0:
				has_evidence = true
	_screening_pending = not has_evidence and not _screening.is_empty()
	_knock_next()

func _knock_next() -> void:
	if busy:
		return
	if _screening_pending:
		current = _first_present_coach()
		door_action = "open"
		door_button.disabled = false
		door_button.text = "Open the door  (E)"
		_set_status("%s is knocking — here for a quick skill check." % current, _waiting_line())
		_set_knocking(true)
		_play_knock()
		return
	if order.is_empty():
		current = ""
		door_action = "invite"
		door_button.disabled = false
		_set_knocking(false)
		door_button.text = "Invite the next teacher  (E)"
		_set_status("No one is waiting right now.", "Review your passport, or invite someone in.")
		return
	current = str(order.pop_front())
	door_action = "open"
	door_button.disabled = false
	door_button.text = "Open the door  (E)"
	_set_status("%s is knocking at the door." % current, _waiting_line())
	_set_knocking(true)
	_play_knock()

func _on_door_pressed() -> void:
	if door_action == "invite":
		door_button.disabled = true
		_set_status("Asking who is available…", "")
		APIClient.get_town()
		return
	if current.is_empty() or busy:
		return
	busy = true
	door_button.disabled = true
	_set_knocking(false)
	var npc := _find_npc(current)
	if npc == null:
		busy = false
		_knock_next()
		return
	_set_status("%s is coming in…" % current, _waiting_line())
	npc.global_position = OFFSCREEN_POSITION
	if npc.has_method("set_present"):
		npc.set_present(true)
	var walk := create_tween()
	walk.tween_property(npc, "global_position", DOOR_POSITION, WALK_IN_SECONDS * 0.45)
	walk.tween_property(npc, "global_position", LESSON_POSITION, WALK_IN_SECONDS * 0.55)
	walk.finished.connect(_begin_lesson)

func _begin_lesson() -> void:
	if _dialogue == null:
		busy = false
		return
	_set_status("In a lesson with %s." % current, _waiting_line())
	if _screening_pending:
		_screening_pending = false
		_dialogue.show_welcome(_screening)
	else:
		_dialogue.start_dialogue(current)

func _on_lesson_closed(_npc_name: String) -> void:
	if not busy:
		return
	var npc := _find_npc(current)
	if npc == null:
		busy = false
		_after_visit()
		return
	_set_status("%s is heading out." % current, _waiting_line())
	var walk := create_tween()
	walk.tween_property(npc, "global_position", DOOR_POSITION, WALK_OUT_SECONDS * 0.6)
	walk.tween_property(npc, "global_position", OFFSCREEN_POSITION, WALK_OUT_SECONDS * 0.4)
	walk.finished.connect(_on_visitor_left.bind(npc))

func _on_visitor_left(npc: Node) -> void:
	if npc != null and npc.has_method("set_present"):
		npc.set_present(false)
	busy = false
	_after_visit()

func _after_visit() -> void:
	# Refresh the town so the next knock reflects evidence just recorded.
	_set_status("Checking who should come next…", _waiting_line())
	await get_tree().create_timer(BEAT_SECONDS).timeout
	APIClient.get_town()

# A guest must be able to delete their own record. Two clicks, because one
# misclick would throw away every answer they gave.
func _on_clear_pressed() -> void:
	if not _clear_armed:
		_clear_armed = true
		clear_button.text = "Confirm"
		_set_status(
			"Clearing deletes every answer in this guest session.",
			"Click Confirm within 5 seconds, or ignore this to keep your record."
		)
		await get_tree().create_timer(5.0).timeout
		if _clear_armed:
			_clear_armed = false
			clear_button.text = "Clear record"
			_knock_next()
		return
	_clear_armed = false
	clear_button.text = "Clear record"
	_reset_room()
	_set_status("Clearing your record…", "")
	APIClient.delete_session()

func _on_session_deleted() -> void:
	_visitor_checked = false
	_screening_pending = false
	_reauth_attempted = false
	_set_status("Record cleared. Starting a fresh guest session…", "")
	APIClient.create_session("Demo learner")

func _reset_room() -> void:
	busy = false
	order = []
	current = ""
	door_button.disabled = true
	if _dialogue != null and _dialogue.visible:
		_dialogue.hide_dialogue()
	for npc in get_tree().get_nodes_in_group("npcs"):
		npc.global_position = OFFSCREEN_POSITION
		if npc.has_method("set_present"):
			npc.set_present(false)

func _on_passport_pressed() -> void:
	if _dialogue == null:
		return
	# Reuses the panel's own passport view, which also loads the learning plan.
	_dialogue.show_dialogue()
	_dialogue.passport_button.pressed.emit()

func _on_api_error(code: String, message: String, _retryable: bool) -> void:
	Config.log_error("API %s: %s" % [code, message])
	if code == "unauthorized" and not _reauth_attempted:
		_reauth_attempted = true
		APIClient.session_token = ""
		APIClient.create_session("Demo learner")
		return
	if not busy:
		_set_status("Could not reach the learning service.", message)
		door_button.disabled = false

func _first_present_coach() -> String:
	# The skill check is hosted by the ethics coach when present, else whoever is first.
	for name in ["Mira", "Jo", "Alex", "Sam"]:
		if _find_npc(name) != null:
			return name
	return ""

func _waiting_line() -> String:
	if order.is_empty():
		return "No one else waiting."
	var names: Array = []
	for name in order:
		names.append(str(name))
	return "Waiting: %s" % ", ".join(names)

func _set_status(headline: String, detail: String) -> void:
	status_label.text = headline
	queue_label.text = detail

func _play_knock() -> void:
	if knock_sound != null and knock_sound.stream != null:
		knock_sound.play()

func _find_npc(npc_name: String) -> Node:
	if npc_name.is_empty():
		return null
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.npc_name == npc_name:
			return npc
	return null
