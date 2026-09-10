#!/usr/bin/env bash
# 导出 Godot Web 构建，然后部署到 Fly.io（远程构建，本机不需要 Docker）。
#
#   tools/deploy_fly.sh [app-name]
#
# 首次部署前需要：flyctl auth login；卷和 app 由 launch/deploy 创建。
set -euo pipefail

APP="${1:-$(awk -F'"' '/^app =/{print $2}' "$(dirname "$0")/../fly.toml")}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"

if ! command -v flyctl >/dev/null 2>&1; then
  echo "缺少 flyctl：brew install flyctl" >&2
  exit 1
fi
if [ ! -x "$GODOT" ]; then
  echo "找不到 Godot：$GODOT（可用 GODOT=... 覆盖）" >&2
  exit 1
fi

echo "==> 导出 Web 构建（会被打进镜像，实现同源）"
"$GODOT" --headless --path "$ROOT/godot" --export-release "Web" web/index.html
test -f "$ROOT/godot/web/index.html"

echo "==> 部署到 Fly app: $APP"
cd "$ROOT"
flyctl deploy --app "$APP" --remote-only

echo
echo "==> 冒烟测试线上环境"
python3 tools/smoke_api.py "https://$APP.fly.dev"
