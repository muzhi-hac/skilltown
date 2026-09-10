"""Evidence-grounded task recommendation rules."""

from __future__ import annotations

from uuid import uuid4


TASK_BY_SKILL = {
    "clarify_context": ("dinner-invitation", "alex"),
    "conflict_awareness": ("supplier-gift", "sam"),
    "communicate_boundary": ("boundary-response", "jo"),
}


REASONS = {
    "unseen": "This skill has no situational evidence yet; start with a short task.",
    "needs_practice": "Recent answers show a specific gap here; try practicing with a different situation.",
    "practiced": "You've shown this skill in practice; verify it independently with a case you haven't seen.",
}


def recommend(skills: list[dict], max_items: int) -> list[dict]:
    priority = {"needs_practice": 0, "unseen": 1, "practiced": 2, "demonstrated": 3}
    ordered = sorted(skills, key=lambda item: priority[item["state"]])
    results = []
    for skill in ordered:
        if skill["state"] == "demonstrated":
            continue
        scenario_id, npc_id = TASK_BY_SKILL[skill["skill_id"]]
        results.append(
            {
                "id": str(uuid4()),
                "scenario_id": scenario_id,
                "npc_id": npc_id,
                "skill_id": skill["skill_id"],
                "reason": REASONS[skill["state"]],
                "evidence_ids": [item["id"] for item in skill["evidence"][-2:]],
            }
        )
        if len(results) >= max_items:
            break
    return results
