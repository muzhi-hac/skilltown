"""Hybrid retrieval over the EU compliance corpus, so answers are judged against
sources rather than vibes.

Two markdown documents in server/content/knowledge are split at their headings
into chunks, each carrying the heading path it came from. Retrieval combines:

- sparse: BM25 over the chunk text, with the heading weighted twice. Exact
  numbers and clause ids ("€25", "Art. 33", "NIS2") are what learners ask about,
  and lexical matching is unbeatable at those.
- dense: static distilled embeddings (model2vec, 256-dim, numpy only, no torch
  and no network at query time). This is what catches a learner who writes "how
  fast must we tell the regulator about a leak" when the passage says "notify the
  supervisory authority within 72 hours of awareness of a personal data breach".

The two rankings are fused with Reciprocal Rank Fusion, which needs no score
normalisation between two very different scales. If the embedding model is not
available, retrieval degrades to sparse only and says so instead of failing.

The corpus is reference material for training, not legal advice, and this module
never decides anything about a learner. It supplies the passages the evaluator is
allowed to cite, and the passages a question is anchored to.
"""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parents[1] / "content" / "knowledge"
# Baked into the image at build time so query encoding never needs the network.
DENSE_MODEL_PATH = Path(os.getenv(
    "SKILLTOWN_DENSE_MODEL_PATH",
    str(Path(__file__).parents[2] / "models" / "potion-base-8M"),
))
DENSE_MODEL_REVISION = os.getenv("SKILLTOWN_DENSE_MODEL_REVISION", "bf8b056651a2c21b8d2565580b8569da283cab23")
_DENSE_FAILURE_REASON = ""
_DENSE_RUNTIME_FAILURE = ""
# Reciprocal Rank Fusion constant; 60 is the value the original paper settles on.
RRF_K = 60
# Measured on 16 questions from this corpus (tools/retrieval_bench.py): sparse
# alone 11/16, dense alone 15/16, plain RRF 14/16, dense weighted twice 15/16.
# The weighted fusion matches dense on paraphrases while keeping sparse's edge on
# exact thresholds and clause ids, and it still works if the model is missing.
DENSE_WEIGHT = 2.0

# Chunks shorter than this are headings with no substance of their own.
MIN_CHUNK_CHARS = 80
# What a learner sees: enough to check a number, not a wall of text.
EXCERPT_CHARS = 700

DOC_LABELS = {
    "eu_regulation_reference.md": "EU Corporate Compliance - Regulation Reference",
    "eu_thresholds_annex.md": "EU Corporate Compliance - Practical Thresholds Annex",
}
DOC_PREFIXES = {"eu_regulation_reference.md": "REF", "eu_thresholds_annex.md": "ANNEX"}

_TOKEN = re.compile(r"[a-z0-9€§][a-z0-9€§._/-]*")
_STOPWORDS = frozenset(
    """a an and or the of to in for on at by with from as is are be if it its that this
    these those not no than then when where which who whom whose you your we our they
    their he she his her must may can should would could will shall do does did have has
    had was were been being about into over under between per each any all more most
    other such only own same so also very s t
    """.split()
)


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    path: str
    text: str
    source: str

    def excerpt(self) -> str:
        """A trimmed, single-paragraph view for the UI and for prompts."""
        collapsed = re.sub(r"\n{2,}", "\n", self.text).strip()
        if len(collapsed) <= EXCERPT_CHARS:
            return collapsed
        cut = collapsed[:EXCERPT_CHARS]
        last_break = max(cut.rfind("\n"), cut.rfind(". "))
        if last_break > EXCERPT_CHARS // 2:
            cut = cut[: last_break + 1]
        return cut.rstrip() + " …"


def tokenise(text: str) -> list[str]:
    return [word for word in _TOKEN.findall(text.casefold()) if word not in _STOPWORDS]


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return re.sub(r"-{2,}", "-", cleaned)[:48]


