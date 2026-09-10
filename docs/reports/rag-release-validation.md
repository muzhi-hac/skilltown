# RAG release validation

Date: 2026-09-10  
Workspace revision: `feat/npc-rag-skills` (uncommitted implementation work)

## Resource and runtime evidence

| Check | Actual result |
| --- | --- |
| Corpus in workspace | 64 indexed chunks from `eu_regulation_reference.md` and `eu_thresholds_annex.md` |
| Runtime image | Python 3.13; Linux arm64; model2vec 0.9.0; 512MiB memory limit |
| Dense model | `minishlab/potion-base-8M` revision `bf8b056651a2c21b8d2565580b8569da283cab23` |
| Model lock verification | 7 pinned files downloaded and SHA-256 checked by `server/build_dense_model.py` |
| Local runtime warmup | `RagStatus(ready=True, retrieval_mode='hybrid', chunk_count=64, model_revision='bf8b056651a2c21b8d2565580b8569da283cab23', reason='')` |
| API readiness with `SKILLTOWN_REQUIRE_DENSE=true` | HTTP 200; `hybrid`, 64 chunks |
| Container image | `skilltown:rag-check`, manifest `sha256:d3fbe34d3a280a4e19d792ad1fbcb1cb16f3f66270f501562d5237e90c4a8d72` |
| 512MB container cold readiness | `/ready` returned hybrid in 0.955s (one local cold-start sample). |
| 512MB container retrieval load | Initial load probe: 100 sequential retrievals 0.0090s; 5×20 concurrent retrievals 0.0157s. Rebuilt-image `server.rag_release_probe`: warmup 0.471925s, sequential 0.010084s, concurrent 0.017794s, isolated cgroup peak 88,408,064 bytes (84.3MiB). |
| 512MB container memory | Retrieval load peak: 195,231,744 bytes (186.2MiB). Full API smoke/matrix peak: 109,047,808 bytes (104.0MiB); post-matrix `docker stats`: `101.9MiB / 512MiB`. |
| Network-isolated image smoke | Corpus: 64 chunks; `warmup_rag(True)` returned hybrid. |

## Contract and regression checks

| Command | Actual result |
| --- | --- |
| `.venv/bin/python -m pytest server/tests -q` | 53 passed, 1 third-party deprecation warning |
| `cd client && npm run build` | Passed; production assets emitted |
| `python3 tools/smoke_api.py http://127.0.0.1:8765` | Passed against hybrid readiness service |
| Container HTTP smoke + answer matrix (`:8768`) | Passed: readiness, provenance, deferred, rewind, idempotency, isolation and 5/5 fixed cases |
| `.venv/bin/python tools/e2e_room.py http://127.0.0.1:8771` | Passed against the rebuilt image: screening, evidence, progress return, ordered NPC queue, Mira task chooser/review and record clearing in real Chrome |
| `git diff --check` | Passed |
| `tools/check_model.py` | No model credential in this runtime; paid model matrix not run |
| `SKILLTOWN_DENSE_MODEL_PATH=/tmp/skilltown-potion-base-8M SKILLTOWN_REQUIRE_DENSE=true ... uvicorn` then `GET /ready` | HTTP 200 hybrid readiness |

## Deterministic answer matrix

The matrix uses independently committed cases in `server/tests/fixtures/grounded_cases.json` and runs each case in a new API attempt.

| Case | Expected | Actual | Assessment | Cited ids |
| --- | --- | --- | --- | --- |
| alex-public-pass | pass | pass | assessed | ANNEX-1.1, ANNEX-1.2, ANNEX-1.3 |
| alex-public-overgeneralized | overgeneralized | overgeneralized | assessed | ANNEX-1.1, ANNEX-1.2, ANNEX-1.3 |
| sam-cash-miss | miss | miss | assessed | ANNEX-4.1 |
| mira-privacy-pass | pass | pass | assessed | ANNEX-2.1 |
| jo-report-pass | pass | pass | assessed | ANNEX-6.3 |

## Remaining release gate

The local cold-start/retrieval measurements are below the 400MiB suggested peak threshold. Run `tools/run_fly_rag_release_probe.sh <app>` on the target Fly CPU architecture, then run `tools/answer_matrix.py https://<app>.fly.dev` with an explicitly configured model credential before making a production performance claim.
