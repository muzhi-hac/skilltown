from server.core.evaluator import FallbackTextEvaluator
from server.core.grounding import build_context
from server.core.scenario_engine import ScenarioEngine


def context(node_id="alex_public_gift"):
    engine = ScenarioEngine()
    scenario = engine.get_scenario("dinner-invitation")
    return build_context("dinner-invitation", scenario["version"], node_id, scenario["nodes"][node_id])


def test_reviewed_answers_are_assessed_with_whitespace_and_case_normalisation():
    value = context()
    text = value.reference_answers[0].text
    result = FallbackTextEvaluator().evaluate("clarify_context", f"  {text.upper()}  ", context=value)
    assert result.assessed and result.passed and result.outcome == "pass"


def test_unreviewed_or_cross_node_answers_are_deferred():
    fallback = FallbackTextEvaluator()
    current = context()
    result = fallback.evaluate("clarify_context", current.reference_answers[0].text + " The opposite is true.", context=current)
    assert not result.assessed and result.outcome == "deferred"
    other = context("alex_private_gift")
    result = fallback.evaluate("clarify_context", other.reference_answers[0].text, context=current)
    assert not result.assessed
