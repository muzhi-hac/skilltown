# SkillTown global configuration.
extends Node

const LOCAL_API_BASE_URL := "http://127.0.0.1:8000"
const API_PREFIX := "/api/v1"

const NPC_NAMES := ["Alex", "Sam", "Mira", "Jo"]
const NPC_TITLES := {
	"Alex": "Business Partner · Ethics & Compliance",
	"Sam": "Supplier · Ethics & Compliance",
	"Mira": "Ethics Coach · Ethics & Compliance",
	"Jo": "Communication Coach · Personal Development"
}
const NPC_SCENARIOS := {
	"Alex": "dinner-invitation",
	"Sam": "supplier-gift",
	"Mira": "ethics-review",
	"Jo": "boundary-response"
}

const PLAYER_SPEED := 200.0
const INTERACTION_DISTANCE := 80.0
const DEBUG_MODE := true
const SHOW_INTERACTION_RANGE := true

func get_api_base_url() -> String:
	var override := OS.get_environment("SKILLTOWN_API_URL")
	if not override.is_empty():
		return override.trim_suffix("/")
	if OS.has_feature("web"):
		var origin = JavaScriptBridge.eval("window.location.origin")
		if origin != null and not str(origin).is_empty():
			return str(origin).trim_suffix("/")
	return LOCAL_API_BASE_URL

func log_info(message: String) -> void:
	if DEBUG_MODE:
		print("[INFO] ", message)

func log_error(message: String) -> void:
	print("[ERROR] ", message)

func log_api(endpoint: String, data: Dictionary = {}) -> void:
	if DEBUG_MODE:
		print("[API] ", endpoint, " -> ", JSON.stringify(data))
