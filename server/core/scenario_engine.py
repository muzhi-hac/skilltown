"""Deterministic scenario state transitions.

The model may evaluate free text, but it never owns state transitions or hidden
policy facts. This service is the authority for allowed choices and rewind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ScenarioError(ValueError):
    """Raised when scenario content or a learner action is invalid."""


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

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        try:
            return self.content["scenarios"][scenario_id]
        except KeyError as exc:
            raise ScenarioError(f"Unknown scenario: {scenario_id}") from exc

    def get_node(self, scenario_id: str, node_id: str) -> dict[str, Any]:
        scenario = self.get_scenario(scenario_id)
        try:
            return scenario["nodes"][node_id]
        except KeyError as exc:
            raise ScenarioError(f"Unknown node: {node_id}") from exc

    def has_node(self, scenario_id: str, node_id: str) -> bool:
        return node_id in self.get_scenario(scenario_id).get("nodes", {})

    def start_node_id(self, scenario_id: str) -> str:
        return str(self.get_scenario(scenario_id)["start_node"])

    def choose(self, scenario_id: str, node_id: str, choice_id: str) -> BranchResult:
        node = self.get_node(scenario_id, node_id)
        allowed = {choice["id"] for choice in node.get("choices", [])}
        if choice_id not in allowed:
            raise ScenarioError(f"Choice {choice_id!r} is not allowed at node {node_id!r}")
        try:
            branch = node["branches"][choice_id]
        except KeyError as exc:
            raise ScenarioError(f"Choice {choice_id!r} has no branch") from exc
        return BranchResult(
            next_node_id=branch["next_node"],
            effect=branch.get("effect", "none"),
            skill_id=branch.get("skill_id"),
            state=branch.get("state"),
            interpretation=branch.get("interpretation"),
            feedback=branch.get("feedback"),
            policy_clause_ids=list(branch.get("policy_clause_ids", [])),
        )

    def rewind_target(self, scenario_id: str, node_id: str) -> str:
        node = self.get_node(scenario_id, node_id)
        target = node.get("rewind_to")
        if not target:
            raise ScenarioError("Current node does not allow rewind")
        self.get_node(scenario_id, target)
        return str(target)

    def town_payload(self) -> dict[str, Any]:
        scenarios = self.content["scenarios"]
        npcs = []
        for npc in self.content["npcs"]:
            item = {key: value for key, value in npc.items() if key != "scenario_ids"}
            item["tasks"] = [
                {
                    "scenario_id": scenario_id,
                    "title": scenarios[scenario_id]["title"],
                    "category": scenarios[scenario_id]["category"],
                    "estimated_minutes": scenarios[scenario_id]["estimated_minutes"],
                    "available_modes": scenarios[scenario_id]["available_modes"],
                }
                for scenario_id in npc["scenario_ids"]
            ]
            item["recommendation_state"] = "none"
            npcs.append(item)
        return {"categories": self.content["categories"], "npcs": npcs}
