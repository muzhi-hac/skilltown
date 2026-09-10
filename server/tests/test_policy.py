from server.core.policy import get_policy_cards


def test_real_card_has_provenance():
    card = get_policy_cards(["ANNEX-1.2"])[0]
    assert card["clause_id"] == "ANNEX-1.2"
    assert card["fictional"] is False
    assert card["source"].strip()


def test_unknown_id_is_not_invented():
    assert get_policy_cards(["NOT-A-REAL-CLAUSE"]) == []


def test_repeated_ids_are_stable_and_unique():
    cards = get_policy_cards(["ANNEX-1.2", "ANNEX-1.2", "ANNEX-1.1"])
    assert [card["clause_id"] for card in cards] == ["ANNEX-1.2", "ANNEX-1.1"]
