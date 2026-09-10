"""One-time RAG readiness checks for deployment probes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from server.core import knowledge


@dataclass(frozen=True)
class RagStatus:
    ready: bool
    retrieval_mode: Literal["hybrid", "sparse", "unavailable"]
    chunk_count: int
    model_revision: str
    reason: str

    def payload(self) -> dict:
        return asdict(self)


def warmup_rag(require_dense: bool) -> RagStatus:
    chunks = knowledge.corpus()
    count = len(chunks)
    if not count:
        return RagStatus(False, "unavailable", 0, knowledge.DENSE_MODEL_REVISION, "empty_corpus")
    try:
        matrix, ids = knowledge._dense_matrix()  # intentionally warms the single cached matrix
        if matrix is not None and len(ids) == count:
            hits = knowledge.search_dense("personal data breach notification", limit=1)
            if hits:
                return RagStatus(True, "hybrid", count, knowledge.DENSE_MODEL_REVISION, "")
    except Exception:  # dense_failure_reason records a non-sensitive compact reason
        pass
    if require_dense:
        return RagStatus(False, "unavailable", count, knowledge.DENSE_MODEL_REVISION, "dense_required")
    if knowledge.search_sparse("personal data breach notification", limit=1):
        return RagStatus(True, "sparse", count, knowledge.DENSE_MODEL_REVISION, "dense_unavailable")
    return RagStatus(False, "unavailable", count, knowledge.DENSE_MODEL_REVISION, "sparse_unavailable")
