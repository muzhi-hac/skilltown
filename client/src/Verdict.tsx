// Where a situation comes to rest: a consequence to look at again, or the end
// of a path. The line under the heading is authored per node and per scenario -
// the same consequence receives opposite mistakes, so nothing here guesses what
// this learner did.

import { verdictKind, type Attempt } from "./api";

export interface VerdictProps {
  attempt: Attempt;
  teacher: string;
  busy: boolean;
  onRewind: () => void;
  onClose: () => void;
}

export function Verdict(props: VerdictProps) {
  const kind = verdictKind(props.attempt);
  if (!kind) return null;
  const atConsequence = kind === "consequence";

  return (
    <section className={`verdict verdict--${kind}`} aria-label="Result" role="status">
      <div className="verdict-body">
        {/* "Completed" is what the path did, not a claim that the learner got it
            all right: independence stays on the skills that earned it. */}
        <h3>{atConsequence ? "This decision needs another look." : "Practice completed."}</h3>
        <p>{props.attempt.node?.verdict_line}</p>
      </div>
      <div className="verdict-actions">
        {atConsequence && (
          <button className="ghost" disabled={props.busy} onClick={props.onRewind}>
            Try it again
          </button>
        )}
        <button className="primary" onClick={props.onClose}>
          Next visitor →
        </button>
      </div>
    </section>
  );
}
