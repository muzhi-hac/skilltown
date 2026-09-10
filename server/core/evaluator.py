"""Free-text evaluation boundary.

The first vertical slice uses a transparent fallback evaluator. A model-backed
adapter can replace it later without changing API or scenario state ownership.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    interpretation: str
    feedback: str
    policy_clause_ids: list[str]
    mode: str = "fallback"
    # True when the answer refuses everything on principle instead of judging the
    # conditions. That is its own teachable mistake, not a generic miss.
    overgeneralized: bool = False

    @property
    def outcome(self) -> str:
        if self.passed:
            return "pass"
        return "overgeneralized" if self.overgeneralized else "miss"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


BLANKET_REFUSAL_TERMS = (
    "refuse everything", "refuse all", "never accept", "always decline",
    "decline everything", "no gifts ever", "reject all", "always refuse",
)


def _looks_like_blanket_refusal(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in BLANKET_REFUSAL_TERMS)


class FallbackTextEvaluator:
    """Auditable keyword-group fallback; never labelled as AI output."""

    def evaluate(self, rule: str, text: str, allow_model: bool = True) -> EvaluationResult:
        del allow_model  # deterministic path never calls a model
        if rule == "clarify_context":
            groups = [
                _contains_any(text, ("who pays", "who is paying", "paying", "picks up the bill", "footing")),
                _contains_any(text, ("approval", "approve", "renewal", "procurement", "tender", "pending decision")),
                _contains_any(text, ("attend", "attending", "who else", "participants", "guest list")),
                _contains_any(text, ("policy", "policies", "record", "log it", "disclose", "declare")),
            ]
            passed = sum(groups) >= 2
            blanket = _looks_like_blanket_refusal(text)
            return EvaluationResult(
                overgeneralized=blanket and not passed,
                passed=passed,
                interpretation=(
                    "The answer proactively added at least two kinds of key facts."
                    if passed
                    else "The answer doesn't yet cover at least two of: who pays, who attends, pending matters, or the applicable policy."
                ),
                feedback=(
                    "You gathered the key context before drawing a conclusion."
                    if passed
                    else "First confirm who pays, who attends, whether any pending approval is involved, and which policy applies."
                ),
                policy_clause_ids=["ETH-03"],
            )
        if rule == "conflict_awareness":
            business_link = _contains_any(
                text, ("approval", "approve", "renewal", "procurement", "tender", "pending decision")
            )
            transparency = _contains_any(
                text, ("hide", "hidden", "off the books", "record", "expense", "receipt", "transparen")
            )
            action = _contains_any(
                text, ("pause", "hold off", "decline", "not accept", "consult", "report", "check with")
            )
            passed = business_link and action and transparency
            blanket = _looks_like_blanket_refusal(text)
            return EvaluationResult(
                overgeneralized=blanket and not passed,
                passed=passed,
                interpretation=(
                    "The answer identified the pending business relationship and the transparency risk, and proposed pausing or consulting."
                    if passed
                    else "The answer doesn't connect the pending business relationship, the request to hide it, and an appropriate next step all at once."
                ),
                feedback=(
                    "You pointed out the concrete risk signals and gave a next step of pausing and consulting."
                    if passed
                    else "Consider the pending business matter, the request to hide it or bypass the record, and the action of pausing and consulting, all together."
                ),
                policy_clause_ids=["ETH-01", "ETH-02"],
            )
        if rule == "communicate_boundary":
            boundary = _contains_any(text, ("hold off", "not accept", "decline", "for now", "pause"))
            reason = _contains_any(text, ("approval", "policy", "compliance", "conflict", "renewal"))
            next_step = _contains_any(text, ("consult", "confirm", "check", "record", "follow up", "come back"))
            passed = boundary and reason and next_step
            return EvaluationResult(
                passed=passed,
                interpretation=(
                    "The reply includes a clear boundary, a reason, and an actionable next step."
                    if passed
                    else "The reply doesn't yet include the boundary, the reason, and the next step all at once."
                ),
                feedback=(
                    "Clearly expressed: state the boundary, then explain the reason, and give a next step for continuing to work together."
                    if passed
                    else "Try a three-part reply: you're holding off, the reason you need to confirm, and a next step to check or consult."
                ),
                policy_clause_ids=["DEV-01"],
            )
        raise ValueError(f"Unknown text evaluation rule: {rule}")
