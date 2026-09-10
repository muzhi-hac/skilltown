"""Build immutable, source-bounded contexts for answer evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from server.core import knowledge


class GroundingError(ValueError):
    """A scenario node cannot be grounded in the committed corpus."""


@dataclass(frozen=True)
class Passage:
    clause_id: str
    title: str
    text: str
    source: str
    retrieval: Literal["hybrid", "exact"]


@dataclass(frozen=True)
class ReferenceAnswer:
    text: str
    outcome: Literal["pass", "miss", "overgeneralized"]


@dataclass(frozen=True)
class EvaluationContext:
    scenario_id: str
    scenario_version: str
    node_id: str
    question: str
    facts_json: str
    grading_question: str
    required: tuple[str, ...]
    criteria: tuple[tuple[str, str], ...]
    forbidden_claims: tuple[str, ...]
    reference_answers: tuple[ReferenceAnswer, ...]
    passages: tuple[Passage, ...]

    @property
    def allowed_clause_ids(self) -> tuple[str, ...]:
        return tuple(passage.clause_id for passage in self.passages)


def build_context(
    scenario_id: str,
    scenario_version: str,
    node_id: str,
    node: dict[str, Any],
) -> EvaluationContext:
    """Pin evaluation to this node's declared sources, never to user input."""
    ids = tuple(dict.fromkeys(node.get("knowledge", [])))
    if not ids:
        raise GroundingError(f"{scenario_id}/{node_id}: empty knowledge")

    chunks: dict[str, knowledge.Chunk] = {}
    for clause_id in ids:
        chunk = knowledge.get(clause_id)
        if chunk is None or not chunk.source.strip():
            raise GroundingError(f"{scenario_id}/{node_id}: unresolved source {clause_id}")
        chunks[clause_id] = chunk

    try:
        rubric = node["rubric"]
        required = tuple(rubric["required"])
        criteria = tuple((key, rubric["criteria"][key]) for key in required)
        references = tuple(ReferenceAnswer(**item) for item in rubric["reference_answers"])
    except (KeyError, TypeError) as exc:
        raise GroundingError(f"{scenario_id}/{node_id}: invalid rubric") from exc

    facts_json = json.dumps(node["facts"], ensure_ascii=False, sort_keys=True)
    # The learner answer intentionally does not participate in retrieval.  The
    # declared node anchors set the complete citation boundary.
    query = f"{node['text']}\n{facts_json}\n{rubric['question']}"
    hits = knowledge.search(query, limit=max(3, len(ids)))
    ranked = tuple(dict.fromkeys(chunk.id for chunk in hits if chunk.id in chunks))
    ordered = ranked + tuple(clause_id for clause_id in ids if clause_id not in ranked)
    passages = tuple(
        Passage(
            clause_id=clause_id,
            title=chunks[clause_id].title,
            text=chunks[clause_id].text,
            source=chunks[clause_id].source,
            retrieval="hybrid" if clause_id in ranked else "exact",
        )
        for clause_id in ordered
    )
    return EvaluationContext(
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        node_id=node_id,
        question=node["text"],
        facts_json=facts_json,
        grading_question=rubric["question"],
        required=required,
        criteria=criteria,
        forbidden_claims=tuple(rubric.get("forbidden_claims", [])),
        reference_answers=references,
        passages=passages,
    )
