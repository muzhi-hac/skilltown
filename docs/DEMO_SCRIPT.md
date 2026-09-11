# Three-minute grounded-RAG demo script

Live URL: https://skilltown.fly.dev

Use a fresh browser profile so the record is empty. The screen always shows the
source cards that bound the current answer; do not claim that the training
corpus replaces local legal or compliance advice.

---

## 0:00 — The claim

> "Nobody in this town teaches you. The people who knock want you to bend a
rule, and they do not give up after one answer. Every line they say and every
verdict behind it is anchored to a visible source passage, and the record keeps
what I actually wrote, not a guessed learner profile."

Point out `/ready` in the deployment view if available: the image is ready only
after the dense corpus has warmed successfully.

## 0:20 — Nobody tells you anything

Open the door. Alex says a gift arrived after this morning's meeting and you
should take it. That is all he says: not who sent it, not what it is worth, not
whether anyone wrote it down. The brief on screen withholds the same three
things.

Type a question instead of an answer: **"Who is it actually from?"** He tells
you — the head of unit at the city office, the one who signs off the permits.
Ask again: **"What is it worth?"** Twenty-six euros on the receipt.

Point at the round counter while you do it: still 0 of 4.

> "Asking costs nothing here, and it is the whole first skill. The facts he
gives back are written in the content, not generated - the model only decides
what was asked. A learner who decides without asking gets graded on what they
actually knew, and the record says they never asked."

## 1:00 — Someone pushes back, four rounds deep

Open Alex's **Gifts and hospitality** situation. He speaks first: the head of
unit left €26 of chocolates for you. Open **Check the rules** once to show the
ANNEX cards are one click away, exactly as they would be at a real desk.

Type the weak answer: **“€26 is a small gift, so I will accept it.”**

Point at what does *not* happen: no red cross, no correct answer, no evidence
line. The header now reads **Round 1/2** - he heard a settled answer, so he gets
one more push rather than three - and Alex simply pushes again -
first as ordinary courtesy, then sweetening the offer, then making it personal,
then asking you to keep it off the books. Keep giving way and the arc ends, and this is the part to slow down on: the
panel does not say "wrong". It says **what happened next**, one beat at a time.
Eleven days later an audit pulls the city office's gift register. In March the
permit decision is reopened and the official who signed it is stood down. By
summer you are a named party in a file you never opened. Click **Then what?**
between beats and let the room read them. Only then does Mira debrief, and the
rewind takes you back to the moment it turned.

Hold the line at any round instead and he backs off in character, and the
situation moves on.

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
