# Three-minute grounded-RAG demo script

Live URL: https://skilltown.fly.dev

Use a fresh browser profile so the three-question starting check appears. The
screen always shows the source cards that bound the current answer; do not claim
that the training corpus replaces local legal or compliance advice.

---

## 0:00 — The claim

> "Nobody in this town teaches you. The people who knock want you to bend a
rule, and they do not give up after one answer. Every line they say and every
verdict behind it is anchored to a visible source passage, and the record keeps
what I actually wrote, not a guessed learner profile."

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

## 1:00 — Someone pushes back, four rounds deep

Open Alex's **Gifts and hospitality** situation. He speaks first: the head of
unit left €26 of chocolates for you. Open **Check the rules** once to show the
ANNEX cards are one click away, exactly as they would be at a real desk.

Type the weak answer: **“€26 is a small gift, so I will accept it.”**

Point at what does *not* happen: no red cross, no correct answer, no evidence
line. The header now reads **Round 1 of 4** and Alex simply pushes again -
first as ordinary courtesy, then sweetening the offer, then making it personal,
then asking you to keep it off the books. Keep giving way and the arc ends in
the consequence preview; hold the line at any round and he backs off in
character and the situation moves on.

> "Pressure is the thing being trained. A verdict after one answer teaches you
the rule; four rounds of someone you like asking again teaches you what you
actually do. The grading half of that same model call is unchanged: it may cite
only this node's passages, it must quote my own words to pass me, and the server
rechecks both. The line he speaks is dropped if it names a rule or a clause id."

## 1:50 — Evidence-driven review

Close Alex and Sam, let Nina and Jo through, then wait for Mira - the only
visitor who is not pressing you for anything. Open her **Review a case from your
record**.

> "Mira selected a static, version-matched copy of a case I actually answered.
Old scenario versions remain in the record but are not mapped onto new wording."

Open **My progress** to show the learner's own evidence sentence and the skill
state, including how many rounds of pressure it took and whether they held the
line or gave way. Close Progress to return to the conversation, not a broken
room state.

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
