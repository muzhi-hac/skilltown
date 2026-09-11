from copy import deepcopy

import pytest

from server.core.content_validation import validate_content
from server.core.scenario_engine import ScenarioEngine


def test_production_content_validates():
    validate_content(ScenarioEngine().content)


def test_duplicate_or_unresolved_knowledge_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    node = content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift"]
    node["knowledge"].append("ANNEX-1.1")
    with pytest.raises(ValueError, match="knowledge must be non-empty and unique"):
        validate_content(content)


def test_pressure_node_without_a_spoken_line_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift"]["line"] = ""
    with pytest.raises(ValueError, match="needs a spoken line"):
        validate_content(content)


def test_pressure_node_owned_by_the_coach_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift"]["npc_id"] = "mira"
    with pytest.raises(ValueError, match="no persona to press with"):
        validate_content(content)


def test_incomplete_persona_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    next(npc for npc in content["npcs"] if npc["id"] == "alex")["persona"]["wants"] = " "
    with pytest.raises(ValueError, match="persona.wants"):
        validate_content(content)


def test_single_rung_ladder_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    persona = next(npc for npc in content["npcs"] if npc["id"] == "sam")["persona"]
    persona["tactics"] = persona["tactics"][:1]
    with pytest.raises(ValueError, match="at least two rungs"):
        validate_content(content)


def test_a_consequence_without_a_story_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift_consequence"]["consequence"] = []
    with pytest.raises(ValueError, match="two to five beats"):
        validate_content(content)


def test_a_consequence_beat_without_a_time_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    beats = content["scenarios"]["supplier-gift"]["nodes"]["sam_cash_limit_consequence"]["consequence"]
    beats[0] = {"when": "", "text": beats[0]["text"]}
    with pytest.raises(ValueError, match="when and text"):
        validate_content(content)

def test_consequence_node_without_its_summary_is_rejected():
    """The card at a consequence has one authored sentence and no fallback."""
    content = deepcopy(ScenarioEngine().content)
    del content["scenarios"]["dinner-invitation"]["nodes"]["alex_public_gift_consequence"]["consequence_summary"]
    with pytest.raises(ValueError, match="consequence_summary"):
        validate_content(content)


def test_scenario_without_a_completion_summary_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    content["scenarios"]["supplier-gift"]["completion_summary"] = "  "
    with pytest.raises(ValueError, match="completion_summary"):
        validate_content(content)


def alex_policy(content):
    return next(npc for npc in content["npcs"] if npc["id"] == "alex")["persona"]["adaptive_policy"]


def adaptive_node(content, node_id="alex_public_gift"):
    return content["scenarios"]["dinner-invitation"]["nodes"][node_id]["adaptive_rubric"]


def test_a_grouping_that_drops_a_required_point_is_rejected():
    """Every required point has to be askable, or Alex can never ask for it."""
    content = deepcopy(ScenarioEngine().content)
    adaptive_node(content)["execution"] = []
    with pytest.raises(ValueError, match="adaptive_rubric"):
        validate_content(content)


def test_a_grouping_that_invents_a_criterion_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    adaptive_node(content)["reasons"] = ["recipient_role", "not_a_criterion"]
    with pytest.raises(ValueError, match="adaptive_rubric"):
        validate_content(content)


def test_a_duplicate_strategy_id_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    policy = alex_policy(content)
    policy["strategies"].append(dict(policy["strategies"][0]))
    with pytest.raises(ValueError, match="adaptive_policy"):
        validate_content(content)


def test_a_missing_strategy_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    policy = alex_policy(content)
    policy["strategies"] = [s for s in policy["strategies"] if s["id"] != "probe_action"]
    with pytest.raises(ValueError, match="probe_action"):
        validate_content(content)


def test_a_strategy_without_a_fallback_line_is_rejected():
    """The fallback is what Alex says when the model's line is unusable."""
    content = deepcopy(ScenarioEngine().content)
    for strategy in alex_policy(content)["strategies"]:
        if strategy["id"] == "probe_reason":
            strategy["fallback_line"] = "  "
    with pytest.raises(ValueError, match="fallback_line"):
        validate_content(content)


def test_retry_is_allowed_to_say_nothing():
    content = deepcopy(ScenarioEngine().content)
    for strategy in alex_policy(content)["strategies"]:
        if strategy["id"] == "retry":
            assert strategy["fallback_line"] == ""
    validate_content(content)


def test_duplicate_action_rules_are_rejected():
    content = deepcopy(ScenarioEngine().content)
    rules = adaptive_node(content)["action_rules"]
    rules.append(dict(rules[0]))
    with pytest.raises(ValueError, match="action_rules"):
        validate_content(content)


def test_an_action_rule_without_a_description_is_rejected():
    content = deepcopy(ScenarioEngine().content)
    adaptive_node(content)["action_rules"][0]["description"] = ""
    with pytest.raises(ValueError, match="action_rules"):
        validate_content(content)


def test_the_other_visitors_need_no_adaptive_configuration():
    """Only Alex is adaptive this round; Sam and Jo keep the fixed ladder."""
    content = deepcopy(ScenarioEngine().content)
    for npc in content["npcs"]:
        if npc["id"] != "alex" and npc.get("persona"):
            assert "adaptive_policy" not in npc["persona"]
    validate_content(content)
