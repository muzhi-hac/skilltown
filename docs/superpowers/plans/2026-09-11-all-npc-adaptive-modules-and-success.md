# All-NPC Adaptive Modules and Success Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Sam, Nina and Jo the same evidence-driven questioning contract as Alex, expose every visitor's learning module to the learner, and pause after a successful decision with explicit continue-or-switch actions.

**Architecture:** Keep the model as a proposer and reuse the existing server-owned `select_strategy` path for every configured pressure persona. Content owns character-specific fallback lines and per-node rubric groupings/action rules; the runtime enables any fully configured persona rather than hard-coding Alex. The town API exposes presentation-safe module metadata, while the client adds a module disclosure and a success handoff without exposing personas or grading rubrics.

**Tech Stack:** Python 3.13/FastAPI/Pydantic, JSON scenario content, React 19/TypeScript, CSS, pytest, Vite/oxlint.

---

### Task 1: Generalize the adaptive runtime

**Files:**
- Modify: `server/core/grounding.py`
- Modify: `server/core/model_evaluator.py`
- Modify: `server/api/routes.py`
- Test: `server/tests/test_grounding.py`
- Test: `server/tests/test_model_evaluator.py`
- Test: `server/tests/test_api.py`

- [ ] Replace the Alex-only NPC/scenario check with a configuration-driven check: an enabled pressure node is adaptive exactly when its persona has `adaptive_policy` and its node has `adaptive_rubric`.
- [ ] Add `SKILLTOWN_ADAPTIVE_NPCS_ENABLED`, while treating the existing `SKILLTOWN_ALEX_ADAPTIVE_ENABLED` as a backward-compatible fallback.
- [ ] Rename Alex-specific runtime comments/log wording to visitor-neutral language without changing the API response contract.
- [ ] Add tests proving Sam becomes adaptive when configured, unconfigured/coach nodes stay fixed, server strategy overrides model proposals, deferred answers spend no pressure round, and repeated generated dialogue is replaced.
- [ ] Run `python -m pytest server/tests/test_grounding.py server/tests/test_model_evaluator.py server/tests/test_api.py -q`; expect all selected tests to pass.

### Task 2: Author adaptive content for Sam, Nina and Jo

**Files:**
- Modify: `server/content/scenarios.json`
- Modify: `server/tests/test_content_validation.py`

- [ ] Add the complete nine-strategy `adaptive_policy` to Sam, Nina and Jo, with fallback lines in each character's voice.
- [ ] Add `adaptive_rubric` to all five Sam nodes, three Nina nodes and four Jo nodes. Each rubric partitions every required criterion into reasons/decision/execution and declares node-specific explicit action rules.
- [ ] Update validation tests to require every pressure persona and every pressure node to carry complete adaptive configuration.
- [ ] Run `python -m pytest server/tests/test_content_validation.py server/tests/test_alex_strategy.py -q`; expect all tests to pass.

### Task 3: Expose visitor module metadata

**Files:**
- Modify: `server/content/scenarios.json`
- Modify: `server/core/content_validation.py`
- Modify: `server/core/scenario_engine.py`
- Modify: `server/api/models.py`
- Modify: `client/src/api.ts`
- Modify: `client/src/App.tsx`
- Modify: `client/src/styles.css`
- Test: `server/tests/test_api.py`
- Test: `server/tests/test_content_validation.py`

- [ ] Add presentation-safe `module` metadata (`label`, `summary`, `skills`) to every NPC, including Mira.
- [ ] Validate non-empty module fields and expose them from `town_payload` while continuing to omit the private persona.
- [ ] Add a `What <name> covers` button beside the door and in the lesson header; toggle an accessible module panel listing the module summary and skill labels.
- [ ] Reset the module panel when the visitor changes or a task starts.
- [ ] Test the town contract includes modules and still excludes personas.
- [ ] Run `python -m pytest server/tests/test_api.py server/tests/test_contract.py server/tests/test_content_validation.py -q` and `cd client && npm run build`; expect success.

### Task 4: Add an explicit success handoff

**Files:**
- Modify: `client/src/Lesson.tsx`
- Modify: `client/src/Verdict.tsx`
- Modify: `client/src/App.tsx`
- Modify: `client/src/styles.css`

- [ ] Detect a successful assessed transition from learning updates whose state is `practiced` or `demonstrated`.
- [ ] Before accepting an answer on the already-returned next node, replace the answer controls with a success card: `Decision accepted`, the recorded skill, `Continue with <NPC>` and `Next visitor`.
- [ ] Keep consequence/deferred behavior unchanged; acknowledge a success by attempt revision so it appears once only.
- [ ] Change final completion copy to `Module complete` and retain the `Next visitor` action.
- [ ] Run `cd client && npm run build && npm run lint`; expect build success and only the existing lint baseline.

### Task 5: Regression, live visual QA and delivery

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `fly.toml`

- [ ] Document adaptive visitors, the new global switch with legacy fallback, module disclosure, and success handoff.
- [ ] Enable `SKILLTOWN_ADAPTIVE_NPCS_ENABLED=true` in Fly and retain the legacy switch during the transition.
- [ ] Run `python -m pytest server/tests -q`, client build/lint, model-disabled e2e and smoke against a temporary local database.
- [ ] Visually verify desktop and narrow layouts: module disclosure, collapsed policy references, intermediate success card, continue-same-NPC, and next-visitor return.
- [ ] Review `git diff --check`, confirm no secret/build/database artifacts, commit, push main, wait for CI/deploy, and verify production `/ready` plus a browser canary.

## Self-review

- Spec coverage: all pressure NPCs are adaptive; Mira remains a coach but receives visible module metadata; module ownership is visible before and during a task; successful intermediate and final states expose the next action.
- Security boundary: town output adds only authored learner-facing module metadata; personas, tactics, rubrics and action rules remain server-only.
- Compatibility: the old Alex flag continues to enable configured adaptive nodes until deployment environments adopt the new global flag.
- Scope: no database migration and no new endpoint; existing attempt/town response shapes are extended compatibly.
