# SkillTown main scene bootstrap. Session and town data come from FastAPI.
extends Node2D

var _reauth_attempted := false

func _ready() -> void:
	Config.log_info("SkillTown scene ready")
	APIClient.session_created.connect(_on_session_created)
	APIClient.town_received.connect(_on_town_received)
	APIClient.api_error.connect(_on_api_error)
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
