"""FastAPI routes for the first end-to-end learning slice."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response, status

from server.api.models import (
    ActivityRequest,
    AnswerRequest,
    AttemptResponse,
    CreateAttemptRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    FeedbackMode,
    HintResponse,
    MutationRequest,
    PassportResponse,
    RecommendationRequest,
    RecommendationResponse,
    SessionView,
    TownResponse,
)
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
        "choices": node.get("choices", []),
        "allow_text": node.get("allow_text", False),
        "policy_cards": [],
    }


def _attempt_response(engine, attempt: dict, **overrides) -> dict:
    values = dict(attempt)
    values.update(overrides)
    node_id = values["current_node_id"]
    return {
        "attempt_id": values["id"],
        "scenario_id": values["scenario_id"],
        "scenario_version": values["scenario_version"],
        "mode": values["mode"],
        "status": values["status"],
        "revision": values["revision"],
        "assisted": bool(values["assisted"]),
        "node": _node_view(engine, values["scenario_id"], node_id),
        "feedback": overrides.get("feedback"),
        "effect": overrides.get("effect", "none"),
        "learning_updates": overrides.get("learning_updates", []),
        "is_complete": values["status"] == "completed",
        "feedback_mode": overrides.get("feedback_mode", "scripted"),
        "timing": {
            "active_seconds": values.get("active_seconds", 0),
            "model_wait_seconds": values.get("model_wait_seconds", 0),
        },
    }


@router.post(
    "/session", response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED, operation_id="createSession"
)
def create_session(body: CreateSessionRequest, request: Request):
    store: Store = request.app.state.store
    token, session = store.create_session(body.display_name)
    return CreateSessionResponse(session_token=token, session=SessionView(**session))


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteSession")
def delete_session(request: Request, session: Session) -> Response:
    request.app.state.store.delete_session(session["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/town", response_model=TownResponse, operation_id="getTown")
def get_town(request: Request, session: Session):
    store, engine, _ = _services(request)
    skills, _timing = store.passport(session["id"])
    states = {str(skill["skill_id"]): str(skill["state"]) for skill in skills}
    return engine.town_payload(states)


@router.post(
    "/attempts", response_model=AttemptResponse,
    status_code=status.HTTP_201_CREATED, operation_id="createAttempt"
)
def create_attempt(body: CreateAttemptRequest, request: Request, session: Session):
    store, engine, _ = _services(request)
    scenario = engine.get_scenario(body.scenario_id)
    if body.mode.value not in scenario["available_modes"]:
        from server.main import ApiError

        raise ApiError(400, "invalid_mode", "This mode is not available for the scenario.")
    start_node_id = engine.start_node_id(body.scenario_id)
    if engine.start_node_selector(body.scenario_id) == "weakest_skill":
        skills, _ = store.passport(session["id"])
        start_node_id = engine.coaching_node_id(body.scenario_id, _weakest_skill(skills))
    attempt = store.create_attempt(
        session["id"], body.scenario_id, scenario["version"], body.mode.value,
        start_node_id,
    )
    return _attempt_response(engine, attempt)


# Coaching targets the weakest skill the learner has actually answered on. Skills with
# no evidence are not gaps: they are unverified, and inventing a gap for them would be
# a fake memory.
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
    return _attempt_response(engine, attempt)


@router.post(
    "/attempts/{attempt_id}/respond", response_model=AttemptResponse,
    operation_id="respondToAttempt"
)
def respond(
    attempt_id: UUID, body: AnswerRequest, request: Request, session: Session
):
    store, engine, evaluator = _services(request)
    request_payload = body.model_dump(mode="json")
    prior_response = store.find_event_response(
        session["id"], str(body.client_event_id), request_payload
    )
    if prior_response is not None:
        return prior_response
    attempt = store.get_attempt(session["id"], str(attempt_id))
    # Revision is checked before scenario validation so a duplicated click on a stale
    # revision resyncs the client (409) instead of looking like an invalid choice (400).
    if attempt["revision"] != body.expected_revision:
        raise RevisionConflictError("Attempt revision is stale")
    node_id = attempt["current_node_id"]
    node = engine.get_node(attempt["scenario_id"], node_id)

    if body.kind == "choice":
        branch = engine.choose(attempt["scenario_id"], node_id, body.choice_id)
        next_node_id = branch.next_node_id
        effect = branch.effect
        skill_id = branch.skill_id
        learning_state = branch.state
        interpretation = branch.interpretation
        feedback_message = branch.feedback
        clause_ids = branch.policy_clause_ids
        observed = body.choice_id
        feedback_mode = FeedbackMode.SCRIPTED.value
    else:
        rule = node.get("text_rule")
        if not node.get("allow_text") or not rule:
            from server.main import ApiError

            raise ApiError(400, "text_not_allowed", "Free text is not allowed at this node.")
        # A publicly shared demo needs a spend ceiling; over budget the answer is
        # still evaluated, just deterministically and labelled as fallback.
        budget = int(os.getenv("SKILLTOWN_MODEL_CALL_BUDGET", "40"))
        started = time.monotonic()
        evaluated = evaluator.evaluate(
            rule, body.text, allow_model=store.model_calls(session["id"]) < budget
        )
        waited = time.monotonic() - started
        if evaluated.mode == "ai":
            store.record_model_call(session["id"])
        store.add_model_wait(session["id"], str(attempt_id), waited)
        next_node_id = node["text_pass_node"] if evaluated.passed else node_id
        effect = "completed" if evaluated.passed and next_node_id.endswith("_complete") else "none"
        skill_id = rule
        learning_state = "pass" if evaluated.passed else "needs_practice"
        interpretation = evaluated.interpretation
        feedback_message = evaluated.feedback
        clause_ids = evaluated.policy_clause_ids
        observed = body.text
        feedback_mode = evaluated.mode

    def build_response(old_attempt, revision, new_status, evidence_id, resolved_state):
        current = dict(old_attempt)
        current.update(
            current_node_id=next_node_id,
            revision=revision,
            status=new_status,
        )
        updates = []
        if evidence_id and skill_id and resolved_state:
            updates.append(
                {
                    "skill_id": skill_id,
                    "state": resolved_state,
                    "evidence_id": evidence_id,
                    "assisted": bool(old_attempt["assisted"]),
                }
            )
        feedback = (
            {
                "title": "Learning feedback",
                "message": feedback_message,
                "mode": feedback_mode,
                "policy_clauses": get_policy_cards(clause_ids),
            }
            if feedback_message
            else None
        )
        return _attempt_response(
            engine,
            current,
            feedback=feedback,
            effect=effect,
            learning_updates=updates,
            feedback_mode=feedback_mode,
        )

    return store.apply_transition(
        session_id=session["id"],
        attempt_id=str(attempt_id),
        client_event_id=str(body.client_event_id),
        expected_revision=body.expected_revision,
        request_payload=request_payload,
        next_node_id=next_node_id,
        effect=effect,
        skill_id=skill_id,
        state=learning_state,
        observed_response=observed,
        interpretation=interpretation,
        policy_clause_ids=clause_ids,
        response_builder=build_response,
    )


@router.post("/attempts/{attempt_id}/hint", response_model=HintResponse, operation_id="requestHint")
def request_hint(
    attempt_id: UUID, body: MutationRequest, request: Request, session: Session
):
    store, engine, _ = _services(request)
    attempt = store.get_attempt(session["id"], str(attempt_id))
    node = engine.get_node(attempt["scenario_id"], attempt["current_node_id"])
    rule = node.get("text_rule", "clarify_context")
    clause_id = {
        "clarify_context": "ETH-03",
        "conflict_awareness": "ETH-01",
        "communicate_boundary": "DEV-01",
    }[rule]
    updated = store.mark_assisted(
        session["id"], str(attempt_id), body.expected_revision, str(body.client_event_id)
    )
    return {
        **updated,
        "hint": "First identify the facts still missing, the relationship to the business decision, and an appropriate next step.",
        "policy_card": get_policy_cards([clause_id])[0],
    }


@router.post(
    "/attempts/{attempt_id}/rewind", response_model=AttemptResponse,
    operation_id="rewindAttempt"
)
def rewind(attempt_id: UUID, body: MutationRequest, request: Request, session: Session):
    store, engine, _ = _services(request)
    attempt = store.get_attempt(session["id"], str(attempt_id))
    # The current node must declare a rewind target; the learner then returns to the
    # decision point they actually answered from, not to the start of the scenario.
    target = engine.rewind_target(attempt["scenario_id"], attempt["current_node_id"])
    answered = store.last_answered_node(session["id"], str(attempt_id))
    if answered and engine.has_node(attempt["scenario_id"], answered):
        target = answered
    updated = store.rewind(session["id"], str(attempt_id), body.expected_revision, target)
    return _attempt_response(engine, updated, effect="rewind_available")


@router.post(
    "/attempts/{attempt_id}/activity", status_code=status.HTTP_204_NO_CONTENT,
    operation_id="recordActivity"
)
def record_activity(
    attempt_id: UUID, body: ActivityRequest, request: Request, session: Session
) -> Response:
    request.app.state.store.record_activity(
        session["id"], str(attempt_id), str(body.client_event_id), body.kind
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/passport", response_model=PassportResponse, operation_id="getPassport")
def get_passport(request: Request, session: Session):
    skills, timing = request.app.state.store.passport(session["id"])
    return {
        "skills": skills,
        "total_active_seconds": timing["active_seconds"],
        "total_model_wait_seconds": timing["model_wait_seconds"],
    }


@router.post(
    "/recommendations", response_model=RecommendationResponse,
    operation_id="generateRecommendations"
)
def recommendations(body: RecommendationRequest, request: Request, session: Session):
    skills, _ = request.app.state.store.passport(session["id"])
    return {
        "generated_at": datetime.now(UTC),
        "items": recommend(skills, body.max_items),
    }
