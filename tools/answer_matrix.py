"""Run independently reviewed grounded cases against a running API.

Usage: .venv/bin/python tools/answer_matrix.py [base-url]
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CASES = json.loads((Path(__file__).parents[1] / "server/tests/fixtures/grounded_cases.json").read_text(encoding="utf-8"))


def call(method: str, path: str, body=None, token: str | None = None):
    request = urllib.request.Request(BASE + path, method=method)
    request.add_header("Content-Type", "application/json")
    if token: request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, json.dumps(body).encode() if body is not None else None, timeout=120) as response:
            return json.loads(response.read().decode() or "{}"), response.status
    except urllib.error.HTTPError as error:
        return json.loads(error.read().decode() or "{}"), error.code


def outcome(result: dict) -> str:
    """Read how the arc ended from the transcript, not from where it landed.

    Both kinds of wrong now finish at the same consequence node on purpose, so
    the node id no longer separates them. The answer that closed the arc is
    tagged, which is the only thing that still tells them apart.
    """
    if result.get("assessment_status") == "deferred": return "deferred"
    said = [turn for turn in result.get("dialogue", []) if turn.get("speaker") == "learner"]
    if said and said[-1].get("kind") == "overgeneralized": return "overgeneralized"
    if result.get("effect") == "consequence_preview": return "miss"
    node = (result.get("node") or {}).get("id", "")
    updates = result.get("learning_updates") or [{}]
    return "overgeneralized" if node in {"alex_public_gift", "sam_cash_limit"} and updates[0].get("state") == "needs_practice" else "pass"


def settle(attempt: dict, text: str, token: str):
    """Answer until the arc resolves: an unresolved round carries no verdict."""
    rounds = max(1, (attempt.get("pressure") or {}).get("max_turns", 1))
    result, status = {}, 0
    for _ in range(rounds):
        result, status = call("POST", f"/api/v1/attempts/{attempt['attempt_id']}/respond", {
            "client_event_id": str(uuid.uuid4()), "expected_revision": attempt["revision"],
            "kind": "text", "text": text,
        }, token)
        if status != 200 or result.get("assessment_status") == "deferred":
            return result, status
        if result.get("learning_updates") or result.get("effect") == "consequence_preview":
            return result, status
        attempt = {**attempt, "revision": result["revision"]}
    return result, status


def main() -> int:
    token, _ = call("POST", "/api/v1/session", {"display_name": "Answer matrix"})
    token = token["session_token"]
    failures = []
    print("case_id\texpected\tactual\tassessment\tfeedback_mode\tcited_ids")
    for case in CASES:
        attempt, status = call("POST", "/api/v1/attempts", {"scenario_id": case["scenario_id"], "mode": "practice"}, token)
        if status != 201 or attempt["node"]["id"] != case["node_id"]:
            failures.append(case["case_id"])
            print(f"{case['case_id']}\t{case['expected_outcome']}\tsetup_error\t-\t-\t-")
            continue
        result, status = settle(attempt, case["text"], token)
        actual = outcome(result) if status == 200 else "http_error"
        cited = [card["clause_id"] for card in ((result.get("feedback") or {}).get("policy_clauses") or [])]
        print(f"{case['case_id']}\t{case['expected_outcome']}\t{actual}\t{result.get('assessment_status')}\t{result.get('feedback_mode')}\t{','.join(cited)}")
        if actual != case["expected_outcome"] or not set(cited).issubset(set(case["allowed_clause_ids"])):
            failures.append(case["case_id"])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
