#!/usr/bin/env bash
# Build the client and deploy it to Fly.io (remote builder, no local Docker needed).
#
#   tools/deploy_fly.sh [app-name]
#
# Before the first deploy: flyctl auth login. The app and volume are created separately.
set -euo pipefail

APP="${1:-$(awk -F'"' '/^app =/{print $2}' "$(dirname "$0")/../fly.toml")}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl is missing: brew install flyctl" >&2
  exit 1
fi
if [ ! -x "$GODOT" ]; then
  echo "Godot not found: $GODOT (override with GODOT=...)" >&2
  exit 1
fi

echo "==> Building the web client (baked into the image, same origin)"
"$GODOT" --headless --path "$ROOT/godot" --export-release "Web" web/index.html
test -f "$ROOT/godot/web/index.html"

echo "==> Deploying to Fly app: $APP"
cd "$ROOT"
flyctl deploy --app "$APP" --remote-only

echo
echo "==> Smoke-testing the deployed URL"
python3 tools/smoke_api.py "https://$APP.fly.dev"
