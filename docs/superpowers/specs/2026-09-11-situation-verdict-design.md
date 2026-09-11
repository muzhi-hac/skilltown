# Situation Verdict — design

**Goal:** a learner should never leave a situation unsure whether they got it right. Today a
situation ends in procedural text ("Review the cited conditions before deciding again"), which reads
like a form, not a result.

**Decided with the user:**

- The verdict is per situation, not per session.
- No jail imagery. It would exaggerate the consequence of every mistake and cost the product its
  credibility with the people it is dressed for.
- All copy in English, matching the rest of the UI.
- A fixed consequence line describes the risk in the situation. It never guesses what this learner
  did wrong: the same consequence node receives opposite mistakes — accepting what should have been
  refused, and refusing what the rules allow.
- No round count. The learner's turns prove how many times they answered, not how long they held:
  three answers accepting the gift produce three turns too.
- Nothing claims the learner passed overall. `is_complete` proves the path ended, nothing more.

## When each thing shows

| Moment | What the learner sees | Why |
|---|---|---|
| Passed mid-path | A light green inline line, the path continues on its own | Alex has five situations; a card each time would be five interruptions |
| Landed on a consequence | Failure card, with a way back and a way out | This is where a learner is actually stuck |
| Finished a visitor's whole path | One summary card | The moment worth marking |

## The two cards

**Consequence — "This decision needs another look."** Under it, the authored line for that node.
Buttons: `Try it again` (rewind) and `Next visitor →`.

**End of a path — "Practice completed."** Under it, the authored line for that scenario, which says
what the practice covered rather than what the learner got right. Button: `Next visitor →`.

`Passed independently` stays where it already is: on a skill in the passport that has
`demonstrated` evidence. It is never promoted into a conclusion about the whole path.

## Where the words come from

Authored in `server/content/scenarios.json`, not generated:

- `consequence_summary` on each `*_consequence` node — 17 lines.
- `completion_summary` on each scenario — 6 lines.

`content_validation` rejects a missing summary at startup, the way the existing grounding checks do.
The model is not asked for these: they must be stable, accurate, and present when the model is off.

## Copy

### Consequence lines

| Node | Line |
|---|---|
| `alex_public_gift` | Gifts involving public officials need careful handling; missing the applicable conditions or documentation can lead to compliance concerns. |
| `alex_private_gift` | The €30 benchmark alone does not settle the decision; context, frequency and registration still matter. |
| `alex_business_meal` | Proceeding while approval is pending can leave the meal outside the stated approval process. |
| `alex_cash_gift` | Cash gifts fall outside the hospitality rules in this scenario and raise bribery concerns. |
| `alex_permitted_meal` | A blanket refusal can block permitted hospitality, while missing its conditions can leave it improperly documented. |
| `sam_cash_limit` | Accepting a payment above the applicable cash limit can expose the firm to compliance action. |
| `sam_kyc_boundary` | Proceeding without the required identity check leaves the customer verification incomplete. |
| `sam_linked_payments` | Treating linked payments separately can hide a total that exceeds the applicable cash limit. |
| `sam_beneficial_owner` | Applying the wrong ownership or control test can leave the beneficial-ownership assessment incomplete. |
| `sam_permitted_cash` | A blanket refusal can block a permitted payment; acceptance still depends on the stated checks and records. |
| `mira_privacy_clock` | Using the wrong starting point or notification test can misdirect the breach response. |
| `mira_nis2_stages` | Missing a reporting stage can delay the information needed for an effective incident response. |
| `mira_encrypted_backup` | Automatic notification can cause unnecessary alarm; effective encryption and the risk assessment still need to be considered and documented. |
| `jo_report_receipt` | Missing acknowledgement, feedback or confidentiality can undermine trust in the reporting channel. |
| `jo_no_retaliation` | Punitive scheduling in response to a report can harm the reporter and undermine the reporting process. |
| `jo_rest_hours` | Approving ten hours of rest would fall short of the minimum stated in this scenario. |
| `jo_average_hours` | A blanket refusal can block a permitted schedule; the reference-period average and other applicable limits still need checking. |

### Completion lines

They say what the practice covered. None of them claims the learner got it all right.

| Scenario | Line |
|---|---|
| `screening` | You completed three starting situations. Your recorded answers show where to practise next. |
| `dinner-invitation` | This practice covered gifts, meals, cash and the conditions for accepting or declining them. |
| `supplier-gift` | This practice covered cash limits, identity checks, linked payments and beneficial ownership. |
| `data-incidents` | This practice covered notification timing, recipients and the role of risk assessment. |
| `boundary-response` | This practice covered reporting protections, rest periods and conditional scheduling decisions. |
| `ethics-review` | This review explored a selected case using the supplied sources. |

## Client

One new component, `client/src/Verdict.tsx`, rendering the resting-state block `Lesson.tsx`
currently builds inline. Presentation only:

- consequence when `attempt.effect === "consequence_preview"`
- end of path when `attempt.is_complete`
- the inline green line when a response carries `learning_updates` whose state is not
  `needs_practice` and the path continues

Animation is a short settle in CSS, disabled under `prefers-reduced-motion`, which the page does not
currently honour anywhere.

## Reaching the buttons (Task C, merged in)

A verdict nobody scrolls to is not a verdict: at the consequence the page is 2253px against an
813px viewport, so the card sits far below the fold. The lesson panel becomes three bands — header,
a scrolling reader, and an action row that stays in view.

Acceptance:

- Arriving at a consequence or a completion brings the verdict heading into view by itself.
- The primary action stays reachable and never covers the text being read.
- Checked once each on a long transcript, a narrow screen, and with reduced motion on.
- Updates never force a scroll to the bottom: a learner reading back through the transcript is not
  yanked away from it.

## Testing

- Content validation rejects a consequence node with no `consequence_summary`, and a scenario with
  no `completion_summary`.
- API: a resolved arc returns the authored consequence line; a completed scenario returns the
  completion line.
- Browser: the failure card appears at the consequence with both buttons working and its heading in
  view; the summary card appears at the end of a path.
