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


def choice(client, headers, attempt, choice_id, event_id=None):
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
        result = choice(client, headers, attempt, "accept_now")
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
        first = choice(client, headers, attempt, "ask_context", event_id)
        second = choice(client, headers, attempt, "ask_context", event_id)
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
        conflict = choice(client, headers, attempt, "accept_now", event_id)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_practice_and_verification_have_distinct_states(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        dinner = create_attempt(client, headers)
        step = choice(client, headers, dinner, "ask_context").json()
        completed = choice(client, headers, step, "pause_consult")
        assert completed.status_code == 200, completed.text
        assert completed.json()["learning_updates"][0]["state"] == "practiced"

        gift = create_attempt(client, headers, "supplier-gift", "verification")
        verified = choice(client, headers, gift, "pause_gift")
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
        risk = choice(client, headers, attempt, "ask_context").json()
        assert risk["node"]["id"] == "dinner_risk"
        preview = choice(client, headers, risk, "accept_hidden").json()
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
        benign = choice(client, headers, attempt, "pause_gift").json()
        done = choice(client, headers, benign, "accept_documented")
        assert done.status_code == 200, done.text
        assert done.json()["is_complete"] is True
        # A duplicated click carries a fresh event id but the old revision: the client
        # must be told to resync (409), not that its choice was invalid (400).
        stale = choice(client, headers, benign, "accept_documented")
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
        risk = choice(client, conflict, dinner, "ask_context").json()
        choice(client, conflict, risk, "accept_hidden")
        coached = create_attempt(client, conflict, "ethics-review", "practice")
        assert coached["node"]["id"] == "review_conflict"
        assert [c["id"] for c in coached["node"]["choices"]] == [
            "who_pays", "hide_record", "celebration"
        ]

        # A learner who over-generalised instead gets the context card.
        _, broad = session(client, "Broad")
        other = create_attempt(client, broad)
        choice(client, broad, other, "reject_everything")
        assert create_attempt(client, broad, "ethics-review", "practice")["node"]["id"] == (
            "review_clarify"
        )


def test_gift_scenario_teaches_the_counter_example_not_blanket_refusal(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, "supplier-gift", "practice")
        # Even the correct answer meets the counter-example before completing.
        benign = choice(client, headers, attempt, "pause_gift").json()
        assert benign["node"]["id"] == "gift_benign"
        assert benign["is_complete"] is False
        refused = choice(client, headers, benign, "refuse_anyway").json()
        assert refused["node"]["id"] == "gift_benign"
        assert refused["learning_updates"][0]["state"] == "needs_practice"
        assert refused["learning_updates"][0]["skill_id"] == "clarify_context"
        finished = choice(client, headers, refused, "accept_documented").json()
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
        second = choice(client, headers, attempt, "who_pays_pending").json()
        assert second["node"]["id"] == "screen_conflict"
        third = choice(client, headers, second, "small_amount_ok").json()
        assert third["node"]["id"] == "screen_boundary"
        # The boundary question belongs to the other category, and says so.
        assert third["node"]["category"] == "personal_development"
        done = choice(client, headers, third, "reason_and_next").json()
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
        second = choice(client, headers, attempt, "who_pays_pending").json()
        third = choice(client, headers, second, "small_amount_ok").json()
        choice(client, headers, third, "reason_and_next")

        marked = {
            npc["id"]: npc["recommendation_state"]
            for npc in client.get("/api/v1/town", headers=headers).json()["npcs"]
        }
        # conflict_awareness was answered wrong, so its NPCs need review; Jo's only
        # skill came out practiced, so Jo is no longer highlighted.
        assert marked["alex"] == "review"
        assert marked["sam"] == "review"
        assert marked["jo"] == "none"
