"""Small, audited policy-card registry for the hackathon scenario."""

POLICY_CARDS = {
    "ETH-01": {
        "clause_id": "ETH-01",
        "title": "Pending business matters",
        "text": "When the benefit relates to a procurement, renewal, approval, or evaluation you are currently involved in, pause before accepting and confirm the applicable process.",
        "fictional": True,
    },
    "ETH-02": {
        "clause_id": "ETH-02",
        "title": "Transparency and records",
        "text": "A request to hide it, bypass the expense report, or omit the record is a risk signal to stop and consult the designated internal channel.",
        "fictional": True,
    },
    "ETH-03": {
        "clause_id": "ETH-03",
        "title": "Judge with the context",
        "text": "A meal or gift is not automatically a violation; consider the provider, who pays, the timing, the business relationship, and transparency.",
        "fictional": True,
    },
    "DEV-01": {
        "clause_id": "DEV-01",
        "title": "Express a boundary",
        "text": "Stating that you're holding off, the reason you need to confirm, and an appropriate next step helps balance the boundary with the working relationship.",
        "fictional": True,
    },
}


def get_policy_cards(clause_ids: list[str]) -> list[dict]:
    return [POLICY_CARDS[clause_id] for clause_id in clause_ids if clause_id in POLICY_CARDS]
