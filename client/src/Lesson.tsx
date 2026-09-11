// The conversation panel: somebody is in the room asking you to bend a rule,
// and you answer them in your own words. There are no options to pick.
//
// Nobody here is teaching. While the pressure is on, the panel shows only what
// the person said - no verdict, no rule, no correct answer. The debrief arrives
// afterwards, in the coach's voice, once the situation has played out.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { verdictKind, type Attempt, type DialogueTurn, type Passport, type PolicyCard, type Recommendation } from "./api";
import { Verdict } from "./Verdict";

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

/** Render the small Markdown subset used by committed policy excerpts.
 *
 * Keeping this local and structural avoids injecting HTML while still making
 * emphasis, numbered tests and threshold tables readable in the lesson.
 */
function inlinePolicy(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={index}>{part.slice(2, -2)}</strong>
      : part,
  );
}

function tableCells(line: string): string[] {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
}

function PolicyExcerpt({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("|")) {
      const tableLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      const rows = tableLines.map(tableCells);
      const hasDivider = rows[1]?.every((cell) => /^:?-{3,}:?$/.test(cell));
      const body = rows.slice(hasDivider ? 2 : 1);
      blocks.push(
        <div className="policy-table-wrap" key={`table-${index}`}>
          <table>
            <thead><tr>{rows[0].map((cell, cellIndex) => <th key={cellIndex}>{inlinePolicy(cell)}</th>)}</tr></thead>
            <tbody>{body.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{inlinePolicy(cell)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>,
      );
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.*)$/);
    if (ordered) {
      const items: string[] = [];
      while (index < lines.length) {
        const match = lines[index].trim().match(/^\d+\.\s+(.*)$/);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }
      blocks.push(<ol key={`list-${index}`}>{items.map((item, itemIndex) => <li key={itemIndex}>{inlinePolicy(item)}</li>)}</ol>);
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const next = lines[index].trim();
      if (!next || next.startsWith("|") || /^\d+\.\s+/.test(next)) break;
      paragraph.push(next);
      index += 1;
    }
    blocks.push(<p key={`paragraph-${index}`}>{inlinePolicy(paragraph.join(" "))}</p>);
  }

  return <div className="policy-body">{blocks}</div>;
}

function PolicyReference({ card, collapsible = false }: { card: PolicyCard; collapsible?: boolean }) {
  const heading = (
    <span className="policy-heading">
      <strong>{card.title}</strong>
      <small>{cardLabel(card)}</small>
    </span>
  );
  if (collapsible) {
    return (
      <details className="policy" key={card.clause_id}>
        <summary>{heading}</summary>
        <PolicyExcerpt text={card.text} />
      </details>
    );
  }
  return (
    <article className="policy" key={card.clause_id}>
      {heading}
      <PolicyExcerpt text={card.text} />
    </article>
  );
}

const MODE_LABELS: Record<string, string> = {
  scripted: "scripted feedback",
  ai: "live AI feedback",
  fallback: "model unavailable — scripted feedback",
};

