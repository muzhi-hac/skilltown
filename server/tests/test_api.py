from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app


def session(client: TestClient, name: str = "Learner") -> tuple[str, dict[str, str]]:
    response = client.post("/api/v1/session", json={"display_name": name})
    assert response.status_code == 201
    token = response.json()["session_token"]
    return token, {"Authorization": f"Bearer {token}"}


def create_attempt(client, headers, scenario="dinner-invitation", mode="practice"):
    response = client.post(
        "/api/v1/attempts",
        headers=headers,
        json={"scenario_id": scenario, "mode": mode},
    )
    assert response.status_code == 201, response.text
    return response.json()


def answer(client, headers, attempt, choice_id, event_id=None):
    return client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/respond",
        headers=headers,
        json={
            "client_event_id": event_id or str(uuid4()),
            "expected_revision": attempt["revision"],
            "kind": "choice",
            "choice_id": choice_id,
        },
    )


# The learner types their own answer; the deterministic evaluator decides which
# audited branch it lands on (no model is configured under test).
ASK_CONTEXT = "Who pays for this, and is it tied to the renewal approval I own?"
VAGUE = "Sounds fun, let's just go."
BLANKET = "I refuse everything like this, no exceptions."
SPOT_CONFLICT = (
    "The renewal approval sits with me and they asked me to skip the expense record, "
    "so I will pause and consult compliance."
)
SMALL_AMOUNT = "It is a small amount so it is fine."
BOUNDARY_FULL = (
    "I will decline for now because the renewal approval sits with me; I will consult "
    "compliance and we can meet once it is closed."
)
DOCUMENTED = (
    "The renewal approval is already closed and the expense record is complete, so I can "
    "join and log it."
)
REPORT_IT = "I will report this celebration as a violation."


def answer(client, headers, attempt, text, event_id=None):
    return client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/respond",
        headers=headers,
        json={
            "client_event_id": event_id or str(uuid4()),
            "expected_revision": attempt["revision"],
            "kind": "text",
            "text": text,
        },
    )


