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
        # They said what they would do, so one more push is all that is left.
        assert result["pressure"] == {"turn": 1, "max_turns": 2, "active": True}
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
        # Settled answer, one more push, then the consequence: two rounds, not four.
        assert len([t for t in result["dialogue"] if t["speaker"] == "learner"]) == 2
        passport = client.get("/api/v1/passport", headers=headers).json()
        evidence = [item for skill in passport["skills"] for item in skill["evidence"]]
        assert any("2 rounds of pressure, gave way" in str(item["interpretation"]) for item in evidence)


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

        # The other resting place is the end of a path, which says what the
        # practice covered without claiming the learner aced it.
        walked = create_attempt(client, headers, scenario="data-incidents")
        for node_id in ("mira_privacy_clock", "mira_nis2_stages", "mira_encrypted_backup"):
            walked = answer(client, headers, walked, reference(client, "data-incidents", node_id)).json()
        assert walked["is_complete"]
        assert "notification timing" in walked["node"]["verdict_line"]


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
        # Each turn is (kind, asked, outcome) or (kind, asked, outcome, committed).
        self.turns = [tuple(turn) + (False,) * (4 - len(turn)) for turn in turns]
        self.contexts = []

    def evaluate(self, rule, text, allow_model=True, *, context):
        from server.core.evaluator import EvaluationResult

        self.contexts.append(context)
        kind, asked, outcome, committed = (
            self.turns.pop(0) if self.turns else ("decision", (), "miss", False)
        )
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
            committed=bool(committed),
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


def test_a_settled_answer_is_pushed_once_not_four_times(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(
            ("decision", (), "miss", True),
            ("decision", (), "miss", True),
        ))
        attempt = create_attempt(client, headers)
        first = answer(client, headers, attempt, "I am taking it. That is my answer.").json()
        assert first["pressure"] == {"turn": 1, "max_turns": 2, "active": True}
        assert first["learning_updates"] == []

        second = answer(client, headers, first, "Still taking it.").json()
        # Heard once, pushed once, done - not made to repeat themselves twice more.
        assert second["node"]["id"] == "alex_public_gift_consequence"
        assert second["learning_updates"][0]["state"] == "needs_practice"


def test_thinking_aloud_still_gets_the_whole_ladder(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(*[("decision", (), "miss", False)] * 4))
        result = create_attempt(client, headers)
        for expected in (1, 2, 3):
            result = answer(client, headers, result, "I suppose it might be alright?").json()
            assert result["pressure"] == {"turn": expected, "max_turns": 4, "active": True}
        result = answer(client, headers, result, "I suppose it might be alright?").json()
        assert result["node"]["id"] == "alex_public_gift_consequence"


def test_the_last_push_is_the_hardest_sell(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        with_evaluator(client, ScriptedEvaluator(("decision", (), "miss", True)))
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, "I am taking it.").json()
        # Someone who has decided gets the bottom rung, not the gentle opener.
        persona = client.app.state.engine.persona("alex")
        assert result["dialogue"][-1]["text"] == persona.tactics[-1].line


