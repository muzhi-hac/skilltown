// Typed client for the SkillTown learning API.
//
// Same origin in production (FastAPI serves this build), proxied to :8000 in
// dev. The server owns every learning decision; this file only carries data.

export type Category = "ethics_compliance" | "personal_development";
export type FeedbackMode = "scripted" | "ai" | "fallback";
export type Effect = "none" | "consequence_preview" | "rewind_available" | "completed";
export type LearningState = "unseen" | "needs_practice" | "practiced" | "demonstrated";

export interface PolicyCard {
  clause_id: string;
  title: string;
  text: string;
  /** False for passages quoted from the real EU corpus. */
  fictional: boolean;
  /** Which document the passage came from, when it is a real source. */
  source?: string;
}

export interface ScenarioNode {
  id: string;
  npc_id: string;
  category: Category;
  /** The situation, written down. Context, not something anybody says. */
  text: string;
  /** What the person in the room opens with. Empty where nobody is pressing. */
  line: string;
  choices: { id: string; label: string }[];
  allow_text: boolean;
  /** Authored sentence a resting situation states; empty while still deciding. */
  verdict_line: string;
  policy_cards: PolicyCard[];
  /** Only on a consequence node: what follows, one beat at a time. */
  consequence: { when: string; text: string }[];
}

export interface DialogueTurn {
  node_id: string;
  speaker: "npc" | "learner";
  text: string;
  /** A question ("probe") costs no round of pressure; a decision does. */
  kind: "line" | "probe" | "answer" | "decision" | "commit" | "overgeneralized";
  /** True once the arc that contained this round has been settled. */
  resolved: boolean;
}

export interface Pressure {
  /** Rounds already spent against the person still in the room. */
  turn: number;
  max_turns: number;
  active: boolean;
}

export interface Feedback {
  title: string;
  message: string;
  mode: FeedbackMode;
  policy_clauses: PolicyCard[];
}

export interface LearningUpdate {
  skill_id: string;
  state: LearningState;
  evidence_id: string;
  assisted: boolean;
}

export interface Attempt {
  attempt_id: string;
  scenario_id: string;
  scenario_version: string;
  mode: string;
  status: string;
  revision: number;
  assisted: boolean;
  node: ScenarioNode | null;
  feedback: Feedback | null;
  effect: Effect;
  learning_updates: LearningUpdate[];
  is_complete: boolean;
  feedback_mode: FeedbackMode;
  assessment_status: "assessed" | "deferred" | "not_requested";
  dialogue: DialogueTurn[];
  pressure: Pressure | null;
  timing: { active_seconds: number; model_wait_seconds: number };
}

export interface TaskSummary {
  scenario_id: string;
  title: string;
  category: Category;
  estimated_minutes: number;
  available_modes: string[];
}

export interface TownNpc {
  id: string;
  name: string;
  title: string;
  category: Category;
  position: { x: number; y: number };
  tasks: TaskSummary[];
  recommendation_state: "none" | "recommended" | "review";
}

export interface Town {
  categories: { id: Category; label: string; icon: string }[];
  npcs: TownNpc[];
}

export interface Evidence {
  id: string;
  skill_id: string;
  scenario_id: string;
  node_id: string;
  observed_response: string;
  interpretation: string | null;
  policy_clause_ids: string[];
  assisted: boolean;
  created_at: string;
}

export interface Passport {
  skills: { skill_id: string; label: string; state: LearningState; evidence: Evidence[] }[];
  total_active_seconds: number;
  total_model_wait_seconds: number;
}

export interface Recommendation {
  id: string;
  scenario_id: string;
  npc_id: string;
  skill_id: string;
  reason: string;
  evidence_ids: string[];
}

/** Where a situation has come to rest, if it has: the two moments that get a card. */
export function verdictKind(attempt: Attempt | null): "consequence" | "completed" | null {
  if (!attempt) return null;
  if (attempt.effect === "consequence_preview") return "consequence";
  return attempt.is_complete ? "completed" : null;
}

export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;

  constructor(code: string, message: string, status: number, retryable: boolean) {
    super(message);
    this.code = code;
    this.status = status;
    this.retryable = retryable;
  }
}

const TOKEN_KEY = "skilltown.session";
const PREFIX = "/api/v1";

let token = "";
try {
  token = localStorage.getItem(TOKEN_KEY) ?? "";
} catch {
  // Private windows can refuse storage; a session that lives only in memory
  // still works for one sitting.
}

function remember(value: string): void {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function hasSession(): boolean {
  return token !== "";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(PREFIX + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload?.error ?? {};
    throw new ApiError(
      detail.code ?? `http_${response.status}`,
      detail.message ?? "The request failed.",
      response.status,
      Boolean(detail.retryable),
    );
  }
  return payload as T;
}

const uuid = (): string =>
  crypto.randomUUID?.() ??
  `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;

export async function createSession(displayName = "Demo learner"): Promise<void> {
  const result = await request<{ session_token: string }>("POST", "/session", {
    display_name: displayName,
  });
  remember(result.session_token);
}

export async function deleteSession(): Promise<void> {
  await request<void>("DELETE", "/session");
  remember("");
}

export const getTown = (): Promise<Town> => request<Town>("GET", "/town");

export const startAttempt = (scenarioId: string, mode: string): Promise<Attempt> =>
  request<Attempt>("POST", "/attempts", { scenario_id: scenarioId, mode });

export const getAttempt = (attemptId: string): Promise<Attempt> =>
  request<Attempt>("GET", `/attempts/${attemptId}`);

// Answers are always the learner's own words; there are no choices to send.
export const answer = (attemptId: string, revision: number, text: string): Promise<Attempt> =>
  request<Attempt>("POST", `/attempts/${attemptId}/respond`, {
    client_event_id: uuid(),
    expected_revision: revision,
    kind: "text",
    text,
  });

export const requestHint = (
  attemptId: string,
  revision: number,
): Promise<{ revision: number; hint: string; policy_card: PolicyCard }> =>
  request("POST", `/attempts/${attemptId}/hint`, {
    client_event_id: uuid(),
    expected_revision: revision,
  });

export const rewind = (attemptId: string, revision: number): Promise<Attempt> =>
  request<Attempt>("POST", `/attempts/${attemptId}/rewind`, {
    client_event_id: uuid(),
    expected_revision: revision,
  });

export const recordActivity = (attemptId: string, kind: string): Promise<void> =>
  request<void>("POST", `/attempts/${attemptId}/activity`, {
    client_event_id: uuid(),
    kind,
  }).catch(() => undefined);

export const getPassport = (): Promise<Passport> => request<Passport>("GET", "/passport");

export const getRecommendations = (maxItems = 3): Promise<{ items: Recommendation[] }> =>
  request("POST", "/recommendations", { max_items: maxItems });

export async function ensureSession(): Promise<void> {
  if (!hasSession()) {
    await createSession();
    return;
  }
  try {
    await getTown();
  } catch (error) {
    // A stale token from a previous deployment should not strand the learner.
    if (error instanceof ApiError && error.status === 401) {
      remember("");
      await createSession();
      return;
    }
    throw error;
  }
}
