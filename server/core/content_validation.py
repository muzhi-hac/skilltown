"""One strict validation entry point for committed scenario content."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from typing import Any

from server.core import knowledge
from server.core.evaluator import normalise_answer


OUTCOMES = {"pass", "miss", "overgeneralized"}


def _fail(message: str) -> None:
    raise ValueError(f"Invalid scenario content: {message}")


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_content(content: dict[str, Any]) -> None:
    """Raise ValueError with scenario/node/field context on invalid content."""
    chunks = knowledge.corpus()
    if not chunks or len({chunk.id for chunk in chunks}) != len(chunks):
        _fail("knowledge corpus is empty or has duplicate chunk ids")
    sources_path = Path(__file__).parents[1] / "content" / "knowledge_sources.json"
    try:
        sources = json.loads(sources_path.read_text(encoding="utf-8"))["documents"]
        declared = {item["source"] for item in sources if item.get("verified_date") and item.get("reference_date")}
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        _fail(f"knowledge source metadata is invalid: {exc}")
    expected = {f"server/content/knowledge/{path.name}" for path in knowledge.KNOWLEDGE_DIR.glob("*.md")}
    if declared != expected:
        _fail("knowledge source metadata does not cover the committed corpus")

    scenarios = content.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        _fail("scenarios must be a non-empty object")
    for npc in content.get("npcs", []):
        for scenario_id in npc.get("scenario_ids", []):
            if scenario_id not in scenarios:
                _fail(f"npc {npc.get('id')}: unknown scenario {scenario_id}")
        _validate_persona(npc)
        _validate_module(npc)
    known_npcs = {npc.get("id") for npc in content.get("npcs", [])}
    pressuring = {
        npc.get("id") for npc in content.get("npcs", []) if npc.get("persona")
    }
    adaptive_npcs = {
        npc.get("id") for npc in content.get("npcs", [])
        if (npc.get("persona") or {}).get("adaptive_policy")
    }
    from server.core.recommendations import TASK_BY_SKILL
    for skill_id, (scenario_id, _npc_id) in TASK_BY_SKILL.items():
        if scenario_id not in scenarios:
            _fail(f"TASK_BY_SKILL[{skill_id}] points to an unknown scenario")

    for scenario_id, scenario in scenarios.items():
        _validate_scenario(scenario_id, scenario, known_npcs, pressuring, adaptive_npcs)


PERSONA_FIELDS = ("role", "relationship", "wants", "voice", "concede", "closing", "deflect")
MODULE_FIELDS = ("label", "summary")


def _validate_module(npc: dict[str, Any]) -> None:
    module = npc.get("module")
    npc_id = npc.get("id")
    if not isinstance(module, dict):
        _fail(f"npc {npc_id}: module must be an object")
    for field in MODULE_FIELDS:
        if not _nonempty(module.get(field)):
            _fail(f"npc {npc_id}: module.{field} must be non-empty")
    skills = module.get("skills")
    if not isinstance(skills, list) or not skills or not all(_nonempty(skill) for skill in skills):
        _fail(f"npc {npc_id}: module.skills must be a non-empty list")


def _validate_persona(npc: dict[str, Any]) -> None:
    """A persona is what the model performs, so an incomplete one is an error."""
    persona = npc.get("persona")
    if persona is None:
        return
    npc_id = npc.get("id")
    if not isinstance(persona, dict):
        _fail(f"npc {npc_id}: persona must be an object")
    for field in PERSONA_FIELDS:
        if not _nonempty(persona.get(field)):
            _fail(f"npc {npc_id}: persona.{field} must be non-empty")
    tactics = persona.get("tactics")
    if not isinstance(tactics, list) or len(tactics) < 2:
        _fail(f"npc {npc_id}: persona.tactics needs at least two rungs")
    seen: set[str] = set()
    for tactic in tactics:
        if not isinstance(tactic, dict) or not all(
            _nonempty(tactic.get(key)) for key in ("id", "instruction", "line")
        ):
            _fail(f"npc {npc_id}: each tactic needs id, instruction and line")
        if tactic["id"] in seen:
            _fail(f"npc {npc_id}: duplicate tactic {tactic['id']}")
        seen.add(tactic["id"])
    # Any pressure persona may carry an evidence-driven strategy table.
    if persona.get("adaptive_policy") is not None:
        _validate_adaptive_policy(npc_id, persona["adaptive_policy"])


REQUIRED_STRATEGIES = (
    "clarify_decision", "probe_conditions", "probe_reason", "probe_action", "probe_gap",
    "concede", "close_violation", "close_review", "retry",
)


def _validate_adaptive_policy(npc_id: str, policy: dict[str, Any]) -> None:
    """A gap in this table is a strategy the visitor cannot play."""
    strategies = policy.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        _fail(f"{npc_id}: adaptive_policy.strategies must be non-empty")
    ids = [str(item.get("id", "")) for item in strategies]
    if len(ids) != len(set(ids)):
        _fail(f"{npc_id}: adaptive_policy has duplicate strategy ids")
    for required_id in REQUIRED_STRATEGIES:
        if required_id not in ids:
            _fail(f"{npc_id}: adaptive_policy is missing strategy {required_id!r}")
    for item in strategies:
        # retry says nothing at all: the learner is asked to try again, in the
        # panel's own voice, and the visitor does not speak.
        if item.get("id") != "retry" and not _nonempty(item.get("fallback_line")):
            _fail(f"{npc_id}: adaptive_policy strategy {item.get('id')!r} needs a fallback_line")


def _validate_adaptive_rubric(prefix: str, rubric: dict[str, Any], required: list[str]) -> None:
    """The groups decide which gap is asked about, so they must equal the rubric."""
    grouped: list[str] = []
    for group in ("reasons", "decision", "execution"):
        values = rubric.get(group)
        if not isinstance(values, list):
            _fail(f"{prefix}: adaptive_rubric.{group} must be a list")
        grouped.extend(str(value) for value in values)
    if len(grouped) != len(set(grouped)):
        _fail(f"{prefix}: adaptive_rubric groups repeat a criterion")
    if set(grouped) != set(required):
        _fail(f"{prefix}: adaptive_rubric must group exactly the required criteria")

    rules = rubric.get("action_rules")
    if not isinstance(rules, list) or not rules:
        _fail(f"{prefix}: adaptive_rubric.action_rules must be non-empty")
    rule_ids = [str(rule.get("id", "")) for rule in rules]
    if len(rule_ids) != len(set(rule_ids)) or not all(rule_ids):
        _fail(f"{prefix}: adaptive_rubric.action_rules need unique non-empty ids")
    for rule in rules:
        if not _nonempty(rule.get("description")):
            _fail(f"{prefix}: adaptive_rubric.action_rules need a description")


def _validate_scenario(
    scenario_id: str,
    scenario: dict[str, Any],
    known_npcs: set[str | None] | None = None,
    pressuring: set[str | None] | None = None,
    adaptive_npcs: set[str | None] | None = None,
) -> None:
    known_npcs = known_npcs if known_npcs is not None else set()
    pressuring = pressuring if pressuring is not None else set()
    adaptive_npcs = adaptive_npcs if adaptive_npcs is not None else set()
    pressure = scenario.get("pressure")
    if pressure is not None:
        # Both mistakes end at the same consequence node, so a pressure module
        # owes a story for the other one: refusing everything has its own cost.
        rigid = scenario.get("rigid_consequence")
        if not isinstance(rigid, list) or not 2 <= len(rigid) <= 5:
            _fail(f"{scenario_id}: rigid_consequence needs two to five beats")
        for beat in rigid:
            if not isinstance(beat, dict) or not all(
                _nonempty(beat.get(key)) for key in ("when", "text")
            ):
                _fail(f"{scenario_id}: each rigid_consequence beat needs when and text")
        turns = pressure.get("max_turns") if isinstance(pressure, dict) else None
        if not isinstance(turns, int) or not 2 <= turns <= 6:
            _fail(f"{scenario_id}: pressure.max_turns must be an integer from 2 to 6")
    if not _nonempty(scenario.get("version")):
        _fail(f"{scenario_id}: version must be non-empty")
    if not isinstance(scenario.get("available_modes"), list) or not scenario["available_modes"]:
        _fail(f"{scenario_id}: available_modes must be non-empty")
    if not _nonempty(scenario.get("completion_summary")):
        _fail(f"{scenario_id}: completion_summary must be non-empty")
    nodes = scenario.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        _fail(f"{scenario_id}: nodes must be non-empty")
    start = scenario.get("start_node")
    if start not in nodes:
        _fail(f"{scenario_id}: start_node is not a node")

    coaching = scenario.get("coaching_nodes", {})
    for skill_id, node_id in coaching.items():
        if node_id not in nodes:
            _fail(f"{scenario_id}: coaching_nodes[{skill_id}] is unknown")
    for source, node_id in scenario.get("coaching_sources", {}).items():
        if "/" not in source or node_id not in nodes:
            _fail(f"{scenario_id}: invalid coaching source {source!r}")

    for node_id, node in nodes.items():
        if known_npcs and node.get("npc_id") not in known_npcs:
            _fail(f"{scenario_id}/{node_id}: unknown npc {node.get('npc_id')!r}")
        if pressure and node.get("allow_text"):
            # In a pressure module the learner is talking to a person: they need
            # an opening line, and they have to be someone who actually pushes.
            if not _nonempty(node.get("line")):
                _fail(f"{scenario_id}/{node_id}: a pressure node needs a spoken line")
            _validate_withheld(scenario_id, node_id, node)
            if pressuring and node.get("npc_id") not in pressuring:
                _fail(f"{scenario_id}/{node_id}: {node.get('npc_id')!r} has no persona to press with")
            if node.get("npc_id") in adaptive_npcs and node.get("adaptive_rubric") is None:
                _fail(f"{scenario_id}/{node_id}: adaptive persona needs adaptive_rubric")
        if node.get("adaptive_rubric") is not None and node.get("npc_id") not in adaptive_npcs:
            _fail(f"{scenario_id}/{node_id}: adaptive_rubric needs adaptive_policy")
        if node.get("adaptive_rubric") is not None:
            _validate_adaptive_rubric(
                f"{scenario_id}/{node_id}", node["adaptive_rubric"],
                list((node.get("rubric") or {}).get("required", [])),
            )
        if node_id.endswith("_consequence") and not _nonempty(node.get("consequence_summary")):
            # The verdict card states this one sentence and has nothing to fall
            # back on, so a missing line is a content bug, not a blank line.
            _fail(f"{scenario_id}/{node_id}: consequence_summary must be non-empty")
        _validate_node(scenario_id, node_id, node, nodes)
    _validate_reachability(scenario_id, scenario, nodes)
    if scenario_id != "ethics-review":
        _validate_pass_path(scenario_id, scenario, nodes)


def _validate_withheld(scenario_id: str, node_id: str, node: dict[str, Any]) -> None:
    """Facts the learner has to ask for.

    Every pressure node needs at least two, or there is nothing to find out and
    the clarify_context skill has nothing to measure. The wording here is spoken
    verbatim, so an empty one would have the character answer with silence.
    """
    prefix = f"{scenario_id}/{node_id}"
    withheld = node.get("withheld")
    if not isinstance(withheld, list) or len(withheld) < 2:
        _fail(f"{prefix}: a pressure node needs at least two withheld facts")
    seen: set[str] = set()
    for item in withheld:
        if not isinstance(item, dict) or not all(
            _nonempty(item.get(key)) for key in ("id", "topic", "fact")
        ):
            _fail(f"{prefix}: each withheld fact needs id, topic and fact")
        if item["id"] in seen:
            _fail(f"{prefix}: duplicate withheld fact {item['id']}")
        seen.add(item["id"])
    # The brief is what the learner reads before asking, so it must not already
    # contain the numbers that the facts exist to hand over.
    figures = {token for item in withheld for token in _figures(item["fact"])}
    leaked = figures & _figures(f"{node.get('text', '')} {node.get('line', '')}")
    if leaked:
        _fail(f"{prefix}: the brief already gives away {sorted(leaked)}")


def _figures(text: str) -> set[str]:
    import re

    return set(re.findall(r"\d+", text))


def _validate_node(
    scenario_id: str, node_id: str, node: dict[str, Any], nodes: dict[str, Any]
) -> None:
    prefix = f"{scenario_id}/{node_id}"
    if not _nonempty(node.get("npc_id")) or not _nonempty(node.get("text")):
        _fail(f"{prefix}: npc_id and text are required")
    knowledge_ids = node.get("knowledge", [])
    is_complete = node_id.endswith("_complete") or (scenario_id == "ethics-review" and node_id == "review_no_evidence")
    if not is_complete:
        if not knowledge_ids or len(set(knowledge_ids)) != len(knowledge_ids):
            _fail(f"{prefix}: knowledge must be non-empty and unique")
        for clause_id in knowledge_ids:
            chunk = knowledge.get(clause_id)
            if chunk is None or not chunk.source.strip():
                _fail(f"{prefix}: unresolved real source {clause_id}")

    for branch_id, branch in node.get("branches", {}).items():
        target = branch.get("next_node")
        if target not in nodes:
            _fail(f"{prefix}: branch {branch_id} has unknown target")
        ids = branch.get("policy_clause_ids", [])
        if not set(ids).issubset(set(knowledge_ids)):
            _fail(f"{prefix}: branch {branch_id} cites outside node knowledge")
    if node.get("rewind_to") and node["rewind_to"] not in nodes:
        _fail(f"{prefix}: rewind_to has unknown target")
    if node_id.endswith("_consequence"):
        # Giving way has to lead somewhere. A consequence node that only says
        # "review the conditions" is the lesson without the reason for it.
        beats = node.get("consequence")
        if not isinstance(beats, list) or not 2 <= len(beats) <= 5:
            _fail(f"{prefix}: a consequence needs two to five beats")
        for beat in beats:
            if not isinstance(beat, dict) or not all(
                _nonempty(beat.get(key)) for key in ("when", "text")
            ):
                _fail(f"{prefix}: each consequence beat needs when and text")

    if not node.get("allow_text", False):
        return
    if node.get("choices") != []:
        _fail(f"{prefix}: text nodes must expose no choices")
    if not _nonempty(node.get("text_rule")):
        _fail(f"{prefix}: text_rule is required")
    if not isinstance(node.get("facts"), dict) or not all(
        _nonempty(node["facts"].get(key)) for key in ("domain", "scope", "reference_date")
    ):
        _fail(f"{prefix}: facts.domain/scope/reference_date are required")
    rubric = node.get("rubric")
    if not isinstance(rubric, dict):
        _fail(f"{prefix}: rubric is required")
    required = rubric.get("required")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        _fail(f"{prefix}: rubric.required must be non-empty and unique")
    if set(rubric.get("criteria", {})) != set(required):
        _fail(f"{prefix}: rubric.criteria keys must equal required")
    seen_answers: dict[str, str] = {}
    for answer in rubric.get("reference_answers", []):
        outcome = answer.get("outcome")
        if outcome not in OUTCOMES or not _nonempty(answer.get("text")):
            _fail(f"{prefix}: invalid reference answer")
        normalised = normalise_answer(answer["text"])
        if normalised in seen_answers and seen_answers[normalised] != outcome:
            _fail(f"{prefix}: reference answer has conflicting outcomes")
        seen_answers[normalised] = outcome
    if {answer.get("outcome") for answer in rubric.get("reference_answers", [])} != OUTCOMES:
        _fail(f"{prefix}: reference answers must cover pass/miss/overgeneralized")
    hint = node.get("hint")
    if not isinstance(hint, dict) or not _nonempty(hint.get("text")) or hint.get("clause_id") not in knowledge_ids:
        _fail(f"{prefix}: hint must cite node knowledge")
    mapping = node.get("text_branches")
    if not isinstance(mapping, dict) or set(mapping) != OUTCOMES:
        _fail(f"{prefix}: text_branches must cover pass/miss/overgeneralized")
    for outcome, branch_id in mapping.items():
        if branch_id not in node.get("branches", {}):
            _fail(f"{prefix}: text branch {outcome} is unknown")


def _validate_reachability(scenario_id: str, scenario: dict[str, Any], nodes: dict[str, Any]) -> None:
    starts = [scenario["start_node"], *scenario.get("coaching_nodes", {}).values(), *scenario.get("coaching_sources", {}).values()]
    seen: set[str] = set()
    queue = deque(starts)
    while queue:
        node_id = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = nodes[node_id]
        queue.extend(branch["next_node"] for branch in node.get("branches", {}).values())
        if node.get("rewind_to"):
            queue.append(node["rewind_to"])
    missing = set(nodes) - seen
    if missing:
        _fail(f"{scenario_id}: unreachable nodes {sorted(missing)}")


def _validate_pass_path(scenario_id: str, scenario: dict[str, Any], nodes: dict[str, Any]) -> None:
    node_id = scenario["start_node"]
    seen: set[str] = set()
    counterexample = False
    while node_id not in seen:
        seen.add(node_id)
        node = nodes[node_id]
        counterexample = counterexample or bool(node.get("counterexample"))
        if node_id.endswith("_complete"):
            if not counterexample:
                _fail(f"{scenario_id}: pass path lacks a counterexample")
            return
        mapping = node.get("text_branches")
        if not mapping:
            _fail(f"{scenario_id}: pass path stops at {node_id}")
        node_id = node["branches"][mapping["pass"]]["next_node"]
    _fail(f"{scenario_id}: pass path cycles")
