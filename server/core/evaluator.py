"""Deterministic fallback for explicitly reviewed, grounded answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core.grounding import EvaluationContext


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    interpretation: str
    feedback: str
    policy_clause_ids: list[str]
    mode: str = "fallback"
    overgeneralized: bool = False
    assessed: bool = True

    @property
    def outcome(self) -> str:
        if not self.assessed:
            return "deferred"
        if self.passed:
            return "pass"
        return "overgeneralized" if self.overgeneralized else "miss"


def normalise_answer(text: str) -> str:
    """Whitespace/case normalisation that deliberately preserves meaning."""
    return " ".join(text.casefold().split())


class FallbackTextEvaluator:
    """Match only reviewed full-answer examples for the current grounded node."""

    def evaluate(
        self,
        rule: str,
        text: str,
        allow_model: bool = True,
        *,
        context: EvaluationContext,
    ) -> EvaluationResult:
        del rule, allow_model
        matched = next(
            (
                item
                for item in context.reference_answers
                if normalise_answer(item.text) == normalise_answer(text)
            ),
            None,
        )
        if matched is None:
            return EvaluationResult(
                passed=False,
                assessed=False,
                interpretation="The deterministic checker has not assessed this wording.",
                feedback=(
                    "Your answer has not been graded. Review the references and retry; "
                    "no learning result was recorded."
                ),
                policy_clause_ids=list(context.allowed_clause_ids),
            )
        return EvaluationResult(
            passed=matched.outcome == "pass",
            assessed=True,
            overgeneralized=matched.outcome == "overgeneralized",
            interpretation="Matched a reviewed whole-answer example for this node.",
            feedback="This answer was checked against a reviewed example for this scenario.",
            policy_clause_ids=list(context.allowed_clause_ids),
        )
