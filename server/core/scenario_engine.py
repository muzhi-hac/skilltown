"""Deterministic state transitions over validated grounded scenario content."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.core.content_validation import validate_content


class ScenarioError(ValueError):
    """A learner action is invalid for the committed scenario graph."""


class ScenarioVersionError(RuntimeError):
    """A persisted attempt refers to an older content version."""


@dataclass(frozen=True)
class BranchResult:
    next_node_id: str
    effect: str
    skill_id: str | None
    state: str | None
    interpretation: str | None
    feedback: str | None
    policy_clause_ids: list[str]


class ScenarioEngine:
    def __init__(self, content_path: Path | None = None) -> None:
        path = content_path or Path(__file__).parents[1] / "content" / "scenarios.json"
        self.content = json.loads(path.read_text(encoding="utf-8"))
        validate_content(self.content)

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        try:
            return self.content["scenarios"][scenario_id]
        except KeyError as exc:
            raise ScenarioError(f"Unknown scenario: {scenario_id}") from exc

    def assert_version(self, scenario_id: str, version: str) -> None:
        if self.get_scenario(scenario_id)["version"] != version:
            raise ScenarioVersionError(
                "Scenario content changed. Start a new attempt; previous evidence is retained."
            )

    def persona(self, npc_id: str):
        """The tempter behind an NPC, or None for the review coach."""
        from server.core.grounding import build_persona

        for npc in self.content.get("npcs", []):
            if npc.get("id") == npc_id:
                return build_persona(npc)
        return None

    def max_pressure_turns(self, scenario_id: str) -> int:
        """0 where one answer settles the node, as in screening and review."""
        return int(self.get_scenario(scenario_id).get("pressure", {}).get("max_turns", 0))

    def is_pressure_node(self, scenario_id: str, node_id: str) -> bool:
        node = self.get_node(scenario_id, node_id)
        if not node.get("allow_text") or self.max_pressure_turns(scenario_id) < 1:
            return False
        return self.persona(node["npc_id"]) is not None

    def get_node(self, scenario_id: str, node_id: str) -> dict[str, Any]:
        try:
            return self.get_scenario(scenario_id)["nodes"][node_id]
        except KeyError as exc:
            raise ScenarioError(f"Unknown node: {node_id}") from exc

    def has_node(self, scenario_id: str, node_id: str) -> bool:
        return node_id in self.get_scenario(scenario_id).get("nodes", {})

    def start_node_id(self, scenario_id: str) -> str:
        return str(self.get_scenario(scenario_id)["start_node"])

    def start_node_selector(self, scenario_id: str) -> str | None:
        selector = self.get_scenario(scenario_id).get("start_node_selector")
        return str(selector) if selector else None

    def coaching_node_id(self, scenario_id: str, skill_id: str | None) -> str:
        scenario = self.get_scenario(scenario_id)
        node_id = scenario.get("coaching_nodes", {}).get(skill_id or "")
        if not node_id:
            return self.start_node_id(scenario_id)
        self.get_node(scenario_id, str(node_id))
        return str(node_id)

    def coaching_node_for_source(self, scenario_id: str, node_id: str) -> str | None:
        target = self.get_scenario("ethics-review").get("coaching_sources", {}).get(
            f"{scenario_id}/{node_id}"
        )
        if not target:
            return None
        self.get_node("ethics-review", str(target))
        return str(target)

    def choose(self, scenario_id: str, node_id: str, choice_id: str, allow_unlisted: bool = False) -> BranchResult:
        node = self.get_node(scenario_id, node_id)
        allowed = {choice["id"] for choice in node.get("choices", [])}
        if not allow_unlisted and choice_id not in allowed:
            raise ScenarioError(f"Choice {choice_id!r} is not allowed at node {node_id!r}")
        try:
            branch = node["branches"][choice_id]
        except KeyError as exc:
            raise ScenarioError(f"Choice {choice_id!r} has no branch") from exc
        return BranchResult(
            next_node_id=branch["next_node"], effect=branch.get("effect", "none"),
            skill_id=branch.get("skill_id"), state=branch.get("state"),
            interpretation=branch.get("interpretation"), feedback=branch.get("feedback"),
            policy_clause_ids=list(branch.get("policy_clause_ids", [])),
        )

    def resolve_text(self, scenario_id: str, node_id: str, outcome: str) -> BranchResult:
        node = self.get_node(scenario_id, node_id)
        mapping = node.get("text_branches")
        if not mapping:
            raise ScenarioError(f"Node {node_id!r} does not accept free-text branching")
        branch_id = mapping.get(outcome)
        if not branch_id:
            raise ScenarioError(f"No branch for outcome {outcome!r} at node {node_id!r}")
        return self.choose(scenario_id, node_id, branch_id, allow_unlisted=True)

    def has_text_branches(self, scenario_id: str, node_id: str) -> bool:
        return bool(self.get_node(scenario_id, node_id).get("text_branches"))

    def rewind_target(self, scenario_id: str, node_id: str) -> str:
        node = self.get_node(scenario_id, node_id)
        target = node.get("rewind_to")
        if not target:
            raise ScenarioError("Current node does not allow rewind")
        self.get_node(scenario_id, target)
        return str(target)

    def town_payload(self, skill_states: dict[str, str] | None = None) -> dict[str, Any]:
        states = skill_states or {}
        scenarios = self.content["scenarios"]
        npcs = []
        for npc in self.content["npcs"]:
            # The persona carries the escalation ladder and the model's stage
            # directions. Sending it to the browser would hand the learner the
            # script for the pressure they are supposed to be facing.
            item = {
                key: value for key, value in npc.items()
                if key not in {"scenario_ids", "persona"}
            }
            item["tasks"] = [
                {"scenario_id": scenario_id, "title": scenarios[scenario_id]["title"],
                 "category": scenarios[scenario_id]["category"],
                 "estimated_minutes": scenarios[scenario_id]["estimated_minutes"],
                 "available_modes": scenarios[scenario_id]["available_modes"]}
                for scenario_id in npc["scenario_ids"]
            ]
            skills = [skill for scenario_id in npc["scenario_ids"] for skill in scenarios[scenario_id].get("skills", [])]
            item["recommendation_state"] = self._recommendation_state(skills, states)
            npcs.append(item)
        payload: dict[str, Any] = {"categories": self.content["categories"], "npcs": npcs}
        if self.content.get("screening_task"):
            payload["screening"] = self.content["screening_task"]
        return payload

    @staticmethod
    def _recommendation_state(skills: list[str], states: dict[str, str]) -> str:
        if any(states.get(skill, "unseen") == "needs_practice" for skill in skills):
            return "review"
        if any(states.get(skill, "unseen") == "unseen" for skill in skills):
            return "recommended"
        return "none"
