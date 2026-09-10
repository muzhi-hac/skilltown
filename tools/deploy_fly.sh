#!/usr/bin/env bash
# Build the client and deploy it to Fly.io (remote builder, no local Docker needed).
#
#   tools/deploy_fly.sh [app-name]
#
# Before the first deploy: flyctl auth login. The app and volume are created separately.
set -euo pipefail

APP="${1:-$(awk -F'"' '/^app =/{print $2}' "$(dirname "$0")/../fly.toml")}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl is missing: brew install flyctl" >&2
  exit 1
fi
echo "==> Building the React web client (baked into the image, same origin)"
cd "$ROOT/client"
npm ci --cache "${NPM_CACHE_DIR:-/tmp/skilltown-npm-cache}"
npm run build
test -f "$ROOT/client/dist/index.html"

echo "==> Deploying to Fly app: $APP"
cd "$ROOT"
flyctl deploy --app "$APP" --remote-only

echo
echo "==> Smoke-testing the deployed URL"
python3 tools/smoke_api.py "https://$APP.fly.dev"
