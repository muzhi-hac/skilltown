"""Training-only policy stand-ins, kept for scenarios not yet grounded in the
real corpus. Anything from server/content/knowledge is a real reference and is
served by server.core.knowledge instead."""

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
    """Resolve clause ids to cards, real corpus passages first.

    An id like ANNEX-1.2 comes from the committed EU documents and is served as
    a real reference with its source named. An id like ETH-01 is a training-only
    stand-in from the table above and is labelled as fictional. Unknown ids are
    dropped rather than invented, which is what stops a model from citing a
    clause that does not exist.
    """
    from server.core import knowledge

    cards: list[dict] = []
    for clause_id in dict.fromkeys(clause_ids):
        chunk = knowledge.get(clause_id)
        if chunk is not None:
            cards.append(
                {
                    "clause_id": chunk.id,
                    "title": chunk.title,
                    "text": chunk.excerpt(),
                    "fictional": False,
                    "source": chunk.source,
                }
            )
            continue
        stand_in = POLICY_CARDS.get(clause_id)
        if stand_in is not None:
            cards.append(stand_in)
    return cards
