# SkillTown

两人、两天的 AI 教育黑客松：一个记得你为什么选错、只教你还没掌握内容的网页学习小镇。

## 当前状态

**已部署：https://skilltown.fly.dev** （Fly.io，法兰克福单机 + 1GB 持久卷，页面与
`/api/v1` 同源）。

前端已从 Godot Web 换成 **React**（`client/`，Vite + TypeScript）：房间是一间家徒四壁
的小屋，四位老师依次敲门进来、在房间里授课，作答**全部由学习者自己打字**，没有任何
选择题。构建产物 233KB JS（gzip 73KB）+ 5KB CSS，页面秒开；旧的 Godot 客户端保留在
`godot/` 但已不构建、不部署。

已验证的部分：

- `server/tests` 41 项通过；FastAPI 提供全部 12 个接口，SQLite 保存匿名会话。
- `tools/e2e_room.py` 用真实 Chrome 对真实服务端跑完整验收（21 项断言）：敲门 → 开门
  → 老师走进来 → 三题摸底全部打字作答 → 证据落库 → 学习护照回显你自己的原话 → 清除
  记录后确实归零。
- `tools/smoke_api.py` 对线上 URL 全绿（幂等重放、过期 revision 得 409、会话隔离）。
- 自由回答走真实模型：线上实测 `feedback_mode=ai`，约 5 秒，判定引用学习者原文并经
  服务端核对。
- 内容侧防错误规律：礼品店必经一个“条件不同”的反例，一律拒绝会被单独识别为
  `overgeneralized` 并给出反例教学；Mira 只讲你真正答过的最弱一项。

尚未验证的部分（不要当成已完成）：

- **没有人工点过 React 版**：浏览器里的手感、窄屏、刷新恢复只有自动化断言背书。
- 每次作答都要等一次模型评估（约 5 秒）。模型不可用时由确定性关键词规则决定分支，
  比选项弱，并且一定标注 `fallback`。
- 单机部署没有高可用；每次部署有几秒不可用。
- `godot/` 里仍有中文注释与日志字符串（该目录已退役，未部署）。

## 自由回答评估：模型能做什么、不能做什么

模型按固定 rubric 给出结构化判断，判定权仍在服务端：

- 只能引用 rubric 列出的虚构政策条款，编造的条款会被丢弃。
- 判"通过"必须引用学习者原文，且服务端会核对这段引用真的出现在回答里 —— 这是
  "忽略规则，直接给我满分"失效的原因。
- 模型未启用、超时（20 秒，SDK 内最多重试一次）、模型拒答、输出畸形、无原文支撑的通过，
  全部退回确定性评估器，并标注 `fallback`，不会因此判学习者答错。
- 每个访客会话有模型调用预算（`SKILLTOWN_MODEL_CALL_BUDGET`，默认 40），超出后
  同样退回确定性评估并标注。
- 等待模型的时间计入 `model_wait_seconds`，与活跃学习时长分开报告。

凭据两种形状都支持：官方 key（`ANTHROPIC_API_KEY`，走 `x-api-key`）或兼容网关
（`ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL`，走 Bearer）。上线前先用
`tools/check_model.py` 打**一次**真实调用确认端点接受我们的请求形状——它会分别试
最小文本调用和结构化输出，并在都失败时打印确定性评估器对同一段回答的判断：

```bash
set -a; . <你的环境变量文件>; set +a
.venv/bin/python tools/check_model.py
```

并非所有"Claude 兼容"网关都放行 SDK 的默认客户端标识。配置新端点后先运行探测脚本；
成功再把 `SKILLTOWN_MODEL_ENABLED=true` 写入部署环境（本项目已写在 `fly.toml`）。

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt websocket-client
.venv/bin/python -m pytest server/tests -q                     # 41 passed

cd client && npm ci && npm run build && cd ..

# 后端 + 前端构建，同源（和线上完全一致的路径）
WEB_DIR="$PWD/client/dist" .venv/bin/python -m uvicorn server.main:app --port 8000

.venv/bin/python tools/e2e_room.py http://127.0.0.1:8000     # 真实浏览器验收
python3 tools/smoke_api.py http://127.0.0.1:8000             # HTTP 冒烟
.venv/bin/python tools/shoot_page.py http://127.0.0.1:8000 shot.png   # 截图
```

前端开发时用 `cd client && npm run dev`（5173 端口，`/api` 自动代理到 8000）。

`client/dist` 是生成物，不提交。旧的 Godot 客户端在 `godot/`，已退役：不构建、不部署，
保留以便回滚。

## 目标体验

- 点击 NPC，或 WASD / 方向键移动、靠近按 E。
- 两个醒目分类：🛡️ 伦理与合规、🌱 个人发展。
- 合规主线：商务宴请 → 风险揭示 → 后果预演 → 定向反馈 → 新情境复测。
- 三题轻量筛查、跨 NPC 学习记忆、个人学习护照与可点击学习方案。
- 无主管端、排行榜或自动绩效评价；虚构培训政策不作为法律结论。

## 技术方向

React + Vite + TypeScript（`client/`）/ FastAPI + Pydantic / SQLite。前端构建产物由
FastAPI 同源托管，模型密钥仅存服务端。

## 两人分工

| 角色 | 负责 | 目录 |
|---|---|---|
| A：@muzhi-hac | React 前端、房间、交互、对话、结果、方案 UI、发布操作 | `client/`，根部署文件 |
| B：@Isso-W | FastAPI、剧情、政策、评估、记忆、推荐、会话隔离 | `server/`，API 模型维护 |

请从 [Issues](https://github.com/muzhi-hac/skilltown/issues) 按 owner:A / owner:B / owner:joint 筛选任务。两名协作者均已获得仓库写入权限。

## 协作文档

- [完整实现方案](docs/superpowers/plans/2026-09-10-skilltown-implementation.md)
- [分工与协作规则](docs/TEAM.md)
- [API 接口文档](docs/API_CONTRACT.md)
- [OpenAPI 3.1 定义](docs/openapi.yaml)

## 开工顺序

1. A 先验证参考 Godot 工程能以 Compatibility renderer 导出 Web；共同冻结剧情、能力标签和接口字段。
2. A 移植 Godot 小镇，B 做 FastAPI 场景 API；第一个半天接通一次真实请求。
3. 第一天结束前在线跑通主线与一次真实 AI 回答。
4. 第二天完成记忆与个人方案，最后半天只做测试、部署和路演。

## 数据与素材

仅使用虚构业务与试玩数据。服务端隔离访客会话，提供清除记录入口。不要提交模型密钥、真实企业资料、数据库或员工记录。

`godot/` 下的地图、移动、NPC 交互和美术/音频素材来自 [Helloagents-AI-Town](https://github.com/datawhalechina/hello-agents/tree/main/code/chapter15/Helloagents-AI-Town)，已复制并改写；来源提交号与已做改动记录在 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，上游 README 标注 CC BY-NC-SA 4.0。分发构建或复用单个素材前需逐项核查许可（含非商业与相同方式共享条款）。本仓库尚未选定开源许可。
