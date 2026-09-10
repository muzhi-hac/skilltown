from __future__ import annotations

import numpy as np

from server.core import knowledge
from server.core.rag_runtime import warmup_rag


def test_empty_corpus_is_unavailable(monkeypatch):
    monkeypatch.setattr(knowledge, "corpus", lambda: ())
    status = warmup_rag(require_dense=False)
    assert (status.ready, status.retrieval_mode, status.reason) == (False, "unavailable", "empty_corpus")


def test_missing_dense_model_can_use_sparse(monkeypatch):
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: (None, ()))
    monkeypatch.setattr(knowledge, "search_sparse", lambda *args, **kwargs: [knowledge.corpus()[0]])
    status = warmup_rag(require_dense=False)
    assert (status.ready, status.retrieval_mode, status.reason) == (True, "sparse", "dense_unavailable")


def test_missing_dense_model_fails_when_required(monkeypatch):
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: (None, ()))
    status = warmup_rag(require_dense=True)
    assert (status.ready, status.retrieval_mode, status.reason) == (False, "unavailable", "dense_required")


def test_healthy_dense_runtime_reports_hybrid(monkeypatch):
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: (object(), tuple(chunk.id for chunk in knowledge.corpus())))
    monkeypatch.setattr(knowledge, "search_dense", lambda *args, **kwargs: [knowledge.corpus()[0]])
    status = warmup_rag(require_dense=True)
    assert status.ready and status.retrieval_mode == "hybrid" and status.reason == ""


def test_query_encoding_failure_is_not_reported_as_hybrid(monkeypatch):
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: (object(), tuple(chunk.id for chunk in knowledge.corpus())))
    monkeypatch.setattr(knowledge, "search_dense", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("encode")))
    monkeypatch.setattr(knowledge, "search_sparse", lambda *args, **kwargs: [knowledge.corpus()[0]])
    status = warmup_rag(require_dense=False)
    assert (status.ready, status.retrieval_mode) == (True, "sparse")


def test_matrix_dimension_error_records_reason(monkeypatch):
    class BrokenEncoder:
        def encode(self, values): return np.asarray([1, 2, 3], dtype="float32")
    monkeypatch.setattr(knowledge, "_encoder", lambda: BrokenEncoder())
    knowledge._dense_matrix.cache_clear()
    matrix, ids = knowledge._dense_matrix()
    assert matrix is None and ids == () and knowledge.dense_failure_reason() == "matrix_shape_invalid"
    knowledge._dense_matrix.cache_clear()


def test_runtime_failure_disables_later_dense_search(monkeypatch):
    monkeypatch.setattr(knowledge, "_DENSE_RUNTIME_FAILURE", "")
    monkeypatch.setattr(knowledge, "search_sparse", lambda *args, **kwargs: [knowledge.corpus()[0]])
    monkeypatch.setattr(knowledge, "search_dense", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("query")))
    assert knowledge.search("personal data breach")[0].id
    assert knowledge.dense_runtime_failure_reason()
    # Once marked failed, hybrid search does not call the failing dense encoder again.
    assert knowledge.search("personal data breach")[0].id


def test_readiness_result_is_a_snapshot_not_a_rewarm(monkeypatch):
    calls = []
    monkeypatch.setattr(knowledge, "_dense_matrix", lambda: calls.append("matrix") or (None, ()))
    monkeypatch.setattr(knowledge, "search_sparse", lambda *args, **kwargs: [knowledge.corpus()[0]])
    status = warmup_rag(require_dense=False)
    assert status.ready and calls == ["matrix"]
