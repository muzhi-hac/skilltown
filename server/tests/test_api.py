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
    response = client.post("/api/v1/attempts", headers=headers, json={"scenario_id": scenario, "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()


def reference(client, scenario_id: str, node_id: str, outcome="pass") -> str:
    node = client.app.state.engine.get_node(scenario_id, node_id)
    return next(item["text"] for item in node["rubric"]["reference_answers"] if item["outcome"] == outcome)


def answer(client, headers, attempt, text, event_id=None):
    return client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/respond", headers=headers,
        json={"client_event_id": event_id or str(uuid4()), "expected_revision": attempt["revision"], "kind": "text", "text": text},
    )


def test_health_ready_and_auth_boundary(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        assert client.get("/health").json() == {"status": "ok", "version": "1.0.0"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["retrieval_mode"] == "sparse"
        assert client.get("/api/v1/town").status_code == 401


def test_nodes_and_hints_expose_real_provenance(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        assert {card["clause_id"] for card in attempt["node"]["policy_cards"]} == {"ANNEX-1.1", "ANNEX-1.2", "ANNEX-1.3"}
        assert all(not card["fictional"] and card["source"] for card in attempt["node"]["policy_cards"])
        restored = client.get(f"/api/v1/attempts/{attempt['attempt_id']}", headers=headers).json()
        assert restored["node"]["policy_cards"] == attempt["node"]["policy_cards"]
        hinted = client.post(f"/api/v1/attempts/{attempt['attempt_id']}/hint", headers=headers, json={"client_event_id": str(uuid4()), "expected_revision": 0})
        assert hinted.status_code == 200
        assert hinted.json()["policy_card"]["source"]


def test_hint_on_complete_node_does_not_change_revision(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        with client.app.state.store.connect() as db:
            db.execute("UPDATE attempts SET current_node_id = 'alex_complete' WHERE id = ?", (attempt["attempt_id"],))
        result = client.post(f"/api/v1/attempts/{attempt['attempt_id']}/hint", headers=headers, json={"client_event_id": str(uuid4()), "expected_revision": 0})
        assert result.status_code == 400
        assert result.json()["error"]["code"] == "hint_not_available"
        with client.app.state.store.connect() as db:
            assert db.execute("SELECT revision FROM attempts WHERE id = ?", (attempt["attempt_id"],)).fetchone()[0] == 0


def test_deferred_answer_keeps_node_and_does_not_write_evidence(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        event_id = str(uuid4())
        result = answer(client, headers, attempt, "This wording is not one of the reviewed answers.", event_id)
        payload = result.json()
        assert payload["assessment_status"] == "deferred"
        assert payload["node"]["id"] == "alex_public_gift"
        assert payload["revision"] == 1 and payload["learning_updates"] == []
        assert answer(client, headers, attempt, "This wording is not one of the reviewed answers.", event_id).json() == payload
        passport = client.get("/api/v1/passport", headers=headers).json()
        assert all(not item["evidence"] for item in passport["skills"])


def test_reviewed_miss_writes_evidence_and_rewinds_to_same_node(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss")).json()
        assert result["effect"] == "consequence_preview"
        assert result["node"]["id"] == "alex_public_gift_consequence"
        assert result["learning_updates"][0]["state"] == "needs_practice"
        rewind = client.post(f"/api/v1/attempts/{attempt['attempt_id']}/rewind", headers=headers, json={"client_event_id": str(uuid4()), "expected_revision": result["revision"]})
        assert rewind.status_code == 200
        assert rewind.json()["node"]["id"] == "alex_public_gift"


def test_verification_evidence_is_demonstrated(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, "supplier-gift", "verification")
        result = answer(client, headers, attempt, reference(client, "supplier-gift", "sam_cash_limit")).json()
        assert result["learning_updates"][0]["state"] == "demonstrated"
        assert result["node"]["id"] == "sam_kyc_boundary"


def test_screening_progresses_for_reviewed_outcomes_and_preserves_category(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, "screening", "screening")
        second = answer(client, headers, attempt, reference(client, "screening", "screen_clarify")).json()
        assert second["node"]["id"] == "screen_conflict"
        third = answer(client, headers, second, reference(client, "screening", "screen_conflict", "miss")).json()
        assert third["node"]["id"] == "screen_boundary"
        assert third["node"]["category"] == "personal_development"
        done = answer(client, headers, third, reference(client, "screening", "screen_boundary")).json()
        assert done["is_complete"] and done["assessment_status"] == "assessed"


def test_coaching_selects_current_version_evidence_and_is_assisted(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
        coached = create_attempt(client, headers, "ethics-review", "practice")
        assert coached["assisted"] is True
        assert coached["node"]["id"] == "coach__dinner-invitation__alex_public_gift"
        assert coached["node"]["policy_cards"][0]["source"]


def test_version_mismatch_blocks_read_mutations_but_not_activity(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        with client.app.state.store.connect() as db:
            db.execute("UPDATE attempts SET scenario_version = '0.0.0' WHERE id = ?", (attempt["attempt_id"],))
        url = f"/api/v1/attempts/{attempt['attempt_id']}"
        assert client.get(url, headers=headers).json()["error"]["code"] == "scenario_version_mismatch"
        response = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift"))
        assert response.status_code == 409 and response.json()["error"]["code"] == "scenario_version_mismatch"
        hint = client.post(url + "/hint", headers=headers, json={"client_event_id": str(uuid4()), "expected_revision": 0})
        rewind = client.post(url + "/rewind", headers=headers, json={"client_event_id": str(uuid4()), "expected_revision": 0})
        assert hint.status_code == rewind.status_code == 409
        activity = client.post(url + "/activity", headers=headers, json={"client_event_id": str(uuid4()), "kind":"start"})
        assert activity.status_code == 204


def test_openapi_response_contract_includes_assessment_status(tmp_path):
    schema = create_app(tmp_path / "test.sqlite3").openapi()
    properties = schema["components"]["schemas"]["AttemptResponse"]["properties"]
    assert properties["assessment_status"]["default"] == "not_requested"


def test_runtime_dense_failure_updates_readiness_and_honours_required_mode(tmp_path, monkeypatch):
    from server.core import knowledge

    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        original_search = knowledge.search

        def broken_dense_search(*args, **kwargs):
            knowledge.mark_dense_runtime_failed("query_encode_error:RuntimeError")
            return original_search(*args, **kwargs)

        monkeypatch.setattr(knowledge, "search", broken_dense_search)
        monkeypatch.setattr(client.app.state, "require_dense", True)
        required = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift"))
        assert required.status_code == 503
        assert client.app.state.rag_status.retrieval_mode == "unavailable"

        knowledge._DENSE_RUNTIME_FAILURE = ""
        monkeypatch.setattr(client.app.state, "require_dense", False)
        relaxed = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift"))
        assert relaxed.status_code == 200
        assert client.app.state.rag_status.retrieval_mode == "sparse"


def test_ready_reads_lifespan_snapshot_without_rewarming(tmp_path, monkeypatch):
    import server.main as main
    from server.core.rag_runtime import RagStatus

    calls = []
    monkeypatch.setattr(main, "warmup_rag", lambda required: calls.append(required) or RagStatus(True, "hybrid", 64, "test", ""))
    app = main.create_app(tmp_path / "test.sqlite3")
    with TestClient(app) as client:
        assert client.get("/ready").json()["retrieval_mode"] == "hybrid"
        assert client.get("/ready").json()["retrieval_mode"] == "hybrid"
    assert calls == [False]
