"""Keep the suite hermetic: no developer's .env, no credential, no network.

server.main.create_app reads a local .env so that pasting a key into a file is
enough to run the model. That convenience must never reach the tests, or a
machine with a real key would quietly evaluate against a paid endpoint and a
machine with a stale one would spend every assertion waiting for a connection
to fail.
"""

from __future__ import annotations

import pytest

import server.main as main


PROVIDER_NAMES = (
    "SKILLTOWN_MODEL_ENABLED",
    "SKILLTOWN_MODEL",
    "SKILLTOWN_MODEL_PROVIDER",
    "SKILLTOWN_MODEL_USER_AGENT",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORGANIZATION",
)


@pytest.fixture(autouse=True)
def no_ambient_model(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "ENV_FILE", tmp_path / "absent.env")
    for name in PROVIDER_NAMES:
        monkeypatch.delenv(name, raising=False)