/** The conversation to show: stored rounds, or the opening line on arrival. */
function transcript(attempt: Attempt | null): DialogueTurn[] {
  if (!attempt) return [];
  if (attempt.dialogue.length > 0) return attempt.dialogue;
  const line = attempt.node?.line;
  if (!line || !attempt.node) return [];
  return [{ node_id: attempt.node.id, speaker: "npc", text: line, kind: "line", resolved: false }];
}

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
  const transcriptEnd = useRef<HTMLDivElement>(null);
  const lastAttempt = useRef<string | null>(null);
  const lastRevision = useRef<number | null>(null);

  const node = attempt?.node ?? null;
  const canAnswer = Boolean(node?.allow_text) && !attempt?.is_complete && !busy;
  const beats = node?.consequence ?? [];
  const [revealed, setRevealed] = useState(1);
  const moreToCome = revealed < beats.length;
  const said = transcript(attempt);
  const atRest = verdictKind(attempt) !== null;
  const pressure = attempt?.pressure ?? null;
  const underPressure = Boolean(pressure?.active) && (pressure?.turn ?? 0) > 0;
  const debrief = attempt?.feedback ?? null;

  useEffect(() => {
    if (canAnswer) input.current?.focus();
  }, [canAnswer, node?.id]);

  // Each situation tells its own story from the first beat.
  useEffect(() => {
    setRevealed(1);
  }, [node?.id]);

  // A new round should be the thing you are looking at, not something above.
  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "end" });
  }, [said.length]);

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
    <section className="lesson" aria-label="Conversation">
      <header className="lesson-head">
        <div>
          <h2>{props.teacher}</h2>
          <p className="lesson-sub">{props.teacherTitle}</p>
        </div>
        <div className="head-right">
          {underPressure && pressure && (
            <span
              className="rounds"
              aria-label={`Round ${pressure.turn} of ${pressure.max_turns}`}
            >
              Round {pressure.turn}/{pressure.max_turns}
              <span className="pips" aria-hidden="true">
                {Array.from({ length: pressure.max_turns }, (_, index) => (
                  <span key={index} className={index < pressure.turn ? "pip spent" : "pip"} />
                ))}
              </span>
            </span>
          )}
          {/* Leaving early; carrying on after a finished situation is the
              button down in the answer area, so the two never compete. */}
          <button className="ghost" onClick={props.onClose}>
            Close
          </button>
        </div>
      </header>

      <div className="lesson-reader" aria-label="The situation so far">
      {props.taskTitle && <p className="lesson-task">Situation: {props.taskTitle}</p>}

      {beats.length > 0 ? (
        <div className="aftermath" aria-label="What happened next">
          <p className="aftermath-head">What happened next</p>
          {beats.slice(0, revealed).map((beat, index) => (
            <p key={index} className="beat">
              <span className="beat-when">{beat.when}</span>
              {beat.text}
            </p>
          ))}
          {moreToCome && (
            <button className="ghost beat-more" onClick={() => setRevealed((n) => n + 1)}>
              Then what?
            </button>
          )}
          {!moreToCome && node?.text && <p className="beat-close">{node.text}</p>}
        </div>
      ) : (
        node?.text && <p className="brief">{node.text}</p>
      )}

      <div className="talk" aria-label="What has been said">
        {said.map((turn, index) => (
          <p
            key={`${turn.node_id}-${index}`}
            className={`bubble ${turn.speaker === "npc" ? "them" : "you"}`}
          >
            <span className="who">{turn.speaker === "npc" ? props.teacher : "You"}</span>
            {turn.text}
          </p>
        ))}
        <div ref={transcriptEnd} />
      </div>

      {/* The rules are yours to consult under pressure, exactly as at a desk.
          Closed by default so the situation, not the answer key, is in front. */}
      {node?.policy_cards && node.policy_cards.length > 0 && (
        <details className="rules" open={Boolean(debrief)}>
          <summary>Check the rules ({node.policy_cards.length})</summary>
          {node.policy_cards.map((card) => (
            <PolicyReference key={card.clause_id} card={card} collapsible />
          ))}
        </details>
      )}

      {debrief && (
        <div className={`feedback feedback-${debrief.mode}`}>
          <p className="feedback-head">
            {debrief.title}
            <span className="feedback-mode">{MODE_LABELS[debrief.mode] ?? debrief.mode}</span>
          </p>
          <p>{debrief.message}</p>
          {debrief.policy_clauses.map((card) => (
            <PolicyReference key={card.clause_id} card={card} />
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

      </div>

      <div className="lesson-actions">
      {atRest && attempt ? (
        <Verdict
          attempt={attempt}
          teacher={props.teacher}
          busy={busy}
          onRewind={props.onRewind}
          onClose={props.onClose}
        />
      ) : (
      <div className="answer">
        <label htmlFor="answer-box">
          {canAnswer
            ? underPressure
              ? `What do you say back to ${props.teacher}?`
              : "What do you say, in your own words?"
            : attempt?.is_complete
              ? "This situation is over"
              : "Nothing to say here"}
          {canAnswer && pressure && (
            // Asking is the skill being trained here, so say it is allowed.
            <span className="hint-inline"> — you can ask questions before you decide</span>
          )}
        </label>
        <textarea
          id="answer-box"
          ref={input}
          value={draft}
          disabled={!canAnswer}
          placeholder="Say it the way you would actually say it, then press Enter"
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
      )}
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
