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
