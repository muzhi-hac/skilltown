# SkillTown main scene bootstrap. Session and town data come from FastAPI.
extends Node2D

var _reauth_attempted := false
var _welcome_resolved := false

func _ready() -> void:
	Config.log_info("SkillTown scene ready")
	APIClient.session_created.connect(_on_session_created)
	APIClient.town_received.connect(_on_town_received)
	APIClient.passport_received.connect(_on_passport_received)
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
	if not _welcome_resolved:
		APIClient.get_passport()

# 只有还没留下任何证据的新访客才看到欢迎卡；老访客直接回到小镇。
func _on_passport_received(payload: Dictionary) -> void:
	if _welcome_resolved:
		return
	_welcome_resolved = true
	var skills = payload.get("skills", [])
	if typeof(skills) == TYPE_ARRAY:
		for skill in skills:
			if not skill is Dictionary:
				continue
			var evidence = skill.get("evidence", [])
			if typeof(evidence) == TYPE_ARRAY and evidence.size() > 0:
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
