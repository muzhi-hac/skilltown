"""SkillTown FastAPI application."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.api.models import ErrorDetail, ErrorEnvelope, HealthResponse
from server.api.routes import router
from server.core.evaluator import FallbackTextEvaluator
from server.core.scenario_engine import ScenarioEngine, ScenarioError
from server.core.session import AuthError
from server.storage import (
    IdempotencyConflictError,
    NotFoundError,
    RevisionConflictError,
    Store,
)


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


def create_app(
    database_path: str | Path | None = None, web_dir: str | Path | None = None
) -> FastAPI:
    app = FastAPI(title="SkillTown Learning API", version="1.0.0")
    app.state.store = Store(database_path or os.getenv("DATABASE_PATH", "data/skilltown.sqlite3"))
    app.state.engine = ScenarioEngine()
    app.state.evaluator = FallbackTextEvaluator()
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

    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError):
        return _error(exc.status_code, exc.code, exc.message, exc.retryable)

    @app.exception_handler(AuthError)
    async def auth_error_handler(_request: Request, exc: AuthError):
        return _error(401, "unauthorized", str(exc))

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return _error(404, "not_found", str(exc))

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
    """Serve the Godot Web build from the same origin as /api/v1, when it exists.

    Same-origin means the client reads its API base from window.location.origin and
    no CORS applies. The build is generated (godot/web), so a missing directory is
    normal during backend-only work.
    """
    default = Path(__file__).parents[1] / "godot" / "web"
    directory = Path(web_dir or os.getenv("WEB_DIR", default))
    if not (directory / "index.html").is_file():
        return
    # Some hosts do not know .wasm; a wrong MIME type breaks the Godot loader.
    mimetypes.add_type("application/wasm", ".wasm")
    app.mount("/", StaticFiles(directory=directory, html=True), name="web")


app = create_app()
