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
from server.core import knowledge


PROVIDER_NAMES = (
    # A switch a developer has on in their shell must not decide what the suite
    # tests, the way the dense model on disk used to.
    "SKILLTOWN_ALEX_ADAPTIVE_ENABLED",
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


def test_isolation_actually_redirects_the_env_file(tmp_path, monkeypatch):
    """The guard above is worthless if it can be bypassed by a bound default."""
    monkeypatch.setattr(main, "ENV_FILE", tmp_path / "redirected.env")
    (tmp_path / "redirected.env").write_text("SKILLTOWN_PROOF=redirected\n", encoding="utf-8")
    assert main.load_local_env() == ["SKILLTOWN_PROOF"]
    monkeypatch.delenv("SKILLTOWN_PROOF", raising=False)


def _reset_dense_state() -> None:
    knowledge._DENSE_FAILURE_REASON = ""
    knowledge._DENSE_RUNTIME_FAILURE = ""
    for name in ("_encoder", "_dense_matrix"):
        # A test that replaced one of these still has its stand-in in place when
        # this runs: monkeypatch undoes its own patches after this fixture.
        clear = getattr(getattr(knowledge, name), "cache_clear", None)
        if clear is not None:
            clear()


@pytest.fixture(autouse=True)
def dense_is_opt_in(tmp_path, monkeypatch):
    """Retrieval mode is decided by the test, never by the developer's machine.

    Running the server once leaves models/potion-base-8M on disk, so the same
    suite reported hybrid there and sparse on a fresh CI runner - two tests went
    red on the machine that had the model. The failure flags are module globals
    that nothing ever clears, so they leak between tests too.
    """
    monkeypatch.setattr(knowledge, "DENSE_MODEL_PATH", tmp_path / "no-dense-model")
    _reset_dense_state()
    yield
    _reset_dense_state()


@pytest.fixture
def dense_available(monkeypatch):
    """Opt in to a working dense index without shipping a model to the runner."""
    ids = tuple(range(len(knowledge.corpus())))
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: (object(), ids))
    monkeypatch.setattr(knowledge, "search_dense", lambda *a, **k: list(knowledge.corpus()[:1]))
    return True
