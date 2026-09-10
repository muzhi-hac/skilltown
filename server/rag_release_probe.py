"""Measure the committed RAG runtime in a deployed image.

Run inside the image or through `fly ssh console`:

    python -m server.rag_release_probe

It does not call a model endpoint and does not alter learner data.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from server.core import knowledge
from server.core.rag_runtime import warmup_rag

QUERY = "personal data breach notification awareness 72 hours"


def _memory_value(*names: str) -> int | None:
    for name in names:
        try:
            value = int(Path(name).read_text(encoding="utf-8").strip())
            if value > 0:
                return value
        except (OSError, ValueError):
            continue
    return None


def _memory_snapshot() -> dict[str, int | None]:
    return {
        "peak_bytes": _memory_value(
            "/sys/fs/cgroup/memory.peak",
            "/sys/fs/cgroup/memory/memory.max_usage_in_bytes",
        ),
        "current_bytes": _memory_value(
            "/sys/fs/cgroup/memory.current",
            "/sys/fs/cgroup/memory/memory.usage_in_bytes",
        ),
        "limit_bytes": _memory_value(
            "/sys/fs/cgroup/memory.max",
            "/sys/fs/cgroup/memory/memory.limit_in_bytes",
        ),
    }


def main() -> int:
    cold_start = perf_counter()
    status = warmup_rag(require_dense=True)
    warmup_seconds = perf_counter() - cold_start
    if not status.ready:
        print(json.dumps({"status": status.payload(), "warmup_seconds": warmup_seconds}, indent=2))
        return 1

    start = perf_counter()
    for _ in range(100):
        knowledge.search(QUERY, limit=3)
    sequential_seconds = perf_counter() - start

    start = perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _: knowledge.search(QUERY, limit=3), range(100)))
    concurrent_seconds = perf_counter() - start

    print(json.dumps({
        "status": status.payload(),
        "warmup_seconds": round(warmup_seconds, 6),
        "sequential_100_seconds": round(sequential_seconds, 6),
        "concurrent_5x20_seconds": round(concurrent_seconds, 6),
        "memory": _memory_snapshot(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
