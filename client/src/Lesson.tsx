// The lesson panel: read the situation, write your own answer, read what the
// server made of it. There are no options to pick.

import { useEffect, useRef, useState } from "react";
import type { Attempt, Passport, PolicyCard, Recommendation } from "./api";

const SKILL_LABELS: Record<string, string> = {
  clarify_context: "Gather relevant facts",
  conflict_awareness: "Recognize risks and applicable conditions",
  communicate_boundary: "Explain the decision and next step",
};

const STATE_LABELS: Record<string, string> = {
  unseen: "Not yet verified",
  needs_practice: "Practice suggested",
  practiced: "Practiced",
  demonstrated: "Passed independently",
};

/** A card either quotes a real source or is a training-only stand-in; say which. */
function cardLabel(card: PolicyCard): string {
  if (card.fictional) return `Training policy (fictional) ${card.clause_id}`;
  return card.source ? `${card.source} · ${card.clause_id}` : `Reference ${card.clause_id}`;
}

const MODE_LABELS: Record<string, string> = {
  scripted: "scripted feedback",
  ai: "live AI feedback",
  fallback: "model unavailable — scripted feedback",
};

export interface LessonProps {
  teacher: string;
  teacherTitle: string;
  taskTitle: string;
  attempt: Attempt | null;
  busy: boolean;
  status: string;
  onAnswer: (text: string) => void;
  onHint: () => void;
  onRewind: () => void;
  onClose: () => void;
  versionMismatch?: boolean;
  onStartUpdated?: () => void;
}

export function Lesson(props: LessonProps) {
  const { attempt, busy } = props;
  const [draft, setDraft] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const lastAttempt = useRef<string | null>(null);
  const lastRevision = useRef<number | null>(null);

  const node = attempt?.node ?? null;
  const canAnswer = Boolean(node?.allow_text) && !attempt?.is_complete && !busy;

  useEffect(() => {
    if (canAnswer) input.current?.focus();
  }, [canAnswer, node?.id]);

  useEffect(() => {
    if (!attempt) return;
    const changedAttempt = lastAttempt.current !== null && lastAttempt.current !== attempt.attempt_id;
    const assessedReply = lastRevision.current !== null && lastRevision.current !== attempt.revision
      && attempt.assessment_status === "assessed";
    if (changedAttempt || assessedReply || attempt.is_complete) setDraft("");
    lastAttempt.current = attempt.attempt_id;
    lastRevision.current = attempt.revision;
  }, [attempt?.attempt_id, attempt?.revision, attempt?.assessment_status, attempt?.is_complete]);

  function submit() {
    const text = draft.trim();
    if (!text || !canAnswer) return;
    props.onAnswer(text);
  }

  return (
    <section className="lesson" aria-label="Lesson">
      <header className="lesson-head">
        <div>
          <h2>{props.teacher}</h2>
          <p className="lesson-sub">{props.teacherTitle}</p>
        </div>
        <button className="ghost" onClick={props.onClose}>
          Close
        </button>
      </header>

      {props.taskTitle && <p className="lesson-task">Mission: {props.taskTitle}</p>}

      {node && <p className="lesson-say">{node.text}</p>}

      {node?.policy_cards?.map((card) => (
        <p key={card.clause_id} className="policy">
          <strong>{cardLabel(card)}</strong> · {card.title}: {card.text}
        </p>
      ))}

      {attempt?.feedback && (
        <div className={`feedback feedback-${attempt.feedback.mode}`}>
          <p className="feedback-head">
            {attempt.feedback.title}
            <span className="feedback-mode">
              {MODE_LABELS[attempt.feedback.mode] ?? attempt.feedback.mode}
            </span>
          </p>
          <p>{attempt.feedback.message}</p>
          {attempt.feedback.policy_clauses.map((card) => (
            <p key={card.clause_id} className="policy">
              <strong>{cardLabel(card)}</strong> · {card.title}: {card.text}
            </p>
          ))}
        </div>
      )}

      {attempt?.learning_updates?.map((update) => (
        <p key={update.evidence_id} className="evidence">
          Evidence recorded: {SKILL_LABELS[update.skill_id] ?? update.skill_id} →{" "}
          {STATE_LABELS[update.state] ?? update.state}
          {update.assisted ? " (after a hint, so it does not count as independent)" : ""}
        </p>
      ))}

      {attempt?.effect === "consequence_preview" && (
        <p className="consequence">
          This is a teaching simulation of what could follow, not a real sanction. You can rewind
          to the decision point and answer again.
        </p>
      )}

      <div className="answer">
        <label htmlFor="answer-box">
          {canAnswer
            ? "Your answer, in your own words"
            : attempt?.is_complete
              ? "This task is complete"
              : "Nothing to answer here"}
        </label>
        <textarea
          id="answer-box"
          ref={input}
          value={draft}
          disabled={!canAnswer}
          placeholder="Type what you would actually say or do, then press Enter"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          rows={3}
        />
        <div className="answer-row">
          <button className="primary" disabled={!canAnswer || !draft.trim()} onClick={submit}>
            {busy ? "Sending…" : "Send answer"}
          </button>
          <button className="ghost" disabled={busy || !attempt || attempt.is_complete || !node?.allow_text} onClick={props.onHint}>
            Hint
          </button>
          <button
            className="ghost"
            disabled={busy || attempt?.effect !== "consequence_preview"}
            onClick={props.onRewind}
          >
            Rewind to the decision
          </button>
          {props.versionMismatch && props.onStartUpdated ? (
            <button className="ghost" disabled={busy} onClick={props.onStartUpdated}>Start updated task</button>
          ) : null}
          <span className="status">{props.status}</span>
        </div>
      </div>
    </section>
  );
}

export interface ProgressProps {
  passport: Passport | null;
  plan: Recommendation[];
  npcNameById: (id: string) => string;
  taskTitleById: (id: string) => string;
  onStart: (scenarioId: string) => void;
  onClose: () => void;
}

export function Progress(props: ProgressProps) {
  const { passport, plan } = props;
  return (
    <section className="lesson" aria-label="My progress">
      <header className="lesson-head">
        <div>
          <h2>My progress</h2>
          <p className="lesson-sub">What you have shown, and the answers behind it</p>
        </div>
        <button className="ghost" onClick={props.onClose}>
          Close
        </button>
      </header>

      {!passport && <p>Loading…</p>}

      {passport?.skills.map((skill) => (
        <div key={skill.skill_id} className="skill">
          <p className="skill-head">
            {skill.label} — <strong>{STATE_LABELS[skill.state] ?? skill.state}</strong>{" "}
            <span className="muted">({skill.evidence.length} answers)</span>
          </p>
          {skill.evidence.slice(-2).map((item) => (
            <p key={item.id} className="quote">
              “{item.observed_response}”
              {item.interpretation ? <span className="muted"> — {item.interpretation}</span> : null}
            </p>
          ))}
        </div>
      ))}

      {passport && (
        <p className="muted">
          Active {passport.total_active_seconds}s · waiting on the model{" "}
          {passport.total_model_wait_seconds}s
        </p>
      )}

      {plan.length > 0 && (
        <div className="plan">
          <h3>What to do next</h3>
          {plan.map((item) => (
            <button key={item.id} className="plan-item" onClick={() => props.onStart(item.scenario_id)}>
              <strong>{props.taskTitleById(item.scenario_id)}</strong> with{" "}
              {props.npcNameById(item.npc_id)}
              <span className="muted"> — {item.reason}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
