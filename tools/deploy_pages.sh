#!/usr/bin/env bash
# Export the Godot Web build and deploy it to Cloudflare Pages.
#
# Credentials are read from ~/.config/skilltown/cloudflare.env (chmod 600) and
# never stored in this repository.
#
#   tools/deploy_pages.sh [project-name]
set -euo pipefail

PROJECT="${1:-skilltown}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"
CREDS="${SKILLTOWN_CF_ENV:-$HOME/.config/skilltown/cloudflare.env}"

if [ ! -f "$CREDS" ]; then
  echo "Missing credentials file $CREDS (needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID)" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$CREDS"; set +a

if [ ! -x "$GODOT" ]; then
  echo "Godot executable not found: $GODOT (override with GODOT=...)" >&2
  exit 1
fi

echo "==> Building the web client"
"$GODOT" --headless --path "$ROOT/godot" --export-release "Web" web/index.html

echo "==> Adding the Pages proxy worker"
cp "$ROOT/cloudflare/_worker.js" "$ROOT/godot/web/_worker.js"

echo "==> Deploying to Cloudflare Pages project $PROJECT"
cd "$ROOT"
npx --yes wrangler@latest pages deploy "godot/web" --project-name "$PROJECT" --commit-dirty=true

cat <<'NOTE'

After deploying, set API_ORIGIN in the Pages project to a backend that runs
Python (a VPS, a container host, or a cloudflared tunnel). Without it the page
gets 503 api_origin_missing and cannot create a session.
NOTE
