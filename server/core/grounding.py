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
class Tactic:
    """One rung of a character's escalation ladder, with an authored fallback."""

    id: str
    instruction: str
    line: str


@dataclass(frozen=True)
class Withheld:
    """A fact the character has but does not volunteer.

    The learner has to ask. The wording here is what gets spoken, so the model
    decides only whether it was asked for - never what the number is.
    """

    id: str
    topic: str
    fact: str


@dataclass(frozen=True)
class Persona:
    """The person in the room. Never a teacher: they want the learner to bend."""

    npc_id: str
    name: str
    role: str
    relationship: str
    wants: str
    voice: str
    tactics: tuple[Tactic, ...]
    concede: str
    closing: str
    deflect: str


@dataclass(frozen=True)
class PressureState:
    """Where this answer sits in the character's escalation."""

    turn: int
    max_turns: int
    history: tuple[tuple[str, str], ...] = ()
    # True when the learner has already said what they will do, so this is the
    # character's last attempt rather than the next step of a long ladder.
    final_push: bool = False

    @property
    def is_last_turn(self) -> bool:
        return self.turn >= self.max_turns


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
    opening_line: str = ""
    withheld: tuple[Withheld, ...] = ()
    persona: Persona | None = None
    pressure: PressureState | None = None

    @property
    def allowed_clause_ids(self) -> tuple[str, ...]:
        return tuple(passage.clause_id for passage in self.passages)

    def disclosure(self, fact_id: str) -> str:
        return next((item.fact for item in self.withheld if item.id == fact_id), "")

    @property
    def tactic(self) -> Tactic | None:
        """The rung to play on the next line, or None outside a pressure arc."""
        if not self.persona or not self.persona.tactics or self.pressure is None:
            return None
        if self.pressure.final_push:
            return self.persona.tactics[-1]
        index = min(self.pressure.turn, len(self.persona.tactics)) - 1
        return self.persona.tactics[max(index, 0)]


def build_persona(npc: dict[str, Any]) -> Persona | None:
    """A persona is what makes an NPC a tempter; the coach has none."""
    data = npc.get("persona")
    if not data:
        return None
    return Persona(
        npc_id=npc["id"],
        name=npc["name"],
        role=data["role"],
        relationship=data["relationship"],
        wants=data["wants"],
        voice=data["voice"],
        tactics=tuple(Tactic(**item) for item in data["tactics"]),
        concede=data["concede"],
        closing=data["closing"],
        deflect=data["deflect"],
    )


def build_context(
    scenario_id: str,
    scenario_version: str,
    node_id: str,
    node: dict[str, Any],
    *,
    persona: Persona | None = None,
    pressure: PressureState | None = None,
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
        opening_line=str(node.get("line", "")),
        withheld=tuple(Withheld(**item) for item in node.get("withheld", [])),
        persona=persona,
        pressure=pressure,
    )
