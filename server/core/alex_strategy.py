"""What Alex does next, decided from what the learner has evidenced.

The other visitors walk a fixed ladder: rung one on round one, rung two on
round two, whatever was said. Alex reads the rubric signals the evaluator
already produces and validates - covered, missing, overgeneralized, passed -
and asks for the part that is actually absent.

This module is pure on purpose. It holds no content, calls no model and touches
no state, so the priority order can be pinned down in a table test and the model
never gets a vote on which branch was taken.
"""

from __future__ import annotations

from collections.abc import Set

# Every strategy the selector can return. The content has to supply a fallback
# line for each of them except retry, which says nothing at all.
STRATEGIES = (
    "clarify_decision",
    "probe_conditions",
    "probe_reason",
    "probe_action",
    "probe_gap",
    "concede",
    "close_violation",
    "close_review",
    "retry",
)


def select_strategy(
    assessed: bool,
    passed: bool,
    overgeneralized: bool,
    committed_violation: bool,
    is_last_turn: bool,
    covered: Set[str],
    missing: Set[str],
    reasons: Set[str],
    decision: Set[str],
) -> str:
    """Pick one strategy id. Priority is the contract, not the order of the ifs.

    deferred beats everything: nothing was graded, so nothing is known. A pass
    beats a proposed violation, because a verdict that claims both is
    contradictory and the learner should not lose a situation to it.
    """
    if not assessed:
        return "retry"
    if passed:
        return "concede"
    if committed_violation:
        return "close_violation"
    if is_last_turn:
        return "close_review"
    if overgeneralized:
        return "probe_conditions"
    if not covered:
        return "clarify_decision"
    if decision & covered and reasons & missing:
        return "probe_reason"
    if reasons <= covered and missing:
        return "probe_action"
    if decision & missing:
        return "clarify_decision"
    return "probe_gap"
