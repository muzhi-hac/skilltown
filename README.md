# SkillTown

两人、两天的 AI 教育黑客松：一个记得你为什么选错、只教你还没掌握内容的网页学习小镇。

## 当前状态

第一个纵切可在本机跑通，且**网页构建已实测**：

- FastAPI 提供全部 12 个接口，SQLite 保存匿名会话；`server/tests` 12 项通过。
- Godot 4.5.stable Web 导出成功（GL Compatibility + 单线程模板，已核对导出的
  `index.wasm` 与 `web_nothreads_release/godot.wasm` 哈希一致，因此不需要
  COOP/COEP 跨源隔离头）。
- FastAPI 同源挂载该构建：`/` 返回页面、`/index.wasm` 带 `application/wasm`、
  `/api/v1/*` 不被静态挂载遮挡。
- 无头集成冒烟用真实 GDScript 客户端打通：点击 Alex → 龙虾任务 → 补齐信息记录证据
  → 答错触发后果预演 → 倒回出错的决策点 → 完成 → 学习护照 → 换 Jo 走自由回答支线。

尚未验证的部分（不要当成已完成）：

- **没有在真实浏览器里人工点过**：移动/E 键交互、窄屏、刷新恢复、按钮防重复只有无头
  断言背书；页面也还没部署到公网。
- 自由回答目前走确定性 fallback 评估器：未配置模型时明确返回
  `feedback_mode: "fallback"`，不冒充实时 AI。真实模型调用尚未接入。
- `timing.active_seconds` 仍为 0：活动事件已入库，但还没聚合成时长。
- Mira 的伦理复盘任务只有入口文案，尚无辅导内容。

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python -m pytest server/tests -q                    # 12 passed

# 后端 + 已构建的网页（同源）
.venv/bin/python -m uvicorn server.main:app --reload          # http://127.0.0.1:8000
python3 tools/smoke_api.py                                    # 真实 HTTP 冒烟，部署后换成线上 URL
```

Godot 客户端在 `godot/`（Godot 4.5.stable，`GODOT` 指向本机可执行文件）：

```bash
GODOT=/Applications/Godot.app/Contents/MacOS/Godot
$GODOT --headless --path godot --import                        # 导入资源，检查脚本解析
$GODOT --headless --path godot --export-release "Web" web/index.html
$GODOT --headless --path godot res://tests/headless_flow.tscn  # 需后端已在 8000 端口
python3 tools/check_godot_client.py                            # 静态一致性检查（不需要 Godot）
```

`godot/web/` 是生成物，不提交、不手工编辑。`tools/check_godot_client.py` 只查节点路径、
`APIClient`/`Config` 成员和信号参数个数，替代不了上面两条 Godot 命令。

## 目标体验

- 点击 NPC，或 WASD / 方向键移动、靠近按 E。
- 两个醒目分类：🛡️ 伦理与合规、🌱 个人发展。
- 合规主线：商务宴请 → 风险揭示 → 后果预演 → 定向反馈 → 新情境复测。
- 三题轻量筛查、跨 NPC 学习记忆、个人学习护照与可点击学习方案。
- 无主管端、排行榜或自动绩效评价；虚构培训政策不作为法律结论。

## 技术方向

Godot 4.5（GDScript，Compatibility renderer，单线程 Web Export）/ FastAPI + Pydantic / SQLite。Godot 构建产物与 `/api` 同源发布，模型密钥仅存服务端。

## 两人分工

| 角色 | 负责 | 目录 |
|---|---|---|
| A：@muzhi-hac | Godot Web、地图、交互、对话、结果、方案 UI、发布操作 | `godot/`，根部署文件 |
| B：@Isso-W | FastAPI、剧情、政策、评估、记忆、推荐、会话隔离 | `server/`，API 模型维护 |

请从 [Issues](https://github.com/muzhi-hac/skilltown/issues) 按 owner:A / owner:B / owner:joint 筛选任务。B 的仓库访问需先接受协作邀请。

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
