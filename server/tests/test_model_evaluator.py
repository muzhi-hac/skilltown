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


class RejectsEffortOnce:
    """A cheap model: 400s on effort, then behaves once it is dropped."""

    def __init__(self, verdict_json: str):
        self.messages = self
        self.calls: list[dict] = []
        self._verdict = verdict_json

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "effort" in kwargs.get("output_config", {}):
            raise RuntimeError("Error code: 400 - This model does not support the effort parameter.")
        return FakeResponse(self._verdict)


def test_a_model_without_effort_is_retried_once_and_remembered():
    from server.core.model_evaluator import ClaudeTextEvaluator

    ctx = pressured_context()
    client = RejectsEffortOnce(verdict())
    evaluator = ClaudeTextEvaluator(api_key="x", client=client)
    assert evaluator.evaluate("clarify_context", ctx.reference_answers[0].text, context=ctx).mode == "ai"
    assert "effort" in client.calls[0]["output_config"]
    assert "effort" not in client.calls[1]["output_config"]
    # The structured output itself must survive the retry.
    assert client.calls[1]["output_config"]["format"]["type"] == "json_schema"
    # A second answer must not pay for the same rejection again.
    evaluator.evaluate("clarify_context", ctx.reference_answers[0].text, context=ctx)
    assert len(client.calls) == 3 and "effort" not in client.calls[2]["output_config"]


# --- Alex, deciding what to ask from what the learner evidenced ---------------

def adaptive_context(monkeypatch, node_id="alex_public_gift", turn=1):
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    from server.core.grounding import PressureState
    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    return build_context(
        "dinner-invitation", scenario["version"], node_id, scenario["nodes"][node_id],
        persona=engine.persona("alex"), pressure=PressureState(turn=turn, max_turns=4),
    )


def adaptive_verdict(ctx, **changes):
    """A miss that states the decision but not the reasons."""
    value = {
        "passed": False, "covered": ["decline_or_surrender"],
        "missing": ["recipient_role", "applicable_limit", "record"],
        "overgeneralized": False, "quoted_evidence": "",
        "interpretation": "The decision is stated without its conditions.",
        "feedback": "Say which limit applies and why.", "policy_clause_ids": ["ANNEX-1.2"],
        "strategy_id": "probe_reason", "action_intent": "unclear",
        "action_rule_id": "", "action_quote": "", "character_line": "So why not, exactly?",
    }
    value.update(changes)
    return json.dumps(value)


def evaluate(ctx, answer, payload):
    client = FakeClient(FakeResponse(payload))
    result = ClaudeTextEvaluator(api_key="x", client=client).evaluate(
        "clarify_context", answer, context=ctx
    )
    return result, client.messages


