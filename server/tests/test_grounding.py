from __future__ import annotations

import pytest

from server.core import knowledge
from server.core.grounding import GroundingError, build_context


def node():
    return {
        "knowledge": ["ANNEX-2.1"], "text": "When does the clock start?",
        "facts": {"domain": "data_incidents", "scope": "test", "reference_date": "2026-09-10"},
        "rubric": {"question": "Identify awareness.", "required": ["awareness"],
                   "criteria": {"awareness": "The clock starts at awareness."},
                   "forbidden_claims": [],
                   "reference_answers": [{"text": "At awareness.", "outcome": "pass"}]},
    }


def test_context_pins_sources_and_preserves_full_text(monkeypatch):
    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [knowledge.get("ANNEX-1.2")])
    context = build_context("data-incidents", "2.0.0", "privacy_clock", node())
    assert context.allowed_clause_ids == ("ANNEX-2.1",)
    assert context.passages[0].retrieval == "exact"
    assert context.passages[0].text == knowledge.get("ANNEX-2.1").text
    assert context.scenario_version == "2.0.0"


def test_context_rejects_empty_or_unknown_sources():
    with pytest.raises(GroundingError, match="empty knowledge"):
        build_context("s", "2", "n", {**node(), "knowledge": []})
    with pytest.raises(GroundingError, match="unresolved source"):
        build_context("s", "2", "n", {**node(), "knowledge": ["NOPE"]})


def test_duplicate_search_results_do_not_duplicate_passages(monkeypatch):
    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [knowledge.get("ANNEX-2.1")] * 2)
    context = build_context("s", "2", "n", node())
    assert len(context.passages) == 1
    assert context.passages[0].retrieval == "hybrid"


def alex_pieces():
    """The real Alex persona and node, so the test moves when the content does."""
    from server.core.scenario_engine import ScenarioEngine
    engine = ScenarioEngine()
    return engine, engine.persona("alex"), engine.get_node("dinner-invitation", "alex_public_gift")


def pressure_state():
    from server.core.grounding import PressureState
    return PressureState(turn=1, max_turns=4)


def test_alex_gets_his_strategy_table_when_the_switch_is_on(monkeypatch):
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    _, persona, node = alex_pieces()
    context = build_context("dinner-invitation", "2.1.0", "alex_public_gift", node,
                            persona=persona, pressure=pressure_state())
    assert context.adaptive is not None
    assert context.adaptive.decision == frozenset({"decline_or_surrender"})
    assert context.adaptive.fallback_line("probe_action")
    assert context.adaptive.fallback_line("retry") == ""


def test_the_switch_defaults_to_the_fixed_ladder(monkeypatch):
    monkeypatch.delenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", raising=False)
    _, persona, node = alex_pieces()
    context = build_context("dinner-invitation", "2.1.0", "alex_public_gift", node,
                            persona=persona, pressure=pressure_state())
    assert context.adaptive is None
    assert context.tactic is not None, "the old ladder still has to work"


def test_only_alex_is_adaptive(monkeypatch):
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    from server.core.scenario_engine import ScenarioEngine
    engine = ScenarioEngine()
    node = engine.get_node("supplier-gift", "sam_cash_limit")
    context = build_context("supplier-gift", "1.0.0", "sam_cash_limit", node,
                            persona=engine.persona("sam"), pressure=pressure_state())
    assert context.adaptive is None


def test_a_situation_with_nobody_pressing_is_never_adaptive(monkeypatch):
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    _, persona, node = alex_pieces()
    context = build_context("dinner-invitation", "2.1.0", "alex_public_gift", node,
                            persona=persona, pressure=None)
    assert context.adaptive is None
