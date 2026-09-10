"""HTTP smoke test for the grounded API contract.

Usage: python3 tools/smoke_api.py [base-url]
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FAILS: list[str] = []


def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, json.dumps(body).encode() if body is not None else None, timeout=90) as response:
            code, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        code, text = error.code, error.read().decode()
    payload = json.loads(text) if text else {}
    print(f"  {'ok ' if code == expect else 'BAD'} {method} {path} -> {code}")
    if code != expect: FAILS.append(f"{method} {path}: {code} != {expect}; {text[:160]}")
    return payload


def answer(attempt, text, token, event_id=None):
    return call("POST", f"/api/v1/attempts/{attempt['attempt_id']}/respond", {
        "client_event_id": event_id or str(uuid.uuid4()), "expected_revision": attempt["revision"],
        "kind": "text", "text": text,
    }, token)


print("1) readiness / session / grounded task")
call("GET", "/health")
ready = call("GET", "/ready")
if not ready.get("ready"): FAILS.append(f"readiness reports {ready}")
session = call("POST", "/api/v1/session", {"display_name": "Smoke test"}, expect=201)
token = session.get("session_token", "")
town = call("GET", "/api/v1/town", token=token)
if {npc.get("id") for npc in town.get("npcs", [])} != {"alex", "sam", "mira", "jo"}: FAILS.append("town NPC set changed")
attempt = call("POST", "/api/v1/attempts", {"scenario_id": "dinner-invitation", "mode": "practice"}, token, expect=201)
node = attempt.get("node") or {}
if node.get("id") != "alex_public_gift": FAILS.append(f"unexpected opening node {node.get('id')}")
if not node.get("policy_cards") or any(card.get("fictional") or not card.get("source") for card in node["policy_cards"]):
    FAILS.append("opening node does not expose real source cards")

print("2) hint, unknown-wording observation, reviewed miss and rewind")
hint = call("POST", f"/api/v1/attempts/{attempt['attempt_id']}/hint", {"client_event_id": str(uuid.uuid4()), "expected_revision": 0}, token)
if not hint.get("policy_card", {}).get("source"): FAILS.append("hint lacks source provenance")
attempt["revision"] = hint["revision"]
unknown = answer(attempt, "This answer is deliberately outside the reviewed matrix.", token)
if unknown.get("assessment_status") == "deferred" and unknown.get("learning_updates") != []:
    FAILS.append("deferred answer recorded learning")
# A model may assess arbitrary wording. Use a fresh attempt for this fixed
# deterministic branch assertion so production and model-disabled smoke agree.
miss_attempt = call("POST", "/api/v1/attempts", {"scenario_id": "dinner-invitation", "mode": "practice"}, token, expect=201)
reviewed = answer(miss_attempt, "€26 is a small gift, so I will accept it.", token)
if reviewed.get("effect") != "consequence_preview": FAILS.append("reviewed miss did not enter consequence preview")
rewound = call("POST", f"/api/v1/attempts/{miss_attempt['attempt_id']}/rewind", {"client_event_id": str(uuid.uuid4()), "expected_revision": reviewed.get("revision", -1)}, token)
if (rewound.get("node") or {}).get("id") != "alex_public_gift": FAILS.append("rewind missed the decision node")

print("3) idempotency and real-source feedback")
event_id = str(uuid.uuid4())
pass_text = "Because this is a German public official and €26 exceeds the €25 threshold, I will decline or hand it to the employing office and keep the receipt in the register."
first = answer(rewound, pass_text, token, event_id)
again = answer(rewound, pass_text, token, event_id)
if first != again: FAILS.append("idempotent replay body changed")
if first.get("assessment_status") != "assessed": FAILS.append("reviewed pass was not assessed")
if not all(card.get("source") for card in (first.get("feedback") or {}).get("policy_clauses", [])): FAILS.append("feedback citation lacks source")

print("4) passport and isolation")
passport = call("GET", "/api/v1/passport", token=token)
if not any(skill.get("evidence") for skill in passport.get("skills", [])): FAILS.append("passport has no evidence")
other = call("POST", "/api/v1/session", {"display_name": "Other"}, expect=201).get("session_token")
call("GET", f"/api/v1/attempts/{attempt['attempt_id']}", token=other, expect=404)

if FAILS:
    print("SMOKE FAILED:")
    print("\n".join(f"  - {item}" for item in FAILS))
    raise SystemExit(1)
print("SMOKE OK — readiness, grounding, deferred, rewind, idempotency, provenance and isolation")