def test_alex_carries_the_rubric_signals_back_to_the_route(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    result, _ = evaluate(ctx, "I will not take it.", adaptive_verdict(ctx))
    assert result.covered == ("decline_or_surrender",)
    assert set(result.missing) == {"recipient_role", "applicable_limit", "record"}
    assert result.strategy_id == "probe_reason"


def test_one_answer_costs_one_model_call(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    _, messages = evaluate(ctx, "I will not take it.", adaptive_verdict(ctx))
    assert len(messages.calls) == 1


def test_a_strategy_the_server_did_not_choose_is_replaced_not_obeyed(monkeypatch):
    """The verdict stays; only the line falls back to the chosen strategy."""
    ctx = adaptive_context(monkeypatch)
    result, _ = evaluate(ctx, "I will not take it.",
                         adaptive_verdict(ctx, strategy_id="concede", character_line="Fine, keep it."))
    assert result.strategy_id == "probe_reason"
    assert result.character_line == ctx.adaptive.fallback_line("probe_reason")
    assert result.mode == "ai", "a good verdict is not thrown away over a bad strategy"


def test_a_committed_violation_needs_the_learner_own_words(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    answer = "I will keep the chocolates and say nothing."
    result, _ = evaluate(ctx, answer, adaptive_verdict(
        ctx, action_intent="committed_violation", action_rule_id="accept_over_limit",
        action_quote="I will keep the chocolates", strategy_id="close_violation"))
    assert result.committed_violation and result.strategy_id == "close_violation"


def test_a_quote_the_learner_never_wrote_is_not_a_violation(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    result, _ = evaluate(ctx, "I will not take it.", adaptive_verdict(
        ctx, action_intent="committed_violation", action_rule_id="accept_over_limit",
        action_quote="I will keep the chocolates", strategy_id="close_violation"))
    # A claimed violation the learner never wrote discredits the whole verdict,
    # rather than quietly becoming an ordinary miss.
    assert result.mode == "fallback"
    assert not result.committed_violation


def test_a_rule_from_another_situation_is_not_a_violation(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    answer = "I will take the cash."
    result, _ = evaluate(ctx, answer, adaptive_verdict(
        ctx, action_intent="committed_violation", action_rule_id="accept_cash_gift",
        action_quote="I will take the cash", strategy_id="close_violation"))
    assert result.mode == "fallback"
    assert not result.committed_violation


def test_a_hypothetical_is_not_a_commitment(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    answer = "If it were under the limit I would keep the chocolates."
    result, _ = evaluate(ctx, answer, adaptive_verdict(
        ctx, action_intent="conditional", action_rule_id="accept_over_limit",
        action_quote="I would keep the chocolates"))
    assert not result.committed_violation


def test_a_pass_that_also_claims_a_violation_is_contradictory(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    answer = ctx.reference_answers[0].text
    result, _ = evaluate(ctx, answer, adaptive_verdict(
        ctx, passed=True, covered=list(ctx.required), missing=[],
        quoted_evidence=answer, action_intent="committed_violation",
        action_rule_id="accept_over_limit", action_quote=answer[:20]))
    assert result.mode == "fallback", "a contradictory verdict is not trusted"


def test_partial_coverage_is_contradictory_for_alex(monkeypatch):
    """covered and missing have to account for every required point."""
    ctx = adaptive_context(monkeypatch)
    result, _ = evaluate(ctx, "I will not take it.",
                         adaptive_verdict(ctx, missing=["recipient_role"]))
    assert result.mode == "fallback"


def test_alex_may_say_register_but_not_a_clause_id(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    spoken = "Do we really have to put it in the register over twenty-six euros?"
    result, _ = evaluate(ctx, "I will not take it.",
                         adaptive_verdict(ctx, character_line=spoken))
    assert result.character_line == spoken

    leaked, _ = evaluate(ctx, "I will not take it.",
                         adaptive_verdict(ctx, character_line="Annex-1.2 says thirty is fine."))
    assert leaked.character_line == ctx.adaptive.fallback_line("probe_reason")


def test_alex_may_not_read_out_the_answer_key(monkeypatch):
    ctx = adaptive_context(monkeypatch)
    result, _ = evaluate(ctx, "I will not take it.", adaptive_verdict(
        ctx, character_line="The correct answer is to decline and log it."))
    assert result.character_line == ctx.adaptive.fallback_line("probe_reason")


def test_the_fixed_ladder_is_untouched_for_everyone_else(monkeypatch):
    """Sam keeps the old shape: no strategy, no signals, tactic by round."""
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    from server.core.grounding import PressureState
    engine = ScenarioEngine()
    scenario = engine.get_scenario("supplier-gift")
    ctx = build_context("supplier-gift", scenario["version"], "sam_cash_limit",
                        scenario["nodes"]["sam_cash_limit"],
                        persona=engine.persona("sam"), pressure=PressureState(turn=1, max_turns=4))
    assert ctx.adaptive is None and ctx.tactic is not None
    payload = json.dumps({
        "passed": False, "covered": [], "missing": list(ctx.required), "overgeneralized": False,
        "quoted_evidence": "", "interpretation": "Not yet.", "feedback": "Check the limit.",
        "policy_clause_ids": [ctx.allowed_clause_ids[0]], "character_line": "Come on, it is routine.",
    })
    result, _ = evaluate(ctx, "I am not sure.", payload)
    assert result.strategy_id == "" and result.covered == () and not result.committed_violation
