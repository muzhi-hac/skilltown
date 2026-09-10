"""Evidence-grounded task recommendation rules."""

from __future__ import annotations

from uuid import uuid4


TASK_BY_SKILL = {
    "clarify_context": ("dinner-invitation", "alex"),
    "conflict_awareness": ("supplier-gift", "sam"),
    "communicate_boundary": ("boundary-response", "jo"),
}


REASONS = {
    "unseen": "这项能力还没有情境证据，建议先完成一个短任务。",
    "needs_practice": "最近的回答显示这里仍有具体缺口，建议换一个情境练习。",
    "practiced": "你已在练习中展示过这项能力，建议用未见案例独立验证。",
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
