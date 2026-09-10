"""Fetch the exact dense model payload during image build and verify it."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(lock: dict, output: Path) -> None:
    repo_id, revision = lock["repo_id"], lock["revision"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp_dir:
        staged = Path(temp_dir) / "model"
        staged.mkdir()
        for relative, expected in lock["files"].items():
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{relative}"
            with urlopen(url, timeout=120) as response, destination.open("wb") as handle:  # noqa: S310 -- pinned public model URL
                shutil.copyfileobj(response, handle)
            actual = sha256(destination)
            if actual != expected:
                raise RuntimeError(f"checksum mismatch for {relative}: {actual}")
        if output.exists():
            shutil.rmtree(output)
        staged.rename(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "content" / "dense_model.lock.json")
    parser.add_argument("--output", type=Path, default=ROOT.parents[0] / "models" / "potion-base-8M")
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    required = {"repo_id", "revision", "model2vec_version", "files", "license"}
    if set(lock) != required or not lock["files"]:
        raise RuntimeError("invalid dense model lock")
    download(lock, args.output)
    print(f"verified {len(lock['files'])} files for {lock['repo_id']}@{lock['revision']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"dense model build failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
