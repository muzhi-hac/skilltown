"""HTTP smoke test for the SkillTown API, in the order the Godot client calls it.

Usage: python3 tools/smoke_api.py [base-url]   # default http://127.0.0.1:8000

Run it against a local uvicorn process and again against the deployed URL. It
asserts the fields the GDScript client reads, so a contract drift fails here
before it silently breaks the web client.
"""
import json, sys, urllib.error, urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
FAILS = []

def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=10) as r:
            code, text = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        code, text = e.code, e.read().decode()
    payload = json.loads(text) if text else {}
    ok = "ok " if code == expect else "BAD"
    if code != expect:
        FAILS.append(f"{method} {path} -> {code} (expected {expect}): {text[:200]}")
    print(f"  {ok} {method} {path} -> {code}")
    return payload

def need(label, payload, fields):
    missing = [f for f in fields if f not in payload]
    if missing:
        FAILS.append(f"{label}: missing fields the Godot client reads: {missing}")

print("1) health / session / town")
call("GET", "/health")
s = call("POST", "/api/v1/session", {"display_name": "冒烟测试"}, expect=201)
need("session", s, ["session_token", "session"])
tok = s["session_token"]
town = call("GET", "/api/v1/town", token=tok)
need("town", town, ["categories", "npcs"])
alex = next(n for n in town["npcs"] if n["name"] == "Alex")
need("town.npc", alex, ["id", "name", "title", "category", "tasks", "recommendation_state"])
need("town.task", alex["tasks"][0], ["scenario_id", "title", "estimated_minutes", "available_modes"])
print(f"     Alex -> {alex['tasks'][0]['scenario_id']} modes={alex['tasks'][0]['available_modes']}")

print("2) 龙虾任务：创建 attempt")
a = call("POST", "/api/v1/attempts",
         {"scenario_id": alex["tasks"][0]["scenario_id"], "mode": "practice"}, tok, expect=201)
need("attempt", a, ["attempt_id", "scenario_id", "revision", "node", "effect",
                    "learning_updates", "is_complete", "feedback_mode", "timing"])
need("attempt.node", a["node"], ["id", "text", "choices", "allow_text", "policy_cards"])
aid = a["attempt_id"]
print(f"     node={a['node']['id']} choices={[c['id'] for c in a['node']['choices']]}")

print("3) 提交选择：先补齐信息，再答错以触发后果预演")
def choice(cid, rev):
    return call("POST", f"/api/v1/attempts/{aid}/respond",
                {"client_event_id": __import__("uuid").uuid4().__str__(),
                 "expected_revision": rev, "kind": "choice", "choice_id": cid}, tok)

r1 = choice("ask_context", a["revision"])
print(f"     -> {r1['node']['id']} 证据={[ (u['skill_id'],u['state']) for u in r1['learning_updates']]}")
need("feedback", r1["feedback"], ["title", "message", "mode", "policy_clauses"])
r2 = choice("accept_hidden", r1["revision"])
print(f"     -> {r2['node']['id']} effect={r2['effect']}")

print("4) 倒回决策点并重答")
rw = call("POST", f"/api/v1/attempts/{aid}/rewind",
          {"client_event_id": __import__("uuid").uuid4().__str__(),
           "expected_revision": r2["revision"]}, tok)
print(f"     -> {rw['node']['id']} effect={rw['effect']}")
if rw["node"]["id"] != "dinner_risk":
    FAILS.append(f"rewind landed on {rw['node']['id']}, expected dinner_risk")
r3 = choice("pause_consult", rw["revision"])
print(f"     -> {r3['node']['id']} complete={r3['is_complete']} 证据={[(u['skill_id'],u['state']) for u in r3['learning_updates']]}")

print("5) 幂等重放 / 冲突 / 提示")
ev = __import__("uuid").uuid4().__str__()
g = call("POST", "/api/v1/attempts", {"scenario_id": "supplier-gift", "mode": "verification"}, tok, expect=201)
gid = g["attempt_id"]
first = call("POST", f"/api/v1/attempts/{gid}/respond",
             {"client_event_id": ev, "expected_revision": 0, "kind": "choice", "choice_id": "pause_gift"}, tok)
again = call("POST", f"/api/v1/attempts/{gid}/respond",
             {"client_event_id": ev, "expected_revision": 0, "kind": "choice", "choice_id": "pause_gift"}, tok)
if first != again:
    FAILS.append("replaying the same client_event_id returned a different body")
stale = call("POST", f"/api/v1/attempts/{gid}/respond",
             {"client_event_id": __import__("uuid").uuid4().__str__(), "expected_revision": 0,
              "kind": "choice", "choice_id": "pause_gift"}, tok, expect=409)
print(f"     stale revision -> {stale['error']['code']}")

b = call("POST", "/api/v1/attempts", {"scenario_id": "boundary-response", "mode": "practice"}, tok, expect=201)
h = call("POST", f"/api/v1/attempts/{b['attempt_id']}/hint",
         {"client_event_id": __import__("uuid").uuid4().__str__(), "expected_revision": b["revision"]}, tok)
need("hint", h, ["attempt_id", "revision", "assisted", "hint", "policy_card"])
t = call("POST", f"/api/v1/attempts/{b['attempt_id']}/respond",
         {"client_event_id": __import__("uuid").uuid4().__str__(), "expected_revision": h["revision"],
          "kind": "text", "text": "我暂时不接受这个安排，需要先确认谁付款以及是否涉及续约审批，下一步我会按内部渠道咨询。"}, tok)
print(f"     自由回答 mode={t['feedback_mode']} -> {t['node']['id']} 证据={[(u['skill_id'],u['state'],u['assisted']) for u in t['learning_updates']]}")

print("6) 护照 / 推荐 / 会话隔离")
p = call("GET", "/api/v1/passport", token=tok)
need("passport", p, ["skills", "total_active_seconds", "total_model_wait_seconds"])
for sk in p["skills"]:
    print(f"     {sk['skill_id']}: {sk['state']} (证据 {len(sk['evidence'])} 条)")
rec = call("POST", "/api/v1/recommendations", {"max_items": 3}, tok)
for item in rec["items"]:
    print(f"     建议 -> {item['scenario_id']} / {item['skill_id']}: {item['reason'][:40]}")
other = call("POST", "/api/v1/session", {"display_name": "另一个访客"}, expect=201)["session_token"]
call("GET", f"/api/v1/attempts/{aid}", token=other, expect=404)
call("GET", "/api/v1/town", expect=401)

print()
if FAILS:
    print(f"SMOKE FAILED ({len(FAILS)}):")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("SMOKE OK — 会话→龙虾任务→选择→后果预演→倒带→完成→证据/护照/推荐 全部通过真实 HTTP")
