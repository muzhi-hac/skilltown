from __future__ import annotations

import os
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


def press_through(client, headers, attempt, text):
    """Answer until the character stops pushing, i.e. the arc resolves."""
    node_id, result = attempt["node"]["id"], attempt
    for _ in range(8):
        result = answer(client, headers, result, text).json()
        resolved = result["learning_updates"] or result["node"]["id"] != node_id
        if resolved:
            return result
    raise AssertionError("the pressure arc never resolved")


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
        result = press_through(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
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
        press_through(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
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


def test_ready_reports_hybrid_only_when_dense_actually_answers(tmp_path, dense_available):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        assert client.get("/ready").json()["retrieval_mode"] == "hybrid"


def test_ready_stops_claiming_hybrid_once_dense_fails_at_runtime(tmp_path, monkeypatch, dense_available):
    """A probe that keeps saying hybrid after dense broke is worse than no probe.

    The status is a snapshot taken at startup and deliberately not re-warmed, so
    a dense failure recorded later has to be reflected from what is already
    known rather than by running retrieval inside the probe.
    """
    import server.main as main
    from server.core import knowledge

    warmups = []
    original = main.warmup_rag
    monkeypatch.setattr(main, "warmup_rag", lambda required: warmups.append(required) or original(required))

    with TestClient(main.create_app(tmp_path / "test.sqlite3")) as client:
        assert client.get("/ready").json()["retrieval_mode"] == "hybrid"
        knowledge.mark_dense_runtime_failed("query_encode_error:RuntimeError")

        degraded = client.get("/ready")
        assert degraded.status_code == 200
        assert degraded.json()["retrieval_mode"] == "sparse"
        assert "dense_runtime_failure" in degraded.json()["reason"]

        # A deployment that demands dense should fail this probe, not pass it.
        client.app.state.require_dense = True
        failed = client.get("/ready")
        assert failed.status_code == 503
        assert failed.json()["retrieval_mode"] == "unavailable"

        assert warmups == [False], "the probe re-warmed instead of reporting what it knew"


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


def opening_of(client, scenario_id, node_id):
    return client.app.state.engine.get_node(scenario_id, node_id).get("line", "")


def test_pressure_pushes_back_without_revealing_a_verdict(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        assert attempt["pressure"] == {"turn": 0, "max_turns": 4, "active": True}
        assert [turn["speaker"] for turn in attempt["dialogue"]] == ["npc"]
        assert attempt["dialogue"][0]["text"] == opening_of(client, "dinner-invitation", "alex_public_gift")

        result = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss")).json()
        # Still in the room with the same person, and told nothing about the rule.
        assert result["node"]["id"] == "alex_public_gift"
        assert result["effect"] == "none"
        assert result["feedback"] is None
        assert result["learning_updates"] == []
        assert result["pressure"] == {"turn": 1, "max_turns": 4, "active": True}
        spoken = [turn["text"] for turn in result["dialogue"] if turn["speaker"] == "npc"]
        assert len(spoken) == 2 and spoken[1] != spoken[0]


def test_pressure_arc_ends_in_consequence_and_records_how_long_it_held(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        miss = reference(client, "dinner-invitation", "alex_public_gift", "miss")
        result = press_through(client, headers, attempt, miss)
        assert result["node"]["id"] == "alex_public_gift_consequence"
        assert result["learning_updates"][0]["state"] == "needs_practice"
        # Four rounds of pressure, and the record says the learner gave way.
        assert len([t for t in result["dialogue"] if t["speaker"] == "learner"]) == 4
        passport = client.get("/api/v1/passport", headers=headers).json()
        evidence = [item for skill in passport["skills"] for item in skill["evidence"]]
        assert any("4 rounds of pressure, gave way" in str(item["interpretation"]) for item in evidence)


def test_an_arc_out_of_rounds_lands_on_the_consequence_however_it_was_wrong(tmp_path):
    """Out of rounds is out of rounds, whichever flavour of wrong the last answer was.

    A blanket refusal grades overgeneralized, and that branch loops back to the
    same question on purpose: mid-arc it is another chance. At the end of an arc
    it stranded the learner on a node with no consequence to see and no rewind,
    while the character spoke their closing line as if something had happened.
    """
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        blanket = reference(client, "dinner-invitation", "alex_public_gift", "overgeneralized")
        result = press_through(client, headers, attempt, blanket)
        assert result["node"]["id"] == "alex_public_gift_consequence"
        assert result["effect"] == "consequence_preview"
        assert result["learning_updates"][0]["state"] == "needs_practice"
        rewound = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind", headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": result["revision"]},
        )
        assert rewound.status_code == 200, rewound.text
        assert rewound.json()["node"]["id"] == "alex_public_gift"


def test_a_resting_situation_carries_its_authored_verdict_line(tmp_path):
    """The card has one sentence and no fallback, so the API has to deliver it."""
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        assert attempt["node"]["verdict_line"] == "", "a question is not a verdict"

        miss = reference(client, "dinner-invitation", "alex_public_gift", "miss")
        landed = press_through(client, headers, attempt, miss)
        assert landed["node"]["id"] == "alex_public_gift_consequence"
        assert "public officials" in landed["node"]["verdict_line"]

        screen = create_attempt(client, headers, scenario="screening", mode="screening")
        for node_id in ("screen_clarify", "screen_conflict", "screen_boundary"):
            screen = answer(client, headers, screen, reference(client, "screening", node_id)).json()
        assert screen["is_complete"]
        assert "three starting situations" in screen["node"]["verdict_line"]


def test_holding_the_line_mid_arc_ends_the_pressure_and_moves_on(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        pushed = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss")).json()
        held = answer(client, headers, pushed, reference(client, "dinner-invitation", "alex_public_gift")).json()
        assert held["node"]["id"] == "alex_private_gift"
        assert held["learning_updates"][0]["state"] == "practiced"
        assert "2 rounds of pressure, held the line" in client.get(
            "/api/v1/passport", headers=headers
        ).json()["skills"][0]["evidence"][-1]["interpretation"]
        # The new situation opens with its own person speaking.
        assert held["dialogue"][-1]["text"] == opening_of(client, "dinner-invitation", "alex_private_gift")
        assert held["pressure"] == {"turn": 0, "max_turns": 4, "active": True}


def test_rewind_replays_the_situation_and_restarts_the_pressure(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        spent = press_through(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
        rewound = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind", headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": spent["revision"]},
        ).json()
        assert rewound["node"]["id"] == "alex_public_gift"
        assert rewound["pressure"] == {"turn": 0, "max_turns": 4, "active": True}
        assert [turn["text"] for turn in rewound["dialogue"]] == [
            opening_of(client, "dinner-invitation", "alex_public_gift")
        ]


def test_refresh_restores_the_conversation(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        pushed = answer(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss")).json()
        restored = client.get(f"/api/v1/attempts/{attempt['attempt_id']}", headers=headers).json()
        assert restored["dialogue"] == pushed["dialogue"]
        assert restored["pressure"] == pushed["pressure"]


def test_screening_and_review_settle_on_one_answer(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        screening = create_attempt(client, headers, "screening", "screening")
        assert screening["pressure"] is None
        result = answer(client, headers, screening, reference(client, "screening", "screen_clarify", "miss")).json()
        # A three-question check is not a negotiation: one answer, one verdict.
        assert result["pressure"] is None
        assert result["learning_updates"][0]["state"] == "needs_practice"


def test_town_never_ships_the_pressure_script(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        town = client.get("/api/v1/town", headers=headers).json()
        assert {npc["name"] for npc in town["npcs"]} == {"Alex", "Sam", "Nina", "Jo", "Mira"}
        assert all("persona" not in npc for npc in town["npcs"])
        # The tactic wording must not reach the browser in any field at all.
        assert "conceal" not in str(town)


def test_local_env_file_fills_gaps_without_overriding_the_real_environment(tmp_path, monkeypatch):
    from server.main import load_local_env

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# a comment\n\nANTHROPIC_API_KEY=from-file\nANTHROPIC_BASE_URL=\n"
        "SKILLTOWN_MODEL=\"claude-sonnet-5\"\nbroken line\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SKILLTOWN_MODEL", "already-set")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    loaded = load_local_env(env_file)

    assert loaded == ["ANTHROPIC_API_KEY"]
    assert os.environ["ANTHROPIC_API_KEY"] == "from-file"
    # A blank placeholder is not a value: the SDK reads this name itself, and an
    # empty base URL surfaces as a connection error that is hard to trace back.
    assert "ANTHROPIC_BASE_URL" not in os.environ
    # A value the deployment already set must survive a stray local file.
    assert os.environ["SKILLTOWN_MODEL"] == "already-set"


def test_missing_env_file_is_not_an_error(tmp_path):
    from server.main import load_local_env

    assert load_local_env(tmp_path / "nope.env") == []
