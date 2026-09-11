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


def test_the_first_knock_is_a_real_situation(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        town = client.get("/api/v1/town", headers=headers).json()
        # There is no warm-up quiz any more: every task belongs to somebody.
        assert "screening" not in str(town)
        assert all(task["available_modes"] for npc in town["npcs"] for task in npc["tasks"])
        started = create_attempt(client, headers, "boundary-response", "practice")
        assert started["node"]["category"] == "personal_development"
        assert started["pressure"]["max_turns"] >= 2


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


def test_the_coach_settles_on_one_answer(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        press_through(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
        review = create_attempt(client, headers, "ethics-review", "practice")
        # Mira is not negotiating with anyone: her node takes one answer.
        assert review["pressure"] is None
        node_id = review["node"]["id"]
        result = answer(client, headers, review, reference(client, "ethics-review", node_id, "miss")).json()
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


class ScriptedEvaluator:
    """Stands in for the model: replays queued (turn_kind, asked, outcome)."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.contexts = []

    def evaluate(self, rule, text, allow_model=True, *, context):
        from server.core.evaluator import EvaluationResult

        self.contexts.append(context)
        kind, asked, outcome = self.turns.pop(0) if self.turns else ("decision", (), "miss")
        return EvaluationResult(
            passed=outcome == "pass",
            overgeneralized=outcome == "overgeneralized",
            interpretation="scripted",
            feedback="scripted feedback",
            policy_clause_ids=list(context.allowed_clause_ids[:1]),
            mode="ai",
            character_line="",
            turn_kind=kind,
            asked=tuple(asked),
        )


def with_evaluator(client, evaluator):
    client.app.state.evaluator = evaluator
    return evaluator


def test_asking_costs_no_round_and_answers_only_what_was_asked(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(("probe", ["value"], "miss")))
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, "How much is it worth?").json()

        assert result["node"]["id"] == "alex_public_gift"
        assert result["pressure"] == {"turn": 0, "max_turns": 4, "active": True}
        assert result["feedback"] is None and result["learning_updates"] == []
        spoken = result["dialogue"][-1]
        # The figure is spoken from the content, never from the model.
        node = client.app.state.engine.get_node("dinner-invitation", "alex_public_gift")
        value = next(item["fact"] for item in node["withheld"] if item["id"] == "value")
        assert spoken["text"] == value and spoken["kind"] == "answer"
        # Nothing they did not ask about leaks out with it.
        sender = next(item["fact"] for item in node["withheld"] if item["id"] == "sender")
        assert sender not in spoken["text"]
        assert [turn["kind"] for turn in result["dialogue"]] == ["line", "probe", "answer"]


def test_asking_about_something_else_gets_deflected(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(("probe", [], "miss")))
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, "What is the weather like?").json()
        persona = client.app.state.engine.persona("alex")
        assert result["dialogue"][-1]["text"] == persona.deflect
        assert result["pressure"]["turn"] == 0


def test_questions_are_finite_so_the_arc_cannot_be_stalled(tmp_path):
    from server.api.routes import MAX_PROBES

    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(*[("probe", ["value"], "miss")] * (MAX_PROBES + 1)))
        result = create_attempt(client, headers)
        for _ in range(MAX_PROBES):
            result = answer(client, headers, result, "And how much is it?").json()
            assert result["pressure"]["turn"] == 0
        # One question too many and the character stops answering and pushes.
        result = answer(client, headers, result, "And how much is it?").json()
        assert result["pressure"]["turn"] == 1


def test_the_record_says_whether_they_asked_before_deciding(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(*[("decision", (), "miss")] * 4))
        attempt = create_attempt(client, headers)
        press_through(client, headers, attempt, "I will just take it.")
        evidence = [
            item for skill in client.get("/api/v1/passport", headers=headers).json()["skills"]
            for item in skill["evidence"]
        ]
        assert any("decided without asking anything" in str(item["interpretation"]) for item in evidence)

        _, other = session(client, "Asker")
        with_evaluator(client, ScriptedEvaluator(("probe", ["value"], "miss"), ("decision", (), "pass")))
        asked_first = create_attempt(client, other)
        pushed = answer(client, other, asked_first, "How much is it?").json()
        answer(client, other, pushed, "I decline it and put it in the register.")
        evidence = [
            item for skill in client.get("/api/v1/passport", headers=other).json()["skills"]
            for item in skill["evidence"]
        ]
        assert any("asked 1 question first" in str(item["interpretation"]) for item in evidence)


def test_the_brief_never_gives_the_withheld_figures_away(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        engine = client.app.state.engine
        for scenario_id, scenario in engine.content["scenarios"].items():
            if not scenario.get("pressure"):
                continue
            for node_id, node in scenario["nodes"].items():
                if not node.get("allow_text"):
                    continue
                shown = f"{node['text']} {node['line']}"
                for item in node["withheld"]:
                    assert item["fact"] not in shown, f"{scenario_id}/{node_id} gives away {item['id']}"
