from __future__ import annotations

import json

from server.core.grounding import build_context
from server.core.model_evaluator import ClaudeTextEvaluator, RubricVerdict
from server.core.scenario_engine import ScenarioEngine


class FakeResponse:
    def __init__(self, text: str, stop_reason: str | None = None):
        self.content = [type("Block", (), {"type": "text", "text": text})()]
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, outcomes): self.outcomes, self.calls = list(outcomes), []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outcomes.pop(0)
        if isinstance(value, Exception): raise value
        return value


class FakeClient:
    def __init__(self, *outcomes): self.messages = FakeMessages(outcomes)


def context():
    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    node = scenario["nodes"]["alex_public_gift"]
    return build_context("dinner-invitation", scenario["version"], "alex_public_gift", node)


def verdict(**changes):
    value = {
        "passed": True, "covered": list(context().required), "missing": [], "overgeneralized": False,
        "quoted_evidence": context().reference_answers[0].text,
        "interpretation": "All required points are covered.", "feedback": "Grounded feedback.",
        "policy_clause_ids": ["ANNEX-1.1"],
    }
    value.update(changes)
    return json.dumps(value)


def test_grounded_pass_is_ai_feedback():
    ctx = context()
    result = ClaudeTextEvaluator(api_key="x", client=FakeClient(FakeResponse(verdict()))).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "ai" and result.passed
    assert result.policy_clause_ids == ["ANNEX-1.1"]


def test_invalid_citation_falls_back_to_same_context():
    ctx = context()
    result = ClaudeTextEvaluator(api_key="x", client=FakeClient(FakeResponse(verdict(policy_clause_ids=["ETH-99"])))).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "fallback" and result.passed


def test_prompt_contains_full_passages_but_not_reference_answers():
    ctx = context()
    client = FakeClient(FakeResponse(verdict()))
    ClaudeTextEvaluator(api_key="x", client=client).evaluate("clarify_context", ctx.reference_answers[0].text, context=ctx)
    payload = json.loads(client.messages.calls[0]["messages"][0]["content"])
    assert payload["node_id"] == "alex_public_gift"
    assert payload["passages"][0]["text"] == ctx.passages[0].text
    assert "reference_answers" not in payload
