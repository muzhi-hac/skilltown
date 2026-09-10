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
  echo "缺少凭据文件 $CREDS（需含 CLOUDFLARE_API_TOKEN 与 CLOUDFLARE_ACCOUNT_ID）" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$CREDS"; set +a

if [ ! -x "$GODOT" ]; then
  echo "找不到 Godot 可执行文件：$GODOT（可用 GODOT=... 覆盖）" >&2
  exit 1
fi

echo "==> 导出 Web 构建"
"$GODOT" --headless --path "$ROOT/godot" --export-release "Web" web/index.html

echo "==> 放入 Pages 代理 worker"
cp "$ROOT/cloudflare/_worker.js" "$ROOT/godot/web/_worker.js"

echo "==> 部署到 Cloudflare Pages 项目 $PROJECT"
cd "$ROOT"
npx --yes wrangler@latest pages deploy "godot/web" --project-name "$PROJECT" --commit-dirty=true

cat <<'NOTE'

部署完成后还需要一步：在 Pages 项目里设置环境变量 API_ORIGIN，指向能跑
Python 的后端（VPS/容器宿主，或 cloudflared 隧道地址）。没有它页面会拿到
503 api_origin_missing，无法创建会话。
NOTE