def test_giving_way_returns_a_story_not_just_a_verdict(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        result = press_through(client, headers, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
        assert result["node"]["id"] == "alex_public_gift_consequence"
        beats = result["node"]["consequence"]
        # The story develops: several beats, each with its own point in time.
        assert len(beats) >= 2
        assert all(beat["when"] and beat["text"] for beat in beats)
        assert len({beat["when"] for beat in beats}) == len(beats)
        # It is the situation that plays out, not a restatement of the rule.
        assert not any("ANNEX" in beat["text"] for beat in beats)


def test_every_consequence_has_somewhere_to_go(tmp_path):
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        engine = client.app.state.engine
        nodes = [
            (scenario_id, node_id, node)
            for scenario_id, scenario in engine.content["scenarios"].items()
            for node_id, node in scenario["nodes"].items()
            if node_id.endswith("_consequence")
        ]
        assert len(nodes) >= 10
        for scenario_id, node_id, node in nodes:
            beats = node.get("consequence", [])
            assert 2 <= len(beats) <= 5, f"{scenario_id}/{node_id} has {len(beats)} beats"
            assert node.get("rewind_to"), f"{scenario_id}/{node_id} cannot be rewound"

# --- Alex, adaptive ----------------------------------------------------------

class StubEvaluator:
    """Stands in for the model so a route test can pin one verdict at a time."""

    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def evaluate(self, rule, text, allow_model=True, *, context):
        self.calls.append(text)
        result = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        return result


def adaptive_client(tmp_path, monkeypatch, *results):
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    app = create_app(tmp_path / "test.sqlite3")
    client = TestClient(app)
    client.__enter__()
    if results:
        app.state.evaluator = StubEvaluator(*results)
    return client


def alex_result(**changes):
    from server.core.evaluator import EvaluationResult
    values = {
        "passed": False, "interpretation": "Stated a decision, not the conditions.",
        "feedback": "Say which limit applies.", "policy_clause_ids": ["ANNEX-1.2"],
        "mode": "ai", "covered": ("decline_or_surrender",),
        "missing": ("recipient_role", "applicable_limit", "record"),
        "strategy_id": "probe_reason", "character_line": "So why not, exactly?",
    }
    values.update(changes)
    return EvaluationResult(**values)


def test_alex_presses_on_the_gap_and_stays_in_the_situation(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result())
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        replied = answer(client, headers, attempt, "I will not take it.").json()
        assert replied["node"]["id"] == "alex_public_gift"
        assert replied["learning_updates"] == [], "no verdict is revealed mid-arc"
        assert replied["dialogue"][-1]["text"] == "So why not, exactly?"
        assert replied["pressure"]["turn"] == 1
    finally:
        client.__exit__(None, None, None)


def test_alex_concedes_on_the_first_round_when_the_answer_is_complete(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result(
        passed=True, strategy_id="concede", covered=("recipient_role", "applicable_limit",
        "decline_or_surrender", "record"), missing=(), character_line="All right. I hear you."))
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        replied = answer(client, headers, attempt, "Declined and logged.").json()
        assert replied["node"]["id"] == "alex_private_gift", "a pass moves the situation on"
        assert replied["learning_updates"][0]["state"] != "needs_practice"
    finally:
        client.__exit__(None, None, None)


def test_a_committed_violation_ends_the_situation_on_the_first_round(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result(
        strategy_id="close_violation", committed_violation=True,
        character_line="Then we have a decision.",
        interpretation="Committed to keeping an unrecorded gift."))
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        replied = answer(client, headers, attempt, "I will keep it and say nothing.").json()
        assert replied["node"]["id"] == "alex_public_gift_consequence"
        assert replied["effect"] == "consequence_preview"
        assert replied["learning_updates"][0]["state"] == "needs_practice"
    finally:
        client.__exit__(None, None, None)


def test_running_out_of_rounds_says_the_evidence_was_short_not_that_alex_won(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result(),
                             alex_result(), alex_result(), alex_result(strategy_id="close_review"))
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        result = attempt
        for _ in range(4):
            result = answer(client, headers, result, "I will not take it.").json()
        assert result["node"]["id"] == "alex_public_gift_consequence"
        passport = client.get("/api/v1/passport", headers=headers).json()
        evidence = [item for skill in passport["skills"] for item in skill["evidence"]]
        assert any("without sufficient evidence" in str(item["interpretation"]) for item in evidence)
        assert not any("gave way" in str(item["interpretation"]) for item in evidence)
    finally:
        client.__exit__(None, None, None)


def test_a_deferred_answer_costs_alex_nothing(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result(
        passed=False, mode="fallback", assessed=False, strategy_id="", character_line="",
        covered=(), missing=()))
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        replied = answer(client, headers, attempt, "Something unreviewed.").json()
        assert replied["node"]["id"] == "alex_public_gift"
        assert replied["pressure"]["turn"] == 0, "a round nobody graded is not a round"
        assert replied["learning_updates"] == []
    finally:
        client.__exit__(None, None, None)


def test_the_other_visitors_keep_the_fixed_ladder(tmp_path, monkeypatch):
    """Sam is untouched by the switch: same rungs, same order."""
    monkeypatch.setenv("SKILLTOWN_ALEX_ADAPTIVE_ENABLED", "true")
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)
        attempt = create_attempt(client, headers, scenario="supplier-gift")
        miss = reference(client, "supplier-gift", attempt["node"]["id"], "miss")
        replied = answer(client, headers, attempt, miss).json()
        spoken = [turn["text"] for turn in replied["dialogue"] if turn["speaker"] == "npc"]
        engine = client.app.state.engine
        ladder = [tactic.line for tactic in engine.persona("sam").tactics]
        assert spoken[-1] in ladder


def test_replaying_the_same_event_costs_no_round_and_no_model_call(tmp_path, monkeypatch):
    client = adaptive_client(tmp_path, monkeypatch, alex_result())
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        event = str(uuid4())
        first = answer(client, headers, attempt, "I will not take it.", event).json()
        again = answer(client, headers, attempt, "I will not take it.", event).json()
        assert first == again
        assert first["pressure"]["turn"] == 1
        assert len(client.app.state.evaluator.calls) == 1
    finally:
        client.__exit__(None, None, None)


def test_a_rewound_situation_starts_its_pressure_again(tmp_path, monkeypatch):
    """The old rounds are gone: they were answered about a decision undone."""
    client = adaptive_client(tmp_path, monkeypatch, alex_result())
    try:
        _, headers = session(client)
        attempt = create_attempt(client, headers)
        result = answer(client, headers, attempt, "I will not take it.").json()
        result = answer(client, headers, result, "Still no.").json()
        assert result["pressure"]["turn"] == 2

        client.app.state.evaluator = StubEvaluator(alex_result(
            strategy_id="close_violation", committed_violation=True,
            character_line="Then we have a decision."))
        landed = answer(client, headers, result, "I will keep it and say nothing.").json()
        assert landed["node"]["id"] == "alex_public_gift_consequence"

        rewound = client.post(
            f"/api/v1/attempts/{attempt['attempt_id']}/rewind", headers=headers,
            json={"client_event_id": str(uuid4()), "expected_revision": landed["revision"]},
        ).json()
        assert rewound["node"]["id"] == "alex_public_gift"
        assert rewound["pressure"]["turn"] == 0
        learner_turns = [t for t in rewound["dialogue"] if t["speaker"] == "learner"]
        assert learner_turns == [], "the old arc is not evidence for the new one"
    finally:
        client.__exit__(None, None, None)


def test_the_story_matches_which_way_the_learner_was_wrong(tmp_path):
    """Both mistakes land on the same node, so the node cannot narrate one of them."""
    with TestClient(create_app(tmp_path / "test.sqlite3")) as client:
        _, headers = session(client)

        _, gave_way = session(client, "Gave way")
        attempt = create_attempt(client, gave_way)
        result = press_through(client, gave_way, attempt, reference(client, "dinner-invitation", "alex_public_gift", "miss"))
        gave_way_beats = [beat["text"] for beat in result["node"]["consequence"]]
        assert any("register" in text or "audit" in text for text in gave_way_beats)

        _, refused = session(client, "Refused everything")
        attempt = create_attempt(client, refused)
        result = press_through(client, refused, attempt, reference(client, "dinner-invitation", "alex_public_gift", "overgeneralized"))
        assert result["node"]["id"] == "alex_public_gift_consequence"
        rigid_beats = [beat["text"] for beat in result["node"]["consequence"]]
        # Refusing everything has its own cost, and it is not the one above.
        assert rigid_beats and rigid_beats != gave_way_beats
        assert not any("audit pulls" in text for text in rigid_beats)

        # A refresh must not swap the story back.
        restored = client.get(f"/api/v1/attempts/{attempt['attempt_id']}", headers=refused).json()
        assert [beat["text"] for beat in restored["node"]["consequence"]] == rigid_beats
