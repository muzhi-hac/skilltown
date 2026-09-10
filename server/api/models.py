"""Pydantic models for the public SkillTown API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LearningCategory(StrEnum):
    ETHICS_COMPLIANCE = "ethics_compliance"
    PERSONAL_DEVELOPMENT = "personal_development"


class NpcId(StrEnum):
    ALEX = "alex"
    SAM = "sam"
    MIRA = "mira"
    JO = "jo"


class SkillId(StrEnum):
    CLARIFY_CONTEXT = "clarify_context"
    CONFLICT_AWARENESS = "conflict_awareness"
    COMMUNICATE_BOUNDARY = "communicate_boundary"


class LearningState(StrEnum):
    UNSEEN = "unseen"
    NEEDS_PRACTICE = "needs_practice"
    PRACTICED = "practiced"
    DEMONSTRATED = "demonstrated"


class AttemptMode(StrEnum):
    SCREENING = "screening"
    PRACTICE = "practice"
    VERIFICATION = "verification"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Effect(StrEnum):
    NONE = "none"
    CONSEQUENCE_PREVIEW = "consequence_preview"
    REWIND_AVAILABLE = "rewind_available"
    COMPLETED = "completed"


class FeedbackMode(StrEnum):
    SCRIPTED = "scripted"
    AI = "ai"
    FALLBACK = "fallback"


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    version: str = "1.0.0"


class CreateSessionRequest(StrictModel):
    display_name: str = Field(min_length=1, max_length=40)


class SessionView(StrictModel):
    id: UUID
    display_name: str
    expires_at: datetime


class CreateSessionResponse(StrictModel):
    session_token: str
    session: SessionView


class CategoryView(StrictModel):
    id: LearningCategory
    label: str
    icon: str


class Position(StrictModel):
    x: float
    y: float


class TaskSummary(StrictModel):
    scenario_id: str
    title: str
    category: LearningCategory
    estimated_minutes: int = Field(ge=1, le=15)
    available_modes: list[AttemptMode]


class TownNpc(StrictModel):
    id: NpcId
    name: str
    title: str
    category: LearningCategory
    position: Position
    tasks: list[TaskSummary]
    recommendation_state: Literal["none", "recommended", "review"] = "none"


class TownResponse(StrictModel):
    categories: list[CategoryView]
    npcs: list[TownNpc]
    # The opening screening is not attached to an NPC, but its id still comes from
    # the server so the client never hard-codes a scenario id.
    screening: TaskSummary | None = None


class Choice(StrictModel):
    id: str
    label: str = Field(max_length=240)


class PolicyCard(StrictModel):
    clause_id: str
    title: str
    text: str
    # True only for training-only stand-ins. Passages quoted from the EU corpus
    # are real references and must not be dressed up as fiction.
    fictional: bool = False
    # Which document a real passage came from; empty for fictional stand-ins.
    source: str = ""


class ScenarioNode(StrictModel):
    id: str
    npc_id: NpcId
    category: LearningCategory
    text: str = Field(max_length=1200)
    choices: list[Choice] = Field(max_length=4)
    allow_text: bool
    policy_cards: list[PolicyCard] = Field(default_factory=list)


class CreateAttemptRequest(StrictModel):
    scenario_id: str
    mode: AttemptMode


class MutationRequest(StrictModel):
    client_event_id: UUID
    expected_revision: int = Field(ge=0)


class ChoiceResponseRequest(MutationRequest):
    kind: Literal["choice"]
    choice_id: str


class TextResponseRequest(MutationRequest):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=1000)


AnswerRequest = Annotated[
    ChoiceResponseRequest | TextResponseRequest,
    Field(discriminator="kind"),
]


class Feedback(StrictModel):
    title: str
    message: str = Field(max_length=1200)
    mode: FeedbackMode
    policy_clauses: list[PolicyCard] = Field(default_factory=list)


class LearningUpdate(StrictModel):
    skill_id: SkillId
    state: LearningState
    evidence_id: UUID
    assisted: bool


class Timing(StrictModel):
    active_seconds: int = Field(ge=0)
    model_wait_seconds: int = Field(ge=0)


class AttemptResponse(StrictModel):
    attempt_id: UUID
    scenario_id: str
    scenario_version: str
    mode: AttemptMode
    status: AttemptStatus
    revision: int = Field(ge=0)
    assisted: bool
    node: ScenarioNode | None
    feedback: Feedback | None = None
    effect: Effect
    learning_updates: list[LearningUpdate] = Field(default_factory=list)
    is_complete: bool
    feedback_mode: FeedbackMode
    timing: Timing


class HintResponse(StrictModel):
    attempt_id: UUID
    revision: int
    assisted: Literal[True] = True
    hint: str
    policy_card: PolicyCard


class ActivityRequest(StrictModel):
    client_event_id: UUID
    kind: Literal["start", "heartbeat", "pause", "resume", "end"]


class EvidenceView(StrictModel):
    id: UUID
    skill_id: SkillId
    scenario_id: str
    node_id: str
    observed_response: str
    interpretation: str | None
    policy_clause_ids: list[str]
    assisted: bool
    created_at: datetime


class SkillPassportEntry(StrictModel):
    skill_id: SkillId
    label: str
    state: LearningState
    evidence: list[EvidenceView]


class PassportResponse(StrictModel):
    skills: list[SkillPassportEntry]
    total_active_seconds: int = Field(ge=0)
    total_model_wait_seconds: int = Field(ge=0)


class RecommendationRequest(StrictModel):
    max_items: int = Field(default=3, ge=1, le=3)


class RecommendationView(StrictModel):
    id: UUID
    scenario_id: str
    npc_id: NpcId
    skill_id: SkillId
    reason: str = Field(max_length=500)
    evidence_ids: list[UUID]


class RecommendationResponse(StrictModel):
    generated_at: datetime
    items: list[RecommendationView] = Field(max_length=3)


class ErrorDetail(StrictModel):
    code: str
    message: str
    request_id: str
    retryable: bool
    latest_attempt_url: str | None = None


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