def _split_document(path: Path) -> list[Chunk]:
    """Split at markdown headings, keeping the heading path for context."""
    source = DOC_LABELS.get(path.name, path.name)
    prefix = DOC_PREFIXES.get(path.name, "DOC")
    chunks: list[Chunk] = []
    heading_stack: list[str] = []
    number = ""
    body: list[str] = []

    def flush() -> None:
        # A level-1 heading alone is the document's own title; its body is the
        # "what this document is" blurb, which matches everything and answers
        # nothing. Only real sections become chunks.
        if len(heading_stack) < 2:
            return
        text = "\n".join(body).strip()
        if len(text) < MIN_CHUNK_CHARS:
            return
        title = heading_stack[-1]
        clause = number or _slug(title)
        chunks.append(
            Chunk(
                id=f"{prefix}-{clause}",
                title=title,
                path=" › ".join(heading_stack),
                text=text,
                source=source,
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            # "### 1.2 Germany-Specific Thresholds" -> clause id 1.2
            numbered = re.match(r"^(\d+(?:\.\d+)*)\s*[·.]?\s*(.*)$", title)
            number = numbered.group(1) if numbered else ""
            body = []
            continue
        body.append(line)
    flush()
    return chunks


@lru_cache(maxsize=1)
def corpus() -> tuple[Chunk, ...]:
    documents = sorted(KNOWLEDGE_DIR.glob("*.md"))
    chunks: list[Chunk] = []
    for path in documents:
        chunks.extend(_split_document(path))
    return tuple(chunks)


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, Chunk], dict[str, float], dict[str, dict[str, int]], float]:
    chunks = {chunk.id: chunk for chunk in corpus()}
    frequencies: dict[str, dict[str, int]] = {}
    document_count: dict[str, int] = {}
    for chunk_id, chunk in chunks.items():
        # The heading carries the topic, so it counts twice.
        counts: dict[str, int] = {}
        for token in tokenise(chunk.text) + tokenise(chunk.path) * 2:
            counts[token] = counts.get(token, 0) + 1
        frequencies[chunk_id] = counts
        for token in counts:
            document_count[token] = document_count.get(token, 0) + 1
    total = max(len(chunks), 1)
    idf = {
        token: math.log(1 + (total - count + 0.5) / (count + 0.5))
        for token, count in document_count.items()
    }
    average_length = sum(sum(counts.values()) for counts in frequencies.values()) / total
    return chunks, idf, frequencies, average_length


def get(chunk_id: str) -> Chunk | None:
    return _index()[0].get(chunk_id)


def get_many(chunk_ids: list[str]) -> list[Chunk]:
    return [chunk for chunk in (get(chunk_id) for chunk_id in chunk_ids) if chunk is not None]


