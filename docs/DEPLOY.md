# 部署：Fly.io 单机 + 持久卷，整站同源

## 结论先说

Fly.io 是这套栈目前最合适的落点：它给**真正的持久卷**，而 SQLite 需要的正是这个。
选它之后架构还能少一跳 —— FastAPI 直接托管 Godot 构建（`WEB_DIR`），页面和
`/api/v1` 天然同源，不需要 Cloudflare Pages 的反代 worker。Cloudflare 只负责
DNS、CDN 和证书。

```
浏览器 ──► Cloudflare（DNS/CDN/TLS，你的免费域名）
             └──► Fly 机器（1 台）
                    ├── FastAPI  /api/v1 + /health
                    ├── 静态构建 /  /index.wasm …
                    └── 持久卷   /data/skilltown.sqlite3
```

## 为什么不能全放 Cloudflare Workers/Pages

后端是 FastAPI（Python）+ 磁盘 SQLite。Workers/Pages 的运行时是 JS/WASM，没有持久
文件系统，跑不了这套代码。改写成 Workers + D1 要重写 `server/`、换掉 SQLite，34 项
测试和确定性剧情引擎全部作废，两天内不现实。Cloudflare Containers 能跑容器但不在
免费额度内。仓库里仍保留 `cloudflare/_worker.js`，作为“页面放 Pages、API 放别处”的
备选路径（见文末）。

## 一次性设置

```bash
brew install flyctl
flyctl auth login                       # 交互式，需要你本人在浏览器里确认

# 1) 创建 app（名字全局唯一，改掉 fly.toml 里的 app = "skilltown"）
flyctl apps create <你的 app 名>

# 2) 创建持久卷（1GB 足够；卷绑定单个机器和可用区）
flyctl volumes create skilltown_data --app <app> --region nrt --size 1

# 3) 模型密钥只作为 Fly secret 注入，不进仓库、不进镜像
flyctl secrets set ANTHROPIC_API_KEY=sk-ant-... --app <app>

# 4) 首次部署（远程构建器，本机不需要 Docker）
tools/deploy_fly.sh <app>               # 导出 Web 构建 → 部署 → 线上冒烟
```

`tools/deploy_fly.sh` 最后会对 `https://<app>.fly.dev` 跑一遍 `tools/smoke_api.py`，
所以部署完成即刻就能知道线上是不是真的通。

## 必须守住的约束：永远只有一台机器

SQLite 单写者，Fly 卷只能挂到一台机器。**不要 `flyctl scale count 2`** —— 第二台
要么挂不上卷，要么拿到一份各自分叉的学习证据。`fly.toml` 里 `min_machines_running = 1`、
`auto_stop_machines = "off"`、`strategy = "immediate"` 就是为此设置的；单机单卷不能
蓝绿或滚动，每次部署有几秒不可用。

## 自定义域名（你的免费二级域名 + Cloudflare）

```bash
flyctl certs create demo.example.org --app <app>      # 输出需要添加的 DNS 记录
```

在 Cloudflare DNS 里按提示加 `CNAME demo → <app>.fly.dev`。橙云（proxied）打开可以
让 Cloudflare 缓存 36MB 的 `index.wasm`，首屏明显更快；如果 Fly 的证书校验因橙云
失败，先关灰云签发证书、再打开橙云。

## 数据与备份

- 学习证据在 `/data/skilltown.sqlite3`，随卷持久化，重新部署不丢。
- Fly 对卷有自动快照（保留期以官网为准）；`flyctl volumes snapshots list <vol-id>`
  查看，`flyctl volumes create --snapshot-id ...` 从快照恢复。
- 演示前后想手动取一份：`flyctl ssh sftp get /data/skilltown.sqlite3 --app <app>`。
- 清库即清所有访客记录；演示重置可以直接删除该文件后重启机器。

## 费用（量级，最终以 Fly 官网为准）

一台 `shared-cpu-1x` / 512MB 常驻大约每月几美元，1GB 卷约 $0.15/月，出站流量按量
计费、单价很低。Fly 已无免费额度，需要绑卡，可能有最低月消费 —— 这几项请你到
控制台确认，我这边的价格信息可能已经过期。省钱的做法是演示结束后把
`auto_stop_machines` 改成 `"suspend"`，机器空闲时挂起、有请求再唤醒（代价是首个
请求多等一会儿，所以路演期间不要开）。

## GitHub Actions

- `ci.yml`：pytest、客户端静态检查、Godot 导入、单线程 Web 导出、无头集成冒烟
  （真实 GDScript 客户端打真实 API）、HTTP 冒烟，并上传构建产物。
- `deploy-fly.yml`：导出 Web 构建 → 远程构建镜像 → `flyctl deploy` → 线上冒烟。
  需要仓库 Secret：`FLY_API_TOKEN`（`flyctl tokens create deploy`）。
- `deploy-pages.yml`：备选路径，把静态构建发到 Cloudflare Pages。

## 环境变量

见 `.env.example`。要点：

- `DATABASE_PATH` 必须落在持久卷上（容器里是 `/data`）。没有持久卷时每次重启都会
  清空学习证据，演示中“系统记得你的错误”就会变成假话。
- `WEB_DIR` 指向镜像里的构建目录（`/app/godot/web`），实现同源。
- `ANTHROPIC_API_KEY` 只作为 Fly secret 注入。未设置时自由回答走确定性 fallback，
  响应里 `feedback_mode` 明确为 `fallback`，不冒充实时 AI。
- `CORS_ORIGINS` 同源部署下留空。
- 密钥不要提交。仓库 `.env` 已忽略；Cloudflare 凭据放
  `~/.config/skilltown/cloudflare.env`（chmod 600）。

## 备选：页面放 Cloudflare Pages，API 放别处

`cloudflare/_worker.js` 会把 `/api/*` 和 `/health` 反代到 Pages 环境变量
`API_ORIGIN`，从而保持同源；`tools/deploy_pages.sh` 负责导出 + 部署。适用于
“页面要吃 Cloudflare 边缘、后端在别的宿主”的情况，代价是多一跳和一个要维护的
`API_ORIGIN`。用 Fly 托管全站时不需要它。

## 已知边界

- 36MB 的 `index.wasm` 每个新访客都要下载；橙云缓存能缓解，首屏仍偏慢，演示前先
  让浏览器缓存一次。
- SQLite 单写者：演示级并发够用，多人同时压测会阻塞。
- 单机部署没有高可用；机器重启期间站点不可用几秒到几十秒。
