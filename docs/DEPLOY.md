# 部署：静态页面在 Cloudflare，API 需要一台能跑 Python 的源站

## 为什么不能全放 Cloudflare Workers/Pages

后端是 FastAPI（Python）+ 磁盘 SQLite。Workers/Pages 的运行时是 JS/WASM，没有
持久文件系统，跑不了这套代码。三条路：

1. **Pages + 外部源站（推荐，改动最小）**：Pages 托管 Godot 静态构建，
   `cloudflare/_worker.js` 把 `/api/*` 和 `/health` 反代到 Pages 环境变量
   `API_ORIGIN`。浏览器只看到一个来源，`config.gd` 读 `window.location.origin`
   就能工作，没有 CORS。源站可以是任何能跑容器的地方，或本机 + cloudflared 隧道。
2. **改写成 Workers + D1**：要把 `server/` 用 JS/TS 重写、SQLite 换 D1 绑定。
   现有 22 项测试和确定性剧情引擎全部作废，两天内不现实。
3. **Cloudflare Containers**：能跑容器，但不在免费额度内。

## 一次演示的最短路径

```bash
# 1) 起后端（本机或 VPS）
.venv/bin/python -m uvicorn server.main:app --port 8000
# 或容器：
docker build -t skilltown-api . && docker run -p 8000:8000 -v skilltown-data:/data skilltown-api

# 2) 用 Cloudflare Tunnel 把它暴露成 https 源站（同一个 Cloudflare 账号，免费）
cloudflared tunnel --url http://127.0.0.1:8000
#    输出形如 https://<random>.trycloudflare.com —— 这就是 API_ORIGIN

# 3) 部署页面（凭据从 ~/.config/skilltown/cloudflare.env 读，不进仓库）
tools/deploy_pages.sh skilltown

# 4) 在 Pages 项目里把 API_ORIGIN 设为第 2 步的地址，然后重新部署一次
```

自定义域名（如免费二级域名）在 Cloudflare DNS 里 CNAME 到 Pages 项目即可；
证书由 Cloudflare 处理。

## GitHub Actions

- `ci.yml`：pytest、客户端静态检查、Godot 导入、单线程 Web 导出、无头集成冒烟
  （真实 GDScript 客户端打真实 API）、HTTP 冒烟，并上传构建产物。
- `deploy-pages.yml`：导出 + 注入代理 worker + `wrangler pages deploy`。
  需要仓库 Secrets：`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`。

## 环境变量

见 `.env.example`。要点：

- `DATABASE_PATH` 必须落在持久卷上（容器里是 `/data`）。没有持久卷时每次重启都会
  清空学习证据，演示中"系统记得你的错误"就会变成假话。
- `ANTHROPIC_API_KEY` 只放服务端。未设置时自由回答走确定性 fallback，响应里
  `feedback_mode` 明确为 `fallback`，不冒充实时 AI。
- `CORS_ORIGINS` 在同源部署下无关紧要；跨源调试才需要。
- 密钥不要提交。仓库里的 `.env` 已被忽略；部署凭据放
  `~/.config/skilltown/cloudflare.env`（chmod 600）。

## 已知边界

- Pages 免费额度对静态资源足够；36MB 的 `index.wasm` 每次访问都要下载，首屏偏慢，
  演示前先让浏览器缓存一次。
- 隧道地址（`trycloudflare.com`）是临时的，重启会变，必须同步更新 `API_ORIGIN`。
  正式演示建议换成固定源站或命名隧道。
- SQLite 单写者：演示级并发够用，多人同时压测会阻塞。
