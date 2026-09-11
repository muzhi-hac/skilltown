"""The decision table on its own: no model, no HTTP, no content.

Alex picks a strategy from what the learner has already evidenced, so this is
where the priority order is pinned down. Everything above it - the model's
proposal, the route - has to agree with what this returns.
"""

from server.core.alex_strategy import select_strategy


def strategy(**overrides) -> str:
    """A miss on a node whose only required point is a reason, unless told otherwise."""
    call = {
        "assessed": True,
        "passed": False,
        "overgeneralized": False,
        "committed_violation": False,
        "is_last_turn": False,
        "covered": set(),
        "missing": {"role"},
        "reasons": {"role"},
        "decision": set(),
    }
    call.update(overrides)
    return select_strategy(**call)


def test_pass_does_not_wait_for_four_rounds():
    assert select_strategy(True, True, False, False, False,
                           {'recipient_role'}, set(), {'recipient_role'}, set()) == 'concede'


def test_empty_coverage_is_not_a_violation():
    assert select_strategy(True, False, False, False, False,
                           set(), {'role'}, {'role'}, set()) == 'clarify_decision'


def test_overgeneralization_does_not_imply_concession():
    assert select_strategy(True, False, True, False, False,
                           set(), {'role'}, {'role'}, set()) == 'probe_conditions'


def test_deferred_on_last_round_is_not_failure():
    assert select_strategy(False, False, False, False, True,
                           set(), {'role'}, {'role'}, set()) == 'retry'


def test_a_committed_violation_closes_the_situation():
    assert strategy(committed_violation=True) == 'close_violation'


def test_running_out_of_rounds_ends_in_review_not_in_a_verdict_about_the_learner():
    assert strategy(is_last_turn=True) == 'close_review'


def test_a_stated_decision_without_its_reasons_is_asked_for_the_reasons():
    assert strategy(covered={'decline'}, missing={'role'},
                    reasons={'role'}, decision={'decline'}) == 'probe_reason'


def test_complete_reasons_without_the_next_step_are_asked_for_the_action():
    assert strategy(covered={'role'}, missing={'record'},
                    reasons={'role'}, decision=set()) == 'probe_action'


def test_reasons_given_but_the_decision_still_missing_is_asked_what_happens_next():
    """"What would you actually do next" is the question for a missing decision."""
    assert strategy(covered={'role'}, missing={'decline'},
                    reasons={'role'}, decision={'decline'}) == 'probe_action'


def test_a_next_step_with_no_reason_and_no_decision_is_asked_for_the_decision():
    assert strategy(covered={'record'}, missing={'role', 'decline'},
                    reasons={'role'}, decision={'decline'}) == 'clarify_decision'


def test_a_partly_reasoned_answer_where_the_rubric_has_no_decision_point():
    """probe_gap exists for the nodes whose rubric has no decision group."""
    assert strategy(covered={'context'}, missing={'benchmark'},
                    reasons={'context', 'benchmark'}, decision=set()) == 'probe_gap'


def test_deferred_outranks_every_other_signal():
    assert strategy(assessed=False, passed=True, committed_violation=True,
                    is_last_turn=True) == 'retry'


def test_a_pass_outranks_a_proposed_violation():
    """Contradictory signals must not let a violation overwrite a pass."""
    assert strategy(passed=True, committed_violation=True) == 'concede'


def test_the_same_evidence_gets_the_same_strategy_whatever_the_round():
    """Rounds are a ceiling, not the thing that chooses what Alex says."""
    first = strategy(covered={'decline'}, missing={'role'}, reasons={'role'}, decision={'decline'})
    second = strategy(covered={'decline'}, missing={'role'}, reasons={'role'}, decision={'decline'})
    assert first == second == 'probe_reason'
