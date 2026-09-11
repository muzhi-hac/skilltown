# Situation Verdict — design

**Goal:** a learner should never leave a situation unsure whether they got it right. Today a
situation ends in procedural text ("Review the cited conditions before deciding again"), which reads
like a form, not a result.

**Decided with the user:**

- The verdict is per situation, not per session.
- No jail imagery. It would exaggerate the consequence of every mistake and cost the product its
  credibility with the people it is dressed for.
- All copy in English, matching the rest of the UI.

## When each thing shows

| Moment | What the learner sees | Why |
|---|---|---|
| Passed mid-path | A light green inline line, the path continues on its own | Alex has five situations; a card each time would be five interruptions |
| Landed on a consequence | Failure card, with a way back and a way out | This is where a learner is actually stuck |
| Finished a visitor's whole path | One summary card | The moment worth marking |

## The two cards

**Failure — "You gave way this time."** Under it, one sentence naming what that costs, written per
consequence node. Buttons: `Try it again` (rewind) and `Next visitor →`.

Where the arc ran its rounds, add `You held for N rounds before giving way.` N is counted from the
learner's turns in `attempt.dialogue` at that node, so it is only shown when it is real.

**Success — "You held the line."** Under it, one sentence naming what the learner actually did,
written per scenario. Button: `Next visitor →`.

State wording follows the existing `STATE_LABELS`: `demonstrated` → "Passed independently",
`practiced` → "Practice completed". Nothing claims independence for a `practiced` result.

## Where the words come from

Authored in `server/content/scenarios.json`, not generated:

- `consequence_summary` on each `*_consequence` node — 17 lines.
- `completion_summary` on each scenario — 6 lines.

`content_validation` rejects a consequence node without a summary at startup, the way the existing
grounding checks do. The model is not asked for these: they must be stable, accurate, and present
when the model is off.

Four situations are permitted-with-conditions cases, where failing means refusing something the
rules allow. Their lines say that, rather than pretending the learner gave way:
`alex_permitted_meal`, `sam_permitted_cash`, `mira_encrypted_backup`, `jo_average_hours`.

## Drafted copy

### Consequence lines

| Node | Line |
|---|---|
| `alex_public_gift` | Accepting an unrecorded gift from a public official is what starts an internal investigation and a disciplinary file. |
| `alex_private_gift` | Treating the €30 benchmark as a blanket allowance keeps the pattern out of the register, where the next audit finds it instead of you. |
| `alex_business_meal` | Going ahead of the pending approval leaves a €100-per-head meal with nothing authorising it. |
| `alex_cash_gift` | Taking cash, at any amount, is what turns a hospitality question into a bribery one. |
| `alex_permitted_meal` | Refusing a meal the policy allows, or recording it wrongly, teaches the team the rules are arbitrary and pushes the next one off the books. |
| `sam_cash_limit` | Accepting cash over the ceiling puts the firm outside the limit, and the payment has to be unwound and reported anyway. |
| `sam_kyc_boundary` | Serving a cash customer before the identity check means the file cannot be reconstructed later, which is the part supervisors sanction. |
| `sam_linked_payments` | Taking the payments as four separate ones records the split the firm was supposed to notice. |
| `sam_beneficial_owner` | Missing the ownership trigger leaves the real controller off the file. |
| `sam_permitted_cash` | Turning away a payment the rules allow costs the sale and still leaves the team guessing where the line is. |
| `mira_privacy_clock` | Starting the clock at the breach instead of at awareness misses the 72-hour notification, and lateness is the part that gets fined. |
| `mira_nis2_stages` | Skipping the early warning means the regulator first hears about it in the final report. |
| `mira_encrypted_backup` | Notifying people when the encryption held spends their attention and the team's, and the assessment still has to be documented either way. |
| `jo_report_receipt` | A report without acknowledgement, feedback and confidentiality is a channel nobody uses twice. |
| `jo_no_retaliation` | Letting punitive shifts stand after a report is retaliation, and it is what turns one complaint into a case against the company. |
| `jo_rest_hours` | Signing off ten hours of rest puts the breach in writing under your name. |
| `jo_average_hours` | Blocking a schedule the reference-period average allows costs the team a week of cover and trains everyone to ignore the real limit. |

### Completion lines

| Scenario | Line |
|---|---|
| `screening` | You worked three situations from the stated facts and the cited thresholds. |
| `dinner-invitation` | You handled gifts, meals and cash from a counterpart who kept asking, and said what goes in the register. |
| `supplier-gift` | You held the cash thresholds, the identity checks and the splitting question at the counter. |
| `data-incidents` | You timed the notifications from awareness and said who had to hear about it. |
| `boundary-response` | You protected a reporter and the rest hours without blocking what the rules allow. |
| `ethics-review` | You reviewed your own earlier answers against the sources. |

## Client

One new component, `client/src/Verdict.tsx`, rendering the resting-state block that
`Lesson.tsx` currently builds inline. It is presentation only:

- failure when `attempt.effect === "consequence_preview"`
- success when `attempt.is_complete`
- the inline green line when a response carries `learning_updates` whose state is not
  `needs_practice` and the path continues

Animation is a short slide-and-settle in CSS, disabled under `prefers-reduced-motion`, which the
page does not currently honour anywhere.

## Testing

- Content validation rejects a consequence node with no `consequence_summary`, and a scenario with
  no `completion_summary`.
- API: a resolved arc returns the authored consequence line; a completed scenario returns the
  completion line.
- Browser: the failure card appears at the consequence with both buttons working, and the summary
  card appears at the end of a path.
