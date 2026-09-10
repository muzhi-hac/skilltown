# Three-minute grounded-RAG demo script

Live URL: https://skilltown.fly.dev

Use a fresh browser profile so the three-question starting check appears. The
screen always shows the source cards that bound the current answer; do not claim
that the training corpus replaces local legal or compliance advice.

---

## 0:00 — The claim

> "This is a learning town where every prompt, hint and evaluation is anchored
to a visible source passage. The system keeps evidence of what I actually wrote,
not a guessed learner profile."

Point out `/ready` in the deployment view if available: the image is ready only
after the dense corpus has warmed successfully.

## 0:20 — Three-question starting check

1. Open the door for Mira.
2. For the public-official gift, type: **“I first confirm the public-official
   role, the applicable Germany-specific rule and how €26 compares with its
   threshold.”**
3. For linked cash payments, type the reviewed weak answer: **“Each €3,000
   payment is separate.”** The scenario advances while recording a specific
   practice signal.
4. For the breach reply, type: **“We became aware at 10:00 today and the breach
   is high risk, so I will notify the authority within 72 hours and affected
   people without undue delay; I will document and coordinate the next steps
   now.”**

> "The check is a starting point. It does not claim that someone has mastered a
whole legal domain."

## 1:00 — Source cards, hint, deferred answer and rewind

Open Alex's **Gifts and hospitality** task. Show the visible ANNEX cards and
request a hint; its card has the same source provenance.

Type a novel answer that is not an approved fallback example. The response stays
on the same node with **deferred** assessment and records no learning result.
Then type: **“€26 is a small gift, so I will accept it.”** The reviewed miss
opens a teaching consequence. Rewind, then type the reviewed pass answer shown
in the answer matrix.

> "The deterministic path does not pretend to grade arbitrary wording. A model
verdict must cite only the passages in this node's context, and the server
rechecks it."

## 1:50 — Evidence-driven review

Close Alex and Sam, then wait for Mira. Her task chooser shows both **Privacy
and incident response** and **Review a case from your record**. Choose the
review task.

> "Mira selected a static, version-matched copy of a case I actually answered.
Old scenario versions remain in the record but are not mapped onto new wording."

Open **My progress** to show the learner's own evidence sentence and the skill
state. Close Progress to return to the lesson, not a broken room state.

## 2:30 — Deployment proof

Show the source card, then the release validation report:

- 64 corpus chunks;
- locked dense model revision and checksum verification;
- `/ready` hybrid status;
- 512MB cgroup retrieval peak of 186.2MiB;
- fixed answer matrix and real-browser E2E results.

## Questions to expect

- **"What stops invented citations?"** The evaluator receives only the current
  node's full passages and rejects citations outside those ids.
- **"What happens when wording is not deterministically covered?"** It is
  `deferred`, remains on the same node and changes no learning projection.
- **"What happens if dense retrieval fails after startup?"** Forced-dense mode
  changes readiness to unavailable and serves 503; development mode is marked
  sparse rather than claiming hybrid.
- **"Does a reviewed miss accuse the learner?"** No. It is a retryable training
  event with a visible source and rewind path.
