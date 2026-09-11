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
