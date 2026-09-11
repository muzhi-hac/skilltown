"""FastAPI routes for grounded, versioned learning attempts."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from server.api.models import (
    ActivityRequest, AnswerRequest, AttemptResponse, CreateAttemptRequest,
    CreateSessionRequest, CreateSessionResponse, FeedbackMode, HintResponse,
    MutationRequest, PassportResponse, RecommendationRequest,
    RecommendationResponse, SessionView, TownResponse,
)
from server.core import knowledge
from server.core.grounding import PressureState, build_context
from server.core.policy import get_policy_cards
from server.core.recommendations import recommend
from server.core.session import require_session
from server.storage import RevisionConflictError, Store

router = APIRouter(prefix="/api/v1")
Session = Annotated[dict, Depends(require_session)]


def _services(request: Request):
    return request.app.state.store, request.app.state.engine, request.app.state.evaluator


def _node_view(engine, scenario_id: str, node_id: str) -> dict:
    scenario = engine.get_scenario(scenario_id)
    node = engine.get_node(scenario_id, node_id)
    return {
        "id": node_id,
        "npc_id": node["npc_id"],
        "category": node.get("category", scenario["category"]),
        "text": node["text"],
        "line": node.get("line", ""),
        "choices": node.get("choices", []),
        "allow_text": node.get("allow_text", False),
        "policy_cards": get_policy_cards(list(dict.fromkeys(node.get("knowledge", [])))),
        "consequence": node.get("consequence", []),
    }


def _open_turns(dialogue: list[dict], node_id: str) -> list[dict]:
    return [
        item for item in dialogue
        if not item["resolved"] and item.get("node_id") == node_id
    ]


def _decisions(dialogue: list[dict], node_id: str) -> int:
    return sum(
        1 for item in _open_turns(dialogue, node_id)
        if item["speaker"] == "learner" and item.get("kind") in {"decision", "commit"}
    )


def _has_committed(dialogue: list[dict], node_id: str) -> bool:
    """Somebody who has said what they will do has been heard."""
    return any(item.get("kind") == "commit" for item in _open_turns(dialogue, node_id))


def _pressure_view(engine, scenario_id: str, node_id: str, dialogue: list[dict]) -> dict | None:
    """Rounds already spent against the character still holding the floor.

    A learner who has committed gets one more push, not the rest of the ladder,
    so the meter shortens to match what is actually left.
    """
    if not engine.is_pressure_node(scenario_id, node_id):
        return None
    turn = _decisions(dialogue, node_id)
    max_turns = engine.max_pressure_turns(scenario_id)
    if _has_committed(dialogue, node_id):
        max_turns = min(max_turns, turn + 1)
    return {"turn": turn, "max_turns": max_turns, "active": turn < max_turns}


def _opening_line(engine, scenario_id: str, node_id: str) -> str:
    """What the next person says on walking into the situation."""
    try:
        return str(engine.get_node(scenario_id, node_id).get("line", ""))
    except Exception:  # a missing node is the caller's problem, not the transcript's
        return ""


def _authored_line(context, committed: bool = False) -> str:
    """The written rung of the ladder, used when no usable model line arrived.

    Someone who has already decided gets the bottom of the ladder: this is the
    character's last attempt, so it is no time for the gentle opener.
    """
    persona = context.persona
    if committed and persona and persona.tactics:
        return persona.tactics[-1].line
    tactic = context.tactic
    return tactic.line if tactic else ""


MAX_PROBES = 4


def _probes_used(dialogue: list[dict], node_id: str) -> int:
    return sum(1 for item in _open_turns(dialogue, node_id) if item.get("kind") == "probe")


def _probes_left(dialogue: list[dict], node_id: str) -> bool:
    """Asking is free, but not unlimited: past the cap the character pushes."""
    return _probes_used(dialogue, node_id) < MAX_PROBES


def _with_rounds(interpretation: str, rounds: int, held: bool, asked: int = 0) -> str:
    """Keep what the learner actually did, since that is the thing being trained.

    Whether they asked anything before deciding is the clarify_context skill in
    one number, so it belongs in the record next to how long they lasted.
    """
    tail = "held the line" if held else "gave way"
    detail = f"after {rounds} rounds of pressure, {tail}" if rounds > 1 else tail
    if asked:
        detail = f"asked {asked} question{'s' if asked > 1 else ''} first, {detail}"
    elif not held:
        detail = f"decided without asking anything, {detail}"
    return f"{interpretation} ({detail})"


def _attempt_response(engine, attempt: dict, **overrides) -> dict:
    values = dict(attempt)
    values.update(overrides)
    dialogue = overrides.get("dialogue", [])
    return {
        "attempt_id": values["id"],
        "scenario_id": values["scenario_id"],
        "scenario_version": values["scenario_version"],
        "mode": values["mode"],
        "status": values["status"],
        "revision": values["revision"],
        "assisted": bool(values["assisted"]),
        "node": _node_view(engine, values["scenario_id"], values["current_node_id"]),
        "feedback": overrides.get("feedback"),
        "effect": overrides.get("effect", "none"),
        "learning_updates": overrides.get("learning_updates", []),
        "is_complete": values["status"] == "completed",
        "feedback_mode": overrides.get("feedback_mode", "scripted"),
        "assessment_status": overrides.get("assessment_status", "not_requested"),
        "dialogue": dialogue,
        "pressure": _pressure_view(
            engine, values["scenario_id"], values["current_node_id"], dialogue
        ),
        "timing": {
            "active_seconds": values.get("active_seconds", 0),
            "model_wait_seconds": values.get("model_wait_seconds", 0),
        },
    }


@router.post("/session", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED, operation_id="createSession")
def create_session(body: CreateSessionRequest, request: Request):
    token, session = request.app.state.store.create_session(body.display_name)
    return CreateSessionResponse(session_token=token, session=SessionView(**session))


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteSession")
def delete_session(request: Request, session: Session) -> Response:
    request.app.state.store.delete_session(session["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/town", response_model=TownResponse, operation_id="getTown")
def get_town(request: Request, session: Session):
    store, engine, _ = _services(request)
    skills, _timing = store.passport(session["id"])
    return engine.town_payload({str(skill["skill_id"]): str(skill["state"]) for skill in skills})


@router.post("/attempts", response_model=AttemptResponse, status_code=status.HTTP_201_CREATED, operation_id="createAttempt")
def create_attempt(body: CreateAttemptRequest, request: Request, session: Session):
    store, engine, _ = _services(request)
    scenario = engine.get_scenario(body.scenario_id)
    if body.mode.value not in scenario["available_modes"]:
        from server.main import ApiError
        raise ApiError(400, "invalid_mode", "This mode is not available for the scenario.")

    start_node_id = engine.start_node_id(body.scenario_id)
    assisted = False
    if body.scenario_id == "ethics-review":
        assisted = True
        skill_id = _weakest_skill(store.passport(session["id"])[0])
        if skill_id:
            for candidate in store.coaching_candidates(session["id"], skill_id):
                source_id = str(candidate["scenario_id"])
                try:
                    source = engine.get_scenario(source_id)
                    source_node = engine.get_node(source_id, str(candidate["node_id"]))
                except Exception:  # stale/removed content is retained but not replayed
                    continue
                if (
                    candidate["scenario_version"] == source["version"]
                    and source_node.get("rubric")
                    and (coach_node_id := engine.coaching_node_for_source(source_id, str(candidate["node_id"])))
                ):
                    start_node_id = coach_node_id
                    break
    elif engine.start_node_selector(body.scenario_id) == "weakest_skill":
        start_node_id = engine.coaching_node_id(body.scenario_id, _weakest_skill(store.passport(session["id"])[0]))

    attempt = store.create_attempt(
        session["id"], body.scenario_id, scenario["version"], body.mode.value, start_node_id,
        assisted=assisted,
    )
    opening = _opening_line(engine, body.scenario_id, start_node_id)
    if opening:
        store.append_dialogue(session["id"], attempt["id"], start_node_id, [("npc", opening, "line")])
    dialogue = store.dialogue(session["id"], attempt["id"])
    return _attempt_response(engine, attempt, dialogue=dialogue)


_STATE_PRIORITY = {"needs_practice": 0, "practiced": 1, "demonstrated": 2}


def _weakest_skill(skills: list[dict]) -> str | None:
    answered = [skill for skill in skills if skill.get("evidence")]
    if not answered:
        return None
    answered.sort(key=lambda skill: _STATE_PRIORITY.get(str(skill.get("state")), 3))
    return str(answered[0]["skill_id"])


@router.get("/attempts/{attempt_id}", response_model=AttemptResponse, operation_id="getAttempt")
def get_attempt(attempt_id: UUID, request: Request, session: Session):
    store, engine, _ = _services(request)
    attempt = store.get_attempt(session["id"], str(attempt_id))
    engine.assert_version(attempt["scenario_id"], attempt["scenario_version"])
    # A refresh mid-conversation has to come back to the same conversation.
    dialogue = store.dialogue(session["id"], str(attempt_id))
    return _attempt_response(engine, attempt, dialogue=dialogue)


@router.post("/attempts/{attempt_id}/respond", response_model=AttemptResponse, operation_id="respondToAttempt")
def respond(attempt_id: UUID, body: AnswerRequest, request: Request, session: Session):
    store, engine, evaluator = _services(request)
    request_payload = body.model_dump(mode="json")
    # A successful identical event is replayed before a content-version check.
    prior_response = store.find_event_response(session["id"], str(body.client_event_id), request_payload)
    if prior_response is not None:
        return prior_response
    attempt = store.get_attempt(session["id"], str(attempt_id))
    if attempt["revision"] != body.expected_revision:
        raise RevisionConflictError("Attempt revision is stale")
    engine.assert_version(attempt["scenario_id"], attempt["scenario_version"])
    node_id = attempt["current_node_id"]
    node = engine.get_node(attempt["scenario_id"], node_id)
    assessment_status = "assessed"
    dialogue_rows: list[tuple[str, str]] = []
    resolve_dialogue = False

    if body.kind == "choice":
        branch = engine.choose(attempt["scenario_id"], node_id, body.choice_id)
        next_node_id, effect = branch.next_node_id, branch.effect
        skill_id, learning_state = branch.skill_id, branch.state
        interpretation, feedback_message = branch.interpretation, branch.feedback
        clause_ids, observed, feedback_mode = branch.policy_clause_ids, body.choice_id, FeedbackMode.SCRIPTED.value
    else:
        rule = node.get("text_rule")
        if not node.get("allow_text") or not rule:
            from server.main import ApiError
            raise ApiError(400, "text_not_allowed", "Free text is not allowed at this node.")
        persona = engine.persona(node["npc_id"])
        pressure_state = None
        history = store.dialogue(session["id"], str(attempt_id), node_id)
        if engine.is_pressure_node(attempt["scenario_id"], node_id):
            open_rounds = _open_turns(history, node_id)
            settled = _has_committed(history, node_id)
            pressure_state = PressureState(
                turn=_decisions(history, node_id) + 1,
                max_turns=engine.max_pressure_turns(attempt["scenario_id"]),
                history=tuple((item["speaker"], item["text"]) for item in open_rounds),
                final_push=settled,
            )
        context = build_context(
            attempt["scenario_id"], attempt["scenario_version"], node_id, node,
            persona=persona, pressure=pressure_state,
        )
        if knowledge.dense_runtime_failure_reason():
            from server.core.rag_runtime import warmup_rag
            request.app.state.rag_status = warmup_rag(bool(request.app.state.require_dense))
            if not request.app.state.rag_status.ready:
                from server.main import ApiError
                raise ApiError(503, "rag_unavailable", "Grounded retrieval is temporarily unavailable.", True)
        budget = int(os.getenv("SKILLTOWN_MODEL_CALL_BUDGET", "40"))
        started = time.monotonic()
        evaluated = evaluator.evaluate(
            rule, body.text, allow_model=store.model_calls(session["id"]) < budget, context=context
        )
        waited = time.monotonic() - started
        if evaluated.mode == "ai":
            store.record_model_call(session["id"])
        store.add_model_wait(session["id"], str(attempt_id), waited)
        observed, feedback_mode = body.text, evaluated.mode

        if not evaluated.assessed:
            next_node_id, effect = node_id, "none"
            skill_id = learning_state = None
            interpretation, feedback_message = evaluated.interpretation, evaluated.feedback
            clause_ids = evaluated.policy_clause_ids
            assessment_status = "deferred"
        elif pressure_state and evaluated.turn_kind == "probe" and _probes_left(history, node_id):
            # They asked instead of deciding. Answer with the authored fact, in
            # the character's mouth, and charge them nothing for asking.
            next_node_id, effect = node_id, "none"
            skill_id = learning_state = None
            interpretation, feedback_message = evaluated.interpretation, None
            clause_ids = evaluated.policy_clause_ids
            answered = [context.disclosure(fact_id) for fact_id in evaluated.asked]
            spoken = " ".join(part for part in answered if part) or (
                persona.deflect if persona else ""
            )
            dialogue_rows = [("learner", body.text, "probe"), ("npc", spoken, "answer")]
        elif (
            pressure_state
            and evaluated.outcome != "pass"
            and not pressure_state.is_last_turn
            and not _has_committed(history, node_id)
        ):
            # Mid-arc: the character presses again. No verdict is revealed and no
            # evidence is written, because the learner has not finished deciding.
            # A settled decision is heard once and pushed once; the ladder is for
            # someone still making their mind up.
            next_node_id, effect = node_id, "none"
            skill_id = learning_state = None
            interpretation, feedback_message = evaluated.interpretation, None
            clause_ids = evaluated.policy_clause_ids
            spoken = evaluated.character_line or _authored_line(context, evaluated.committed)
            said_kind = "commit" if evaluated.committed else "decision"
            dialogue_rows = [("learner", body.text, said_kind), ("npc", spoken, "line")]
        else:
            branch = engine.resolve_text(attempt["scenario_id"], node_id, evaluated.outcome)
            next_node_id, effect = branch.next_node_id, branch.effect
            skill_id, learning_state = branch.skill_id or rule, branch.state
            if evaluated.mode == "ai":
                interpretation = evaluated.interpretation
                # An empty model feedback still owes the learner a debrief.
                feedback_message = evaluated.feedback or branch.feedback
                clause_ids = evaluated.policy_clause_ids or branch.policy_clause_ids
            else:
                interpretation = branch.interpretation or evaluated.interpretation
                feedback_message = branch.feedback or evaluated.feedback
                clause_ids = branch.policy_clause_ids
            if pressure_state and persona:
                # The arc closes in character: they give ground, or they get
                # their way and the consequence takes it from there.
                held = evaluated.outcome == "pass"
                # Giving ground and getting your way are the two endings, and
                # both are authored. A cheap model asked to push in one breath
                # and concede in the next will keep selling through the
                # concession, which reads as if the verdict did not land.
                spoken = persona.concede if held else persona.closing
                dialogue_rows = [("learner", body.text, "decision"), ("npc", spoken, "line")]
                resolve_dialogue = True
                interpretation = _with_rounds(
                    interpretation, pressure_state.turn, held,
                    asked=_probes_used(history, node_id),
                )

    def build_response(old_attempt, revision, new_status, evidence_id, resolved_state, dialogue):
        current = dict(old_attempt)
        current.update(current_node_id=next_node_id, revision=revision, status=new_status)
        updates = []
        if evidence_id and skill_id and resolved_state:
            updates.append({"skill_id": skill_id, "state": resolved_state, "evidence_id": evidence_id, "assisted": bool(old_attempt["assisted"])})
        feedback = {
            "title": "Learning feedback", "message": feedback_message, "mode": feedback_mode,
            "policy_clauses": get_policy_cards(clause_ids),
        } if feedback_message else None
        return _attempt_response(
            engine, current, feedback=feedback, effect=effect, learning_updates=updates,
            feedback_mode=feedback_mode, assessment_status=assessment_status, dialogue=dialogue,
        )

    return store.apply_transition(
        session_id=session["id"], attempt_id=str(attempt_id), client_event_id=str(body.client_event_id),
        expected_revision=body.expected_revision, request_payload=request_payload,
        next_node_id=next_node_id, effect=effect, skill_id=skill_id, state=learning_state,
        observed_response=observed, interpretation=interpretation, policy_clause_ids=clause_ids,
        response_builder=build_response,
        dialogue_rows=dialogue_rows, resolve_dialogue=resolve_dialogue,
        arrival_line=_opening_line(engine, attempt["scenario_id"], next_node_id),
    )


@router.post("/attempts/{attempt_id}/hint", response_model=HintResponse, operation_id="requestHint")
def request_hint(attempt_id: UUID, body: MutationRequest, request: Request, session: Session):
    store, engine, _ = _services(request)
    attempt = store.get_attempt(session["id"], str(attempt_id))
    engine.assert_version(attempt["scenario_id"], attempt["scenario_version"])
    node = engine.get_node(attempt["scenario_id"], attempt["current_node_id"])
    hint = node.get("hint")
    card = get_policy_cards([hint["clause_id"]]) if isinstance(hint, dict) else []
    if not hint or not card:
        from server.main import ApiError
        raise ApiError(400, "hint_not_available", "This node has no hint.")
    updated = store.mark_assisted(session["id"], str(attempt_id), body.expected_revision, str(body.client_event_id))
    return {**updated, "hint": hint["text"], "policy_card": card[0]}


@router.post("/attempts/{attempt_id}/rewind", response_model=AttemptResponse, operation_id="rewindAttempt")
def rewind(attempt_id: UUID, body: MutationRequest, request: Request, session: Session):
    store, engine, _ = _services(request)
    attempt = store.get_attempt(session["id"], str(attempt_id))
    engine.assert_version(attempt["scenario_id"], attempt["scenario_version"])
    target = engine.rewind_target(attempt["scenario_id"], attempt["current_node_id"])
    updated = store.rewind(session["id"], str(attempt_id), body.expected_revision, target)
    # Replaying the moment replays the pressure: the old rounds go, and the
    # person says their opening line again.
    store.clear_dialogue(session["id"], str(attempt_id), target)
    opening = _opening_line(engine, attempt["scenario_id"], target)
    if opening:
        store.append_dialogue(session["id"], str(attempt_id), target, [("npc", opening, "line")])
    dialogue = store.dialogue(session["id"], str(attempt_id))
    return _attempt_response(engine, updated, effect="rewind_available", dialogue=dialogue)


@router.post("/attempts/{attempt_id}/activity", status_code=status.HTTP_204_NO_CONTENT, operation_id="recordActivity")
def record_activity(attempt_id: UUID, body: ActivityRequest, request: Request, session: Session) -> Response:
    request.app.state.store.record_activity(session["id"], str(attempt_id), str(body.client_event_id), body.kind)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/passport", response_model=PassportResponse, operation_id="getPassport")
def get_passport(request: Request, session: Session):
    skills, timing = request.app.state.store.passport(session["id"])
    return {"skills": skills, "total_active_seconds": timing["active_seconds"], "total_model_wait_seconds": timing["model_wait_seconds"]}


@router.post("/recommendations", response_model=RecommendationResponse, operation_id="generateRecommendations")
def recommendations(body: RecommendationRequest, request: Request, session: Session):
    skills, _ = request.app.state.store.passport(session["id"])
    return {"generated_at": datetime.now(UTC), "items": recommend(skills, body.max_items)}
