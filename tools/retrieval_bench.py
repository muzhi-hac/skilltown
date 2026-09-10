"""Compare retrieval strategies on this corpus, so the choice is measured.

Two question families matter here and they pull in opposite directions:

- paraphrase: the learner does not use the document's words ("how fast must we
  tell the regulator about a leak"). Lexical matching struggles.
- thresholds: the learner names a number or a clause ("€25", "NIS2 24 hours").
  Lexical matching is excellent and embeddings drift to neighbouring topics.

Each case lists every passage a reviewer would accept, because several chunks
often answer the same question (the decision card and the table behind it).

    .venv/bin/python tools/retrieval_bench.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.core import knowledge  # noqa: E402

PARAPHRASE: list[tuple[str, set[str]]] = [
    (
        "how fast must we tell the regulator about a leak of customer records",
        {"ANNEX-2.1", "ANNEX-card-2-we-had-a-data-breach", "ANNEX-5.3"},
    ),
    ("someone reported wrongdoing anonymously, when must we reply", {"ANNEX-6.3"}),
    (
        "a client offers me a pen at a trade fair",
        {"ANNEX-1.1", "ANNEX-1.2", "ANNEX-card-1-my-supplier-invited-me-to-dinner"},
    ),
    (
        "are we allowed to accept twelve thousand in banknotes",
        {"ANNEX-4.1", "ANNEX-card-4-client-wants-to-pay-in-cash"},
    ),
    ("how many hours a week can staff work at most", {"ANNEX-6.1"}),
    (
        "the vendor wants to take me to a football match",
        {"ANNEX-1.2", "ANNEX-1.3", "ANNEX-card-1-my-supplier-invited-me-to-dinner"},
    ),
    (
        "we plan to use an algorithm to screen job applicants",
        {"ANNEX-3.1", "ANNEX-card-3-we-want-to-deploy-an-ai-tool", "REF-2"},
    ),
]

THRESHOLDS: list[tuple[str, set[str]]] = [
    ("gift from a public official worth 40 euro Germany", {"ANNEX-1.2"}),
    (
        "business meal 120 euro per person private sector",
        {"ANNEX-1.3", "ANNEX-card-1-my-supplier-invited-me-to-dinner"},
    ),
    (
        "personal data breach notify supervisory authority 72 hours",
        {"ANNEX-2.1", "ANNEX-5.3", "ANNEX-card-2-we-had-a-data-breach"},
    ),
    (
        "cash payment of 12000 euro prohibited commercial transaction",
        {"ANNEX-4.1", "ANNEX-card-4-client-wants-to-pay-in-cash"},
    ),
    ("beneficial ownership 25 percent threshold", {"ANNEX-4.2"}),
    ("NIS2 early warning within 24 hours of awareness", {"ANNEX-5.1"}),
    ("maximum weekly working hours 48 averaged", {"ANNEX-6.1"}),
    ("whistleblower report acknowledged within 7 days", {"ANNEX-6.3"}),
    ("GDPR fine 20 million or 4 percent of turnover", {"ANNEX-2.4"}),
]


def ids(chunks) -> list[str]:
    return [chunk.id for chunk in chunks]


def fuse(sparse: list[str], dense: list[str], dense_weight: float, limit: int = 3) -> list[str]:
    scores: dict[str, float] = {}
    for ranking, weight in ((sparse, 1.0), (dense, dense_weight)):
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (knowledge.RRF_K + rank)
    return [chunk_id for chunk_id, _ in sorted(scores.items(), key=lambda kv: -kv[1])][:limit]


def main() -> int:
    if not knowledge.dense_available():
        print("dense model unavailable; only the sparse column is meaningful")

    strategies = {
        "sparse only": lambda s, d: s[:3],
        "dense only": lambda s, d: d[:3],
        "RRF 1:1": lambda s, d: fuse(s, d, 1.0),
        f"RRF dense x{knowledge.DENSE_WEIGHT:g}": lambda s, d: fuse(s, d, knowledge.DENSE_WEIGHT),
        "RRF dense x4": lambda s, d: fuse(s, d, 4.0),
    }

    rankings = {
        query: (ids(knowledge.search_sparse(query, 6)), ids(knowledge.search_dense(query, 6)))
        for query, _ in PARAPHRASE + THRESHOLDS
    }

    print(f"{'strategy':16s} {'paraphrase':>12s} {'thresholds':>12s} {'total':>8s}")
    for name, pick in strategies.items():
        counts = []
        for family in (PARAPHRASE, THRESHOLDS):
            hits = sum(
                bool(set(pick(*rankings[query])) & accepted) for query, accepted in family
            )
            counts.append((hits, len(family)))
        total = sum(hit for hit, _ in counts), sum(size for _, size in counts)
        print(
            f"{name:16s} {counts[0][0]:>8}/{counts[0][1]} {counts[1][0]:>9}/{counts[1][1]}"
            f" {total[0]:>5}/{total[1]}"
        )

    print()
    print("Recall@3 against the accepted sets above. This measures retrieval only:")
    print("whether the passage a question is about is in front of the evaluator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
