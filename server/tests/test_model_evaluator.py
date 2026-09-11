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


def pressured_context(turn: int = 1):
    from server.core.grounding import PressureState

    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    node = scenario["nodes"]["alex_public_gift"]
    return build_context(
        "dinner-invitation", scenario["version"], "alex_public_gift", node,
        persona=engine.persona("alex"),
        pressure=PressureState(turn=turn, max_turns=4, history=(("npc", node["line"]),)),
    )


def test_prompt_carries_the_character_and_the_current_tactic():
    ctx = pressured_context(turn=2)
    client = FakeClient(FakeResponse(verdict(character_line="Then let me sweeten it.")))
    ClaudeTextEvaluator(api_key="x", client=client).evaluate(
        "clarify_context", ctx.reference_answers[1].text, context=ctx
    )
    payload = json.loads(client.messages.calls[0]["messages"][0]["content"])
    assert payload["character"]["name"] == "Alex"
    assert payload["tactic"]["id"] == "sweeten"
    assert payload["round"] == {"number": 2, "of": 4}
    assert payload["history"][0]["speaker"] == "npc"


def test_character_line_that_leaks_grounding_is_dropped_but_the_verdict_stands():
    ctx = pressured_context()
    leaking = verdict(character_line="Look, ANNEX-1.2 says twenty-five, so we are fine.")
    result = ClaudeTextEvaluator(api_key="x", client=FakeClient(FakeResponse(leaking))).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "ai" and result.passed
    assert result.character_line == ""


def test_clean_character_line_survives_as_spoken_text():
    ctx = pressured_context()
    spoken = verdict(character_line="  Come on.\n It is a thank-you, nothing more.  ")
    result = ClaudeTextEvaluator(api_key="x", client=FakeClient(FakeResponse(spoken))).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.character_line == "Come on. It is a thank-you, nothing more."


class FakeHTTPResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeHTTPClient:
    """Stands in for httpx.Client: records posts, replays queued responses."""

    def __init__(self, *responses):
        self.responses, self.posts = list(responses), []

    def post(self, url, headers=None, json=None):  # noqa: A002 - httpx's own name
        self.posts.append({"url": url, "headers": headers or {}, "json": json or {}})
        return self.responses.pop(0)


def chat(content: str, finish_reason: str = "stop", refusal: str | None = None) -> FakeHTTPResponse:
    message = {"content": content}
    if refusal:
        message = {"content": None, "refusal": refusal}
    return FakeHTTPResponse(200, {"choices": [{"message": message, "finish_reason": finish_reason}]})


def test_openai_verdict_is_checked_exactly_like_the_claude_one():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    client = FakeHTTPClient(chat(verdict(character_line="Take it, it is nothing.")))
    result = OpenAITextEvaluator(api_key="sk-test", client=client).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "ai" and result.passed
    assert result.character_line == "Take it, it is nothing."
    post = client.posts[0]
    assert post["url"] == "https://api.openai.com/v1/chat/completions"
    assert post["headers"]["Authorization"] == "Bearer sk-test"
    assert post["json"]["messages"][0]["role"] == "system"
    assert post["json"]["response_format"]["type"] == "json_schema"
    # Strict mode rejects the annotations Pydantic adds.
    assert "default" not in str(post["json"]["response_format"])


def test_openai_line_that_leaks_grounding_is_dropped_there_too():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    client = FakeHTTPClient(chat(verdict(character_line="ANNEX-1.2 says twenty-five, so relax.")))
    result = OpenAITextEvaluator(api_key="sk-test", client=client).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "ai" and result.character_line == ""


def test_openai_endpoint_that_wants_max_tokens_is_retried_once_and_remembered():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    refusal = FakeHTTPResponse(400, {"error": {"message": "Unsupported parameter: max_completion_tokens"}})
    client = FakeHTTPClient(refusal, chat(verdict()), chat(verdict()))
    evaluator = OpenAITextEvaluator(api_key="sk-test", client=client)
    assert evaluator.evaluate("clarify_context", ctx.reference_answers[0].text, context=ctx).mode == "ai"
    assert "max_tokens" in client.posts[1]["json"]
    # The second answer must not pay for the same rejection again.
    evaluator.evaluate("clarify_context", ctx.reference_answers[0].text, context=ctx)
    assert len(client.posts) == 3 and "max_tokens" in client.posts[2]["json"]


def test_openai_endpoint_without_schema_support_drops_to_json_object():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    refusal = FakeHTTPResponse(400, {"error": {"message": "response_format json_schema is not supported"}})
    # A chattier gateway wraps the object in a fence; the parser already copes.
    client = FakeHTTPClient(refusal, chat(f"```json\n{verdict()}\n```"))
    result = OpenAITextEvaluator(api_key="sk-test", client=client).evaluate(
        "clarify_context", ctx.reference_answers[0].text, context=ctx
    )
    assert result.mode == "ai"
    assert client.posts[1]["json"]["response_format"] == {"type": "json_object"}


def test_openai_refusal_and_truncation_fall_back_without_blaming_the_learner():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    # Wording the deterministic path has never reviewed, so a lost model reply
    # has to leave the answer ungraded rather than guess at it.
    novel = "I would think about it and probably ask someone."
    for response in (chat("", refusal="I cannot help with that"), chat(verdict(), finish_reason="length")):
        result = OpenAITextEvaluator(api_key="sk-test", client=FakeHTTPClient(response)).evaluate(
            "clarify_context", novel, context=ctx
        )
        assert result.mode == "fallback" and result.assessed is False


def test_openai_http_error_is_a_failure_not_a_verdict():
    from server.core.model_evaluator import OpenAITextEvaluator

    ctx = pressured_context()
    client = FakeHTTPClient(FakeHTTPResponse(429, {"error": "slow down"}))
    result = OpenAITextEvaluator(api_key="sk-test", client=client).evaluate(
        "clarify_context", "I would think about it and probably ask someone.", context=ctx
    )
    assert result.mode == "fallback" and result.assessed is False


def test_credentials_choose_the_transport(monkeypatch):
    from server.core.evaluator import FallbackTextEvaluator
    from server.core.model_evaluator import (
        ClaudeTextEvaluator, OpenAITextEvaluator, build_evaluator, chosen_provider,
    )

    monkeypatch.setenv("SKILLTOWN_MODEL_ENABLED", "true")
    assert chosen_provider() == "none"
    assert isinstance(build_evaluator(), FallbackTextEvaluator)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    assert chosen_provider() == "openai"
    assert isinstance(build_evaluator(), OpenAITextEvaluator)

    # With both kinds present the explicit switch decides, and only then.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    assert chosen_provider() == "openai"
    monkeypatch.setenv("SKILLTOWN_MODEL_PROVIDER", "claude")
    assert isinstance(build_evaluator(), ClaudeTextEvaluator)


def test_model_default_follows_the_provider(monkeypatch):
    from server.core.model_evaluator import DEFAULT_MODEL, DEFAULT_OPENAI_MODEL, default_model_for

    assert default_model_for("openai") == DEFAULT_OPENAI_MODEL
    assert default_model_for("claude") == DEFAULT_MODEL
    monkeypatch.setenv("SKILLTOWN_MODEL", "gpt-4.1")
    assert default_model_for("openai") == "gpt-4.1"
