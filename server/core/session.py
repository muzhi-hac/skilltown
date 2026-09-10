"""Bearer-session authentication dependency."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Request


class AuthError(RuntimeError):
    pass


def require_session(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("Missing bearer session")
    token = authorization.removeprefix("Bearer ").strip()
    session = request.app.state.store.get_session(token)
    if not session:
        raise AuthError("Session is missing or expired")
    return session