def search_sparse(query: str, limit: int = 3, within: str = "") -> list[Chunk]:
    """BM25 over the corpus. `within` narrows to chunks whose path contains it."""
    chunks, idf, frequencies, average_length = _index()
    terms = tokenise(query)
    if not terms:
        return []
    k1, b = 1.5, 0.75
    scored: list[tuple[float, str]] = []
    for chunk_id, counts in frequencies.items():
        if within and within.casefold() not in chunks[chunk_id].path.casefold():
            continue
        length = sum(counts.values()) or 1
        score = 0.0
        for term in terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            weight = idf.get(term, 0.0)
            score += weight * (frequency * (k1 + 1)) / (
                frequency + k1 * (1 - b + b * length / average_length)
            )
        if score > 0:
            scored.append((score, chunk_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunks[chunk_id] for _, chunk_id in scored[:limit]]


# --- dense side ----------------------------------------------------------------


def _set_dense_failure(reason: str) -> None:
    global _DENSE_FAILURE_REASON
    _DENSE_FAILURE_REASON = reason


def dense_failure_reason() -> str:
    return _DENSE_FAILURE_REASON


def dense_runtime_failure_reason() -> str:
    return _DENSE_RUNTIME_FAILURE


def mark_dense_runtime_failed(reason: str) -> None:
    global _DENSE_RUNTIME_FAILURE
    _DENSE_RUNTIME_FAILURE = reason


@lru_cache(maxsize=1)
def _encoder():
    """Load only the image-baked static model; runtime never downloads weights."""
    if not DENSE_MODEL_PATH.is_dir():
        _set_dense_failure("model_path_missing")
        return None
    try:
        from model2vec import StaticModel
        return StaticModel.from_pretrained(str(DENSE_MODEL_PATH))
    except Exception as exc:  # noqa: BLE001 - model loading must not crash sparse development mode
        _set_dense_failure(f"encoder_error:{type(exc).__name__}")
        logger.info("dense model unavailable: %s", exc)
        return None


def dense_available() -> bool:
    return _encoder() is not None


@lru_cache(maxsize=1)
def _dense_matrix():
    """Embed the corpus once. 66 chunks, so this is milliseconds."""
    encoder = _encoder()
    if encoder is None:
        return None, ()
    import numpy as np

    chunks = corpus()
    # The heading is part of the meaning of a clause, so it is embedded with it.
    texts = [f"{chunk.path}\n{chunk.text}" for chunk in chunks]
    try:
        vectors = np.asarray(encoder.encode(texts), dtype="float32")
    except Exception as exc:  # noqa: BLE001
        _set_dense_failure(f"encode_error:{type(exc).__name__}")
        return None, ()
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or vectors.shape[1] == 0:
        _set_dense_failure("matrix_shape_invalid")
        return None, ()
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms, tuple(chunk.id for chunk in chunks)


def search_dense(query: str, limit: int = 3, within: str = "") -> list[Chunk]:
    """Cosine similarity over static embeddings."""
    matrix, ids = _dense_matrix()
    # A query with nothing but stopwords carries no question; grounding on its
    # nearest neighbours would be noise dressed up as a source.
    if matrix is None or not tokenise(query):
        return []
    import numpy as np

    encoder = _encoder()
    try:
        vector = np.asarray(encoder.encode([query]), dtype="float32")[0]
    except Exception as exc:  # noqa: BLE001
        _set_dense_failure(f"query_encode_error:{type(exc).__name__}")
        raise RuntimeError("dense query encoding failed") from exc
    if vector.ndim != 1 or matrix.shape[1] != vector.shape[0]:
        _set_dense_failure("query_dimension_invalid")
        raise RuntimeError("dense query dimension does not match corpus matrix")
    norm = float(np.linalg.norm(vector)) or 1.0
    scores = matrix @ (vector / norm)
    chunks = _index()[0]
    order = np.argsort(-scores)
    results: list[Chunk] = []
    for position in order:
        chunk = chunks[ids[int(position)]]
        if within and within.casefold() not in chunk.path.casefold():
            continue
        results.append(chunk)
        if len(results) >= limit:
            break
    return results


def search(query: str, limit: int = 3, within: str = "") -> list[Chunk]:
    """Hybrid retrieval: BM25 and embeddings fused by reciprocal rank.

    Both sides are asked for more than `limit` so the fusion has something to
    work with; ties break towards the sparse ranking, which is the one that
    matches exact thresholds.
    """
    if not tokenise(query):
        return []
    depth = max(limit * 3, 6)
    sparse = search_sparse(query, limit=depth, within=within)
    if dense_runtime_failure_reason():
        dense = []
    else:
        try:
            dense = search_dense(query, limit=depth, within=within)
        except RuntimeError:
            mark_dense_runtime_failed(dense_failure_reason() or "dense_query_failed")
            dense = []
    if not dense:
        return sparse[:limit]

    scores: dict[str, float] = {}
    keep: dict[str, Chunk] = {}
    for ranking, weight in ((sparse, 1.0), (dense, DENSE_WEIGHT)):
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + weight / (RRF_K + rank)
            keep[chunk.id] = chunk
    sparse_rank = {chunk.id: rank for rank, chunk in enumerate(sparse)}
    ordered = sorted(
        keep.values(),
        key=lambda chunk: (-scores[chunk.id], sparse_rank.get(chunk.id, len(sparse)), chunk.id),
    )
    return ordered[:limit]
