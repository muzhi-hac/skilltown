"""SkillTown FastAPI application."""

from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.api.models import ErrorDetail, ErrorEnvelope, HealthResponse, ReadyResponse
from server.api.routes import router
from server.core import knowledge
from server.core.model_evaluator import build_evaluator
from server.core.scenario_engine import ScenarioEngine, ScenarioError, ScenarioVersionError
from server.core.rag_runtime import warmup_rag
from server.core.session import AuthError
from server.storage import (
    IdempotencyConflictError,
    NotFoundError,
    RevisionConflictError,
    Store,
)


logger = logging.getLogger(__name__)

ENV_FILE = Path(__file__).parents[1] / ".env"


def load_local_env(path: Path | None = None) -> list[str]:
    """Read a local .env so a developer only has to paste a key into a file.

    A real environment variable always wins, so this can never quietly override
    what a deployment set. The file is gitignored and excluded from the image;
    production gets its configuration from the platform, not from here. Names of
    what was loaded are logged, never values.

    ENV_FILE is read on every call rather than bound as a default argument, so
    pointing it elsewhere in a test actually redirects this. Bound as a default
    it silently would not, and the suite would run against a real key.
    """
    path = path or ENV_FILE
    if not path.exists():
        return []
    loaded: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        # A blank line in the template means "not set". Exporting it as an empty
        # string is worse than skipping it: the SDKs read some of these names
        # themselves, and an empty ANTHROPIC_BASE_URL becomes a URL with no
        # scheme, which fails as a connection error rather than a config error.
        if not key or not value or key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    if loaded:
        logger.info("loaded %d names from %s: %s", len(loaded), path.name, ", ".join(loaded))
    return loaded


class ApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable


def _error(status_code: int, code: str, message: str, retryable: bool = False, latest=None):
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=f"req-{uuid4().hex[:8]}",
            retryable=retryable,
            latest_attempt_url=latest,
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json", exclude_none=True))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.require_dense = os.getenv("SKILLTOWN_REQUIRE_DENSE", "false").strip().lower() in {"1", "true", "yes", "on"}
    app.state.rag_status = warmup_rag(app.state.require_dense)
    yield


def create_app(
    database_path: str | Path | None = None, web_dir: str | Path | None = None
) -> FastAPI:
    load_local_env()
    app = FastAPI(title="SkillTown Learning API", version="1.0.0", lifespan=_lifespan)
    app.state.store = Store(database_path or os.getenv("DATABASE_PATH", "data/skilltown.sqlite3"))
    app.state.engine = ScenarioEngine()
    app.state.evaluator = build_evaluator()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin for origin in os.getenv("CORS_ORIGINS", "http://localhost:8060").split(",") if origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse, operation_id="healthCheck")
    def health():
        return HealthResponse()

    @app.get("/ready", response_model=ReadyResponse, operation_id="readinessCheck")
    def ready():
        status = app.state.rag_status
        degraded = knowledge.dense_runtime_failure_reason()
        if degraded and status.retrieval_mode == "hybrid":
            # Dense broke after the snapshot was taken. Re-warming here would make
            # a probe do real retrieval work on every call, and something already
            # asserts this endpoint does not; so report the degradation from what
            # is already known rather than keep answering "hybrid".
            status = replace(
                status,
                ready=not app.state.require_dense,
                retrieval_mode="unavailable" if app.state.require_dense else "sparse",
                reason=f"dense_runtime_failure:{degraded}",
            )
        return JSONResponse(status_code=200 if status.ready else 503, content=status.payload())

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError):
        return _error(exc.status_code, exc.code, exc.message, exc.retryable)

    @app.exception_handler(AuthError)
    async def auth_error_handler(_request: Request, exc: AuthError):
        return _error(401, "unauthorized", str(exc))

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return _error(404, "not_found", str(exc))

    @app.exception_handler(ScenarioVersionError)
    async def scenario_version_handler(_request: Request, exc: ScenarioVersionError):
        return _error(409, "scenario_version_mismatch", str(exc), False)

    @app.exception_handler(ScenarioError)
    async def scenario_error_handler(_request: Request, exc: ScenarioError):
        return _error(400, "invalid_scenario_action", str(exc))

    @app.exception_handler(RevisionConflictError)
    async def revision_error_handler(request: Request, exc: RevisionConflictError):
        return _error(409, "revision_conflict", str(exc), True, str(request.url.path).removesuffix("/respond"))

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_error_handler(_request: Request, exc: IdempotencyConflictError):
        return _error(409, "idempotency_conflict", str(exc), False)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        details = "; ".join(error["msg"] for error in exc.errors()[:3])
        return _error(422, "validation_error", details)

    app.include_router(router)
    _mount_web_client(app, web_dir)
    return app


def _mount_web_client(app: FastAPI, web_dir: str | Path | None) -> None:
    """Serve the built web client from the same origin as /api/v1, when it exists.

    Same-origin means the client reads its API base from window.location.origin and
    no CORS applies. The build is generated (client/dist), so a missing directory is
    normal during backend-only work.
    """
    default = Path(__file__).parents[1] / "client" / "dist"
    directory = Path(web_dir or os.getenv("WEB_DIR", default))
    if not (directory / "index.html").is_file():
        return
    # Some hosts do not know .wasm; a wrong MIME type breaks the Godot loader.
    mimetypes.add_type("application/wasm", ".wasm")
    app.mount("/", StaticFiles(directory=directory, html=True), name="web")


app = create_app()