def test_health_and_auth_boundary(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        assert client.get("/health").json() == {"status": "ok", "version": "1.0.0"}
        unauthorized = client.get("/api/v1/town")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "unauthorized"


def test_town_exposes_two_categories_and_four_npcs(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        response = client.get("/api/v1/town", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert {item["id"] for item in payload["categories"]} == {
            "ethics_compliance",
            "personal_development",
        }
        assert {npc["id"] for npc in payload["npcs"]} == {"alex", "sam", "mira", "jo"}


def test_wrong_choice_creates_evidence_and_can_rewind(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, VAGUE)
        assert result.status_code == 200, result.text
        payload = result.json()
        assert payload["effect"] == "consequence_preview"
        assert payload["node"]["id"] == "dinner_consequence"
        assert payload["learning_updates"][0]["state"] == "needs_practice"
        rewind = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind",
            headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": payload["revision"]},
        )
        assert rewind.status_code == 200, rewind.text
        assert rewind.json()["node"]["id"] == "dinner_invite"


def test_respond_is_idempotent_and_rejects_payload_reuse(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        event_id = str(uuid4())
        first = answer(client, headers, attempt, ASK_CONTEXT, event_id)
        second = answer(client, headers, attempt, ASK_CONTEXT, event_id)
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        conflict = answer(client, headers, attempt, VAGUE, event_id)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_practice_and_verification_have_distinct_states(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        dinner = create_attempt(client, headers)
        step = answer(client, headers, dinner, ASK_CONTEXT).json()
        completed = answer(client, headers, step, SPOT_CONFLICT)
        assert completed.status_code == 200, completed.text
        assert completed.json()["learning_updates"][0]["state"] == "practiced"

        gift = create_attempt(client, headers, "supplier-gift", "verification")
        verified = answer(client, headers, gift, SPOT_CONFLICT)
        assert verified.status_code == 200, verified.text
        assert verified.json()["learning_updates"][0]["state"] == "demonstrated"

        passport = client.get("/api/v1/passport", headers=headers)
        assert passport.status_code == 200, passport.text
        skills = {item["skill_id"]: item for item in passport.json()["skills"]}
        assert skills["conflict_awareness"]["state"] == "demonstrated"
        assert len(skills["conflict_awareness"]["evidence"]) == 2


def test_text_fallback_is_explicit_and_grounded(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        response = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/respond",
            headers=headers,
            json={
                "client_event_id": str(uuid4()),
                "expected_revision": 0,
                "kind": "text",
                "text": "我想先确认谁付款，以及这是否和续约审批有关。",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["feedback_mode"] == "fallback"
        assert payload["node"]["id"] == "dinner_risk"
        assert payload["feedback"]["policy_clauses"][0]["fictional"] is True


def test_sessions_are_isolated_and_deletable(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, first_headers = session(client, "First")
        _, second_headers = session(client, "Second")
        attempt = create_attempt(client, first_headers)
        hidden = client.get(
            f"/api/v1/attempts/{attempt['attempt_id']}", headers=second_headers
        )
        assert hidden.status_code == 404
        deleted = client.delete("/api/v1/session", headers=first_headers)
        assert deleted.status_code == 204
        assert client.get("/api/v1/passport", headers=first_headers).status_code == 401


def test_recommendations_only_reference_existing_tasks(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        response = client.post("/api/v1/recommendations", headers=headers, json={"max_items": 3})
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert len(items) == 3
        assert {item["scenario_id"] for item in items} <= {
            "dinner-invitation", "supplier-gift", "boundary-response"
        }


def test_rewind_returns_to_the_node_where_the_mistake_happened(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        risk = answer(client, headers, attempt, ASK_CONTEXT).json()
        assert risk["node"]["id"] == "dinner_risk"
        preview = answer(client, headers, risk, SMALL_AMOUNT).json()
        assert preview["effect"] == "consequence_preview"
        assert preview["node"]["id"] == "dinner_consequence"
        rewind = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind",
            headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": preview["revision"]},
        )
        assert rewind.status_code == 200, rewind.text
        assert rewind.json()["node"]["id"] == "dinner_risk"


def test_stale_revision_reports_conflict_so_the_client_can_resync(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, "supplier-gift", "verification")
        benign = answer(client, headers, attempt, SPOT_CONFLICT).json()
        done = answer(client, headers, benign, DOCUMENTED)
        assert done.status_code == 200, done.text
        assert done.json()["is_complete"] is True
        # A duplicated click carries a fresh event id but the old revision: the client
        # must be told to resync (409), not that its choice was invalid (400).
        stale = answer(client, headers, benign, DOCUMENTED)
        assert stale.status_code == 409, stale.text
        error = stale.json()["error"]
        assert error["code"] == "revision_conflict"
        assert error["retryable"] is True
        assert error["latest_attempt_url"].endswith(attempt["attempt_id"])


def test_web_build_is_served_from_the_same_origin_without_shadowing_the_api(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<canvas id='canvas'></canvas>", encoding="utf-8")
    (web / "index.wasm").write_bytes(b"\x00asm")
    app = create_app(tmp_path / "test.sqlite3", web_dir=web)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "canvas" in page.text
        wasm = client.get("/index.wasm")
        assert wasm.status_code == 200
        assert wasm.headers["content-type"] == "application/wasm"
        # The API and health routes must still win over the static mount.
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/v1/town").status_code == 401


def test_mira_coaches_the_weakest_skill_from_the_learners_own_evidence(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        # No evidence yet: Mira must say so instead of inventing a gap.
        _, fresh = session(client, "Fresh")
        cold = create_attempt(client, fresh, "ethics-review", "practice")
        assert cold["node"]["id"] == "review_no_evidence"

        # A learner who missed the hidden-arrangement risk gets the conflict card.
        _, conflict = session(client, "Conflict")
        dinner = create_attempt(client, conflict)
        risk = answer(client, conflict, dinner, ASK_CONTEXT).json()
        answer(client, conflict, risk, SMALL_AMOUNT)
        coached = create_attempt(client, conflict, "ethics-review", "practice")
        assert coached["node"]["id"] == "review_conflict"
        # Coaching is answered in the learner's own words, not by picking an option.
        assert coached["node"]["choices"] == []
        assert coached["node"]["allow_text"] is True

        # A learner who over-generalised instead gets the context card.
        _, broad = session(client, "Broad")
        other = create_attempt(client, broad)
        answer(client, broad, other, BLANKET)
        assert create_attempt(client, broad, "ethics-review", "practice")["node"]["id"] == (
            "review_clarify"
        )


def test_gift_scenario_teaches_the_counter_example_not_blanket_refusal(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, "supplier-gift", "practice")
        # Even the correct answer meets the counter-example before completing.
        benign = answer(client, headers, attempt, SPOT_CONFLICT).json()
        assert benign["node"]["id"] == "gift_benign"
        assert benign["is_complete"] is False
        refused = answer(client, headers, benign, BLANKET).json()
        assert refused["node"]["id"] == "gift_benign"
        assert refused["learning_updates"][0]["state"] == "needs_practice"
        assert refused["learning_updates"][0]["skill_id"] == "clarify_context"
        finished = answer(client, headers, refused, DOCUMENTED).json()
        assert finished["node"]["id"] == "gift_complete"
        assert finished["is_complete"] is True


def test_activity_events_drive_the_reported_active_time(tmp_path):
    from uuid import uuid4 as _uuid

    app = create_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        for kind in ("start", "heartbeat", "end"):
            recorded = client.post(
                f"/api/v1/attempts/{attempt['attempt_id']}/activity",
                headers=headers,
                json={"client_event_id": str(_uuid()), "kind": kind},
            )
            assert recorded.status_code == 204, recorded.text
        # Real gaps here are milliseconds, so the sum rounds to zero seconds; the
        # rule itself is covered by test_activity.py. What matters here is that the
        # events reach the projection instead of leaving it permanently at zero.
        store = app.state.store
        passport = client.get("/api/v1/passport", headers=headers).json()
        assert passport["total_active_seconds"] == 0

        # With crafted timestamps the same path reports real minutes.
        with store.connect() as db:
            db.execute(
                "DELETE FROM activity_events WHERE attempt_id = ?", (attempt["attempt_id"],)
            )
            row = db.execute(
                "SELECT session_id FROM attempts WHERE id = ?", (attempt["attempt_id"],)
            ).fetchone()
            owner = row["session_id"]
            for offset, kind in ((0, "start"), (15, "heartbeat"), (30, "heartbeat")):
                db.execute(
                    "INSERT INTO activity_events VALUES (?, ?, ?, ?, ?)",
                    (
                        owner,
                        attempt["attempt_id"],
                        f"crafted-{offset}",
                        kind,
                        f"2026-09-10T12:00:{offset:02d}Z",
                    ),
                )
        assert store.refresh_active_seconds(owner, attempt["attempt_id"]) == 30
        passport = client.get("/api/v1/passport", headers=headers).json()
        assert passport["total_active_seconds"] == 30


def test_screening_is_offered_by_the_server_and_labels_each_question(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        town = client.get("/api/v1/town", headers=headers).json()
        assert town["screening"]["scenario_id"] == "screening"
        assert town["screening"]["available_modes"] == ["screening"]

        attempt = create_attempt(client, headers, "screening", "screening")
        assert attempt["node"]["id"] == "screen_clarify"
        assert attempt["node"]["category"] == "ethics_compliance"
        second = answer(client, headers, attempt, ASK_CONTEXT).json()
        assert second["node"]["id"] == "screen_conflict"
        third = answer(client, headers, second, SMALL_AMOUNT).json()
        assert third["node"]["id"] == "screen_boundary"
        # The boundary question belongs to the other category, and says so.
        assert third["node"]["category"] == "personal_development"
        done = answer(client, headers, third, BOUNDARY_FULL).json()
        assert done["is_complete"] is True

        skills = {
            item["skill_id"]: item["state"]
            for item in client.get("/api/v1/passport", headers=headers).json()["skills"]
        }
        assert skills == {
            "clarify_context": "practiced",
            "conflict_awareness": "needs_practice",
            "communicate_boundary": "practiced",
        }


def test_town_marks_npcs_from_the_learners_own_record(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        fresh = {
            npc["id"]: npc["recommendation_state"]
            for npc in client.get("/api/v1/town", headers=headers).json()["npcs"]
        }
        assert fresh == {
            "alex": "recommended", "sam": "recommended",
            "mira": "recommended", "jo": "recommended",
        }

        attempt = create_attempt(client, headers, "screening", "screening")
        second = answer(client, headers, attempt, ASK_CONTEXT).json()
        third = answer(client, headers, second, SMALL_AMOUNT).json()
        answer(client, headers, third, BOUNDARY_FULL)

        marked = {
            npc["id"]: npc["recommendation_state"]
            for npc in client.get("/api/v1/town", headers=headers).json()["npcs"]
        }
        # conflict_awareness was answered wrong, so its NPCs need review; Jo's only
        # skill came out practiced, so Jo is no longer highlighted.
        assert marked["alex"] == "review"
        assert marked["sam"] == "review"
        assert marked["jo"] == "none"


def test_api_labels_ai_feedback_and_falls_back_once_the_budget_is_spent(tmp_path, monkeypatch):
    from uuid import uuid4 as _uuid

    from server.core.evaluator import EvaluationResult

    monkeypatch.setenv("SKILLTOWN_MODEL_CALL_BUDGET", "1")

    class StubEvaluator:
        def __init__(self):
            self.allowed = []

        def evaluate(self, rule, text, allow_model=True):
            self.allowed.append(allow_model)
            mode = "ai" if allow_model else "fallback"
            return EvaluationResult(
                passed=True,
                interpretation="stub",
                feedback="stub feedback",
                policy_clause_ids=["ETH-03"],
                mode=mode,
            )

    app = create_app(tmp_path / "test.sqlite3")
    stub = StubEvaluator()
    app.state.evaluator = stub
    with TestClient(app) as client:
        _, headers = session(client)

        def answer(attempt):
            return client.post(
                f"/api/v1/attempts/{attempt['attempt_id']}/respond",
                headers=headers,
                json={
                    "client_event_id": str(_uuid()),
                    "expected_revision": attempt["revision"],
                    "kind": "text",
                    "text": "我先确认谁付款以及是否涉及续约审批，再决定是否参加。",
                },
            ).json()

        first = answer(create_attempt(client, headers))
        assert first["feedback_mode"] == "ai"
        assert first["feedback"]["mode"] == "ai"

        # The one allowed model call is spent, so the next answer is deterministic
        # and says so instead of silently pretending to be AI feedback.
        second = answer(create_attempt(client, headers))
        assert second["feedback_mode"] == "fallback"
        assert stub.allowed == [True, False]


def test_free_text_lands_on_an_audited_branch_including_over_refusal(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        assert attempt["node"]["choices"] == []
        assert attempt["node"]["allow_text"] is True

        # Refusing everything on principle is its own branch, not a generic miss:
        # it teaches the counter-example instead of just marking the answer wrong.
        broad = answer(client, headers, attempt, BLANKET).json()
        assert broad["node"]["id"] == "dinner_overgeneralized"
        assert broad["learning_updates"][0]["state"] == "needs_practice"

        # Gathering the missing facts moves the story on, in the learner's words.
        asked = answer(client, headers, broad, ASK_CONTEXT).json()
        assert asked["node"]["id"] == "dinner_risk"
        assert asked["learning_updates"][0]["skill_id"] == "clarify_context"
        assert asked["learning_updates"][0]["state"] == "practiced"

        # A miss at the risk node still triggers the audited consequence preview.
        missed = answer(client, headers, asked, SMALL_AMOUNT).json()
        assert missed["node"]["id"] == "dinner_consequence"
        assert missed["effect"] == "consequence_preview"

        rewound = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind",
            headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": missed["revision"]},
        ).json()
        assert rewound["node"]["id"] == "dinner_risk"

        done = answer(client, headers, rewound, SPOT_CONFLICT).json()
        assert done["node"]["id"] == "dinner_complete"
        assert done["is_complete"] is True
        # The evidence is the learner's own sentence, not a choice id.
        evidence = client.get("/api/v1/passport", headers=headers).json()["skills"]
        observed = [
            item["observed_response"]
            for skill in evidence
            for item in skill["evidence"]
        ]
        assert SPOT_CONFLICT in observed
