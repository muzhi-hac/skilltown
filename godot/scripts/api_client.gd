# SkillTown API client. All learning state comes from FastAPI.
extends Node

signal session_created(payload: Dictionary)
signal town_received(payload: Dictionary)
signal attempt_received(payload: Dictionary)
signal hint_received(payload: Dictionary)
signal passport_received(payload: Dictionary)
signal recommendations_received(payload: Dictionary)
signal api_error(code: String, message: String, retryable: bool)

const SESSION_FILE := "user://session.json"

var session_token := ""
var town: Dictionary = {}

func _ready() -> void:
	_load_session()

func has_session() -> bool:
	return not session_token.is_empty()

func create_session(display_name: String = "Demo learner") -> void:
	_request_json(HTTPClient.METHOD_POST, Config.API_PREFIX + "/session", {"display_name": display_name}, "session", false)

func delete_session() -> void:
	_request_json(HTTPClient.METHOD_DELETE, Config.API_PREFIX + "/session", {}, "delete_session")

func get_town() -> void:
	_request_json(HTTPClient.METHOD_GET, Config.API_PREFIX + "/town", {}, "town")

func start_attempt(scenario_id: String, mode: String = "practice") -> void:
	_request_json(HTTPClient.METHOD_POST, Config.API_PREFIX + "/attempts", {"scenario_id": scenario_id, "mode": mode}, "attempt")

func restore_attempt(attempt_id: String) -> void:
	_request_json(HTTPClient.METHOD_GET, Config.API_PREFIX + "/attempts/" + attempt_id, {}, "attempt")

func respond_choice(attempt_id: String, revision: int, choice_id: String) -> void:
	_request_json(
		HTTPClient.METHOD_POST,
		Config.API_PREFIX + "/attempts/" + attempt_id + "/respond",
		{"client_event_id": _uuid_v4(), "expected_revision": revision, "kind": "choice", "choice_id": choice_id},
		"attempt"
	)

func respond_text(attempt_id: String, revision: int, text: String) -> void:
	_request_json(
		HTTPClient.METHOD_POST,
		Config.API_PREFIX + "/attempts/" + attempt_id + "/respond",
		{"client_event_id": _uuid_v4(), "expected_revision": revision, "kind": "text", "text": text},
		"attempt"
	)

func request_hint(attempt_id: String, revision: int) -> void:
	_request_json(
		HTTPClient.METHOD_POST,
		Config.API_PREFIX + "/attempts/" + attempt_id + "/hint",
		{"client_event_id": _uuid_v4(), "expected_revision": revision},
		"hint"
	)

func rewind_attempt(attempt_id: String, revision: int) -> void:
	_request_json(
		HTTPClient.METHOD_POST,
		Config.API_PREFIX + "/attempts/" + attempt_id + "/rewind",
		{"client_event_id": _uuid_v4(), "expected_revision": revision},
		"attempt"
	)

func get_passport() -> void:
	_request_json(HTTPClient.METHOD_GET, Config.API_PREFIX + "/passport", {}, "passport")

func get_recommendations(max_items: int = 3) -> void:
	_request_json(HTTPClient.METHOD_POST, Config.API_PREFIX + "/recommendations", {"max_items": max_items}, "recommendations")

# Town data is the single source of NPC ids, titles and task lists.
func npc_by_name(npc_name: String) -> Dictionary:
	var npcs = town.get("npcs", [])
	if typeof(npcs) != TYPE_ARRAY:
		return {}
	for item in npcs:
		if item is Dictionary and str(item.get("name", "")) == npc_name:
			return item
	return {}

func npc_name_by_id(npc_id: String) -> String:
	var npcs = town.get("npcs", [])
	if typeof(npcs) == TYPE_ARRAY:
		for item in npcs:
			if item is Dictionary and str(item.get("id", "")) == npc_id:
				return str(item.get("name", npc_id))
	return npc_id

func task_title(scenario_id: String) -> String:
	var npcs = town.get("npcs", [])
	if typeof(npcs) == TYPE_ARRAY:
		for item in npcs:
			if not item is Dictionary:
				continue
			var tasks = item.get("tasks", [])
			if typeof(tasks) != TYPE_ARRAY:
				continue
			for task in tasks:
				if task is Dictionary and str(task.get("scenario_id", "")) == scenario_id:
					return str(task.get("title", scenario_id))
	return scenario_id

func category_label(category_id: String) -> String:
	var categories = town.get("categories", [])
	if typeof(categories) == TYPE_ARRAY:
		for item in categories:
			if item is Dictionary and str(item.get("id", "")) == category_id:
				return "%s %s" % [str(item.get("icon", "")), str(item.get("label", ""))]
	return category_id

func _request_json(method: int, path: String, body: Dictionary, kind: String, with_auth: bool = true) -> void:
	var request := HTTPRequest.new()
	add_child(request)
	request.timeout = 25.0
	request.request_completed.connect(_on_request_completed.bind(request, kind))
	var headers := ["Content-Type: application/json"]
	if with_auth and has_session():
		headers.append("Authorization: Bearer " + session_token)
	var body_text := "" if method in [HTTPClient.METHOD_GET, HTTPClient.METHOD_DELETE] else JSON.stringify(body)
	var url := Config.get_api_base_url() + path
	Config.log_api(path, body)
	var error := request.request(url, headers, method, body_text)
	if error != OK:
		request.queue_free()
		api_error.emit("network_error", "请求未能启动", true)

func _on_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray, request: HTTPRequest, kind: String) -> void:
	request.queue_free()
	if result != HTTPRequest.RESULT_SUCCESS:
		api_error.emit("network_error", "网络连接异常，请重试", true)
		return
	var text := body.get_string_from_utf8()
	var payload = {} if text.is_empty() else JSON.parse_string(text)
	if payload == null or not payload is Dictionary:
		api_error.emit("invalid_response", "服务端返回了无法解析的数据", false)
		return
	if response_code < 200 or response_code >= 300:
		var detail = payload.get("error", {})
		if typeof(detail) != TYPE_DICTIONARY:
			detail = {}
		api_error.emit(str(detail.get("code", "http_" + str(response_code))), str(detail.get("message", "请求失败")), bool(detail.get("retryable", false)))
		return
	match kind:
		"session":
			session_token = str(payload.get("session_token", ""))
			_save_session()
			session_created.emit(payload)
		"delete_session":
			session_token = ""
			town = {}
			if FileAccess.file_exists(SESSION_FILE):
				DirAccess.remove_absolute(SESSION_FILE)
		"town":
			town = payload
			town_received.emit(payload)
		"attempt": attempt_received.emit(payload)
		"hint": hint_received.emit(payload)
		"passport": passport_received.emit(payload)
		"recommendations": recommendations_received.emit(payload)

func _save_session() -> void:
	var file := FileAccess.open(SESSION_FILE, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify({"session_token": session_token}))

func _load_session() -> void:
	if not FileAccess.file_exists(SESSION_FILE):
		return
	var file := FileAccess.open(SESSION_FILE, FileAccess.READ)
	if not file:
		return
	var payload = JSON.parse_string(file.get_as_text())
	if payload is Dictionary:
		session_token = str(payload.get("session_token", ""))

func _uuid_v4() -> String:
	var bytes := Crypto.new().generate_random_bytes(16)
	bytes[6] = (bytes[6] & 0x0f) | 0x40
	bytes[8] = (bytes[8] & 0x3f) | 0x80
	var hex := bytes.hex_encode()
	return "%s-%s-%s-%s-%s" % [hex.substr(0, 8), hex.substr(8, 4), hex.substr(12, 4), hex.substr(16, 4), hex.substr(20, 12)]
