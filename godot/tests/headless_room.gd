# Headless check of room mode against a real FastAPI server, no browser needed.
#
# Start the backend, then:
#   /Applications/Godot.app/Contents/MacOS/Godot --headless --path godot \
#       res://tests/headless_room.tscn
extends Node

const ROOM := preload("res://scenes/room.tscn")

var failures: Array[String] = []
var room: Node2D = null

func _ready() -> void:
	get_tree().create_timer(60.0).timeout.connect(_on_timeout)
	APIClient.api_error.connect(_on_api_error)
	_run()

func _on_timeout() -> void:
	print("BAD  timed out after 60s (is the backend running?)")
	get_tree().quit(1)

func _on_api_error(code: String, message: String, _retryable: bool) -> void:
	print("     API error ", code, ": ", message)

func _check(label: String, ok: bool, detail: String = "") -> void:
	if ok:
		print("  ok  ", label)
	else:
		failures.append(label)
		print("  BAD  ", label, " — ", detail)

func _dialogue() -> CanvasLayer:
	return get_tree().get_first_node_in_group("dialogue_system")

func _await_status(fragment: String, timeout := 15.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(timeout * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if room.status_label.text.contains(fragment):
			return true
		await get_tree().process_frame
	return false

func _run() -> void:
	print("1) A fresh guest enters the room")
	APIClient.session_token = ""
	APIClient.create_session("Room smoke")
	await APIClient.session_created
	room = ROOM.instantiate()
	add_child(room)
	var knocked := await _await_status("knocking")
	_check("someone knocks without the learner walking anywhere", knocked, room.status_label.text)
	_check("the door can be opened", not room.door_button.disabled)
	_check("the first visit is the skill check",
		room.status_label.text.contains("skill check"), room.status_label.text)
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.visible:
			_check("visitors stay outside until the door opens", false, str(npc.npc_name))

	print("2) Open the door: the visitor walks in and teaches")
	room.door_button.pressed.emit()
	var in_lesson := await _await_status("In a lesson")
	_check("the lesson starts after the visitor arrives", in_lesson, room.status_label.text)
	var present := []
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.visible:
			present.append(str(npc.npc_name))
	_check("exactly one visitor is in the room", present.size() == 1, str(present))
	_check("the panel is open", _dialogue().visible)

	print("3) The skill check runs through the existing panel")
	_dialogue().choice_container.get_child(0).pressed.emit()
	var q1 = await APIClient.attempt_received
	_check("question 1 arrives", str(q1.get("node", {}).get("id", "")) == "screen_clarify",
		str(q1.get("node", {}).get("id", "")))
	_press("who_pays_pending")
	var q2 = await APIClient.attempt_received
	_press("small_amount_ok")
	var q3 = await APIClient.attempt_received
	_check("question 3 is the boundary one", str(q3.get("node", {}).get("id", "")) == "screen_boundary",
		str(q3.get("node", {}).get("id", "")))
	_press("reason_and_next")
	var done = await APIClient.attempt_received
	_check("the skill check completes", bool(done.get("is_complete", false)))

	print("4) Closing the lesson sends the visitor out and queues the next knock")
	_dialogue().hide_dialogue()
	var next_knock := await _await_status("knocking", 20.0)
	_check("the next teacher knocks on their own", next_knock, room.status_label.text)
	var still_here := []
	for npc in get_tree().get_nodes_in_group("npcs"):
		if npc.visible:
			still_here.append(str(npc.npc_name))
	_check("the previous visitor has left", still_here.is_empty(), str(still_here))
	_check("the queue is shown to the learner",
		room.queue_label.text.contains("Waiting") or room.queue_label.text.contains("No one"),
		room.queue_label.text)

	print("5) The order follows the server's own marking")
	var marked := {}
	for npc in APIClient.town.get("npcs", []):
		if npc is Dictionary:
			marked[str(npc.get("name", ""))] = str(npc.get("recommendation_state", ""))
	var knocking: String = str(room.current)
	_check("whoever knocks is flagged review or recommended",
		marked.get(knocking, "") in ["review", "recommended"],
		"%s -> %s" % [knocking, marked.get(knocking, "?")])

	print("")
	if failures.is_empty():
		print("ROOM SMOKE OK — knock, let in, teach through the real API, leave, next knock")
		get_tree().quit(0)
	else:
		print("ROOM SMOKE FAILED (%d):" % failures.size())
		for item in failures:
			print("  - ", item)
		get_tree().quit(1)

func _press(choice_id: String) -> void:
	for child in _dialogue().choice_container.get_children():
		if child is Button and str(child.get_meta("choice_id", "")) == choice_id:
			child.pressed.emit()
			return
	_check("choice %s is on screen" % choice_id, false, "button not rendered")
