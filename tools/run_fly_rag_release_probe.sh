#!/usr/bin/env bash
# Run the no-model RAG performance probe on the deployed single Fly machine.
# Usage: tools/run_fly_rag_release_probe.sh [app-name]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$(awk -F'"' '/^app =/{print $2}' "$ROOT/fly.toml")}"

flyctl ssh console --app "$APP" --command 'python -m server.rag_release_probe'
