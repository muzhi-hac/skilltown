# SkillTown API 接口文档 v1

> 状态：实现契约，已由 FastAPI 与 React 客户端实现。机器可读定义见 [`openapi.yaml`](openapi.yaml)。

## 1. 技术约定

- 后端：FastAPI，业务接口统一使用 `/api/v1`。
- 客户端：React + Vite，通过 fetch 调用 JSON API。
- 鉴权：`POST /api/v1/session` 返回短期 `session_token`；后续请求携带 `Authorization: Bearer <token>`。
- 身份：服务端从 token 解析访客，不接受客户端传入 `employee_id`。
- 内容类型：`application/json; charset=utf-8`；时间为 ISO 8601 UTC，时长单位为秒。
- 动态 ID 使用 UUID；固定 NPC、技能和分类使用下表枚举。
- 前端只渲染服务端状态，不接收隐藏答案、评分标准或能力升级规则。

## 2. 固定枚举

| 类型 | 值 |
|---|---|
| LearningCategory | `ethics_compliance`, `personal_development` |
| NpcId | `alex`, `sam`, `mira`, `jo` |
| SkillId | `clarify_context`, `conflict_awareness`, `communicate_boundary` |
| LearningState | `unseen`, `needs_practice`, `practiced`, `demonstrated` |
| AttemptMode | `screening`, `practice`, `verification` |
| AttemptStatus | `in_progress`, `completed`, `abandoned` |
| Effect | `none`, `consequence_preview`, `rewind_available`, `completed` |
| FeedbackMode | `scripted`, `ai`, `fallback` |

## 3. 路由

| 方法 | 路径 | 鉴权 | 用途 |
|---|---|---:|---|
| GET | `/health` | 否 | liveness 健康检查 |
| GET | `/ready` | 否 | RAG readiness：hybrid / sparse / unavailable |
| POST | `/api/v1/session` | 否 | 创建匿名试玩会话 |
| DELETE | `/api/v1/session` | 是 | 删除本会话及学习记录 |
| GET | `/api/v1/town` | 是 | 分类、NPC、任务和推荐状态 |
| POST | `/api/v1/attempts` | 是 | 创建任务并冻结场景版本 |
| GET | `/api/v1/attempts/{attempt_id}` | 是 | 刷新或冲突后恢复状态 |
| POST | `/api/v1/attempts/{attempt_id}/respond` | 是 | 提交选择或自由回答 |
| POST | `/api/v1/attempts/{attempt_id}/hint` | 是 | 请求提示并标记 assisted |
| POST | `/api/v1/attempts/{attempt_id}/rewind` | 是 | 从后果预演倒带 |
| POST | `/api/v1/attempts/{attempt_id}/activity` | 是 | 记录开始、心跳、暂停与恢复 |
| GET | `/api/v1/passport` | 是 | 获取能力摘要与支持证据 |
| POST | `/api/v1/recommendations` | 是 | 生成 2–3 个有证据的任务推荐 |

完整 schema、状态码和示例以 `openapi.yaml` 为准。

## 4. 会话示例

```bash
curl -sS -X POST http://localhost:8000/api/v1/session \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Demo learner"}'
```

```json
{
  "session_token": "session-token-value",
  "session": {
    "id": "02dcc3ab-00b2-42e6-88ee-c519c07d1e65",
    "display_name": "Demo learner",
    "expires_at": "2026-09-11T15:00:00Z"
  }
}
```

Godot 在运行时保存 token；Web 刷新恢复时可以写入 `user://session.json`。token 不写入 URL、仓库或日志。`DELETE /api/v1/session` 成功返回 `204`，服务端级联清除该会话的任务、事件、证据、能力投影和推荐。

## 5. 核心交互

### 创建任务

```http
POST /api/v1/attempts
Authorization: Bearer TOKEN
Content-Type: application/json

{"scenario_id":"dinner-invitation","mode":"practice"}
```

响应包含 `attempt_id`、`revision: 0`、固定的 `scenario_version` 和首个 `node`。

### 提交选择

```json
{
  "client_event_id": "52135b80-985b-49ca-8fc5-b529d4e61cb8",
  "expected_revision": 0,
  "kind": "choice",
  "choice_id": "ask_context"
}
```

### 提交自由回答

```json
{
  "client_event_id": "5a020b27-1112-4b2d-aa9e-0c204bed6484",
  "expected_revision": 2,
  "kind": "text",
  "text": "我会先暂停接受邀请，确认谁付款以及续约审批是否会受到影响。"
}
```

`feedback_mode` 表示反馈来源；`assessment_status` 区分 `assessed`、`deferred` 与 `not_requested`。确定性 fallback 只精确匹配审核答案；其余措辞为 `deferred`，不写入学习证据。

### 施压弧（pressure arc）

带 `pressure` 的情境模块里，节点不是一问一答，而是一段最多 `max_turns`（当前为 4）轮的对话：

- `node.line` 是对方走进来说的第一句话；`node.text` 仍是情境说明，不是谁说的。
- `dialogue[]` 是本次 attempt 的完整对话记录（`node_id` / `speaker` / `text` / `resolved`），刷新和 `GET /attempts/{id}` 都会原样返回，前端据此还原对话。
- `pressure` 给出 `turn`（当前节点已用掉的回合）、`max_turns` 和 `active`。
- **答得不到位且还没用完回合**：节点不动，`feedback` 为 `null`，`learning_updates` 为空 —— 不公布判定、不给答案，只回一句对方升级后的话。
- **答对**：对方当场退让，按 `pass` 分支推进，正常写证据。
- **回合用尽**：按 `miss`/`overgeneralized` 分支推进（通常进入后果节点），这时才写证据，`interpretation` 里带上"撑了几轮、最后是顶住还是让步"。
- `POST /rewind` 会清掉该节点的对话并重新说开场白，即重新开始一段施压。

**追问（probe）**：节点的 `withheld` 事实不下发给前端，只有问了才会出现在对话里。

- 模型只判断"这一轮是在问还是在决定"，以及问的是哪个 `withheld.id`；**说出口的原话来自内容文件**，模型不参与措辞，所以它改不了数字。
- `dialogue[].kind` 区分 `line`（开场/施压台词）、`probe`（学习者在问）、`answer`（对方回答问题）、`decision`（学习者在决定）。
- **追问不计回合**：`pressure.turn` 只数 `decision`。每个节点最多 4 次追问，超出后对方不再回答，按施压回合处理。
- 问了内容里没有的东西，得到的是人设里的 `deflect` 一句敷衍。
- 不问就决定不会被从宽：按现有信息评分，证据的 `interpretation` 写明"decided without asking anything"。

人设（`persona`）、升级阶梯和台词只存在于服务端内容里，`/api/v1/town` 与任何响应都不下发。

### 幂等与冲突

- `client_event_id` 在一个会话内唯一。
- 相同 ID 和 payload 重试返回第一次响应，不重复写入。
- 相同 ID 配不同 payload 返回 `409 idempotency_conflict`。
- `expected_revision` 过期返回 `409 revision_conflict`；客户端随后调用 `GET /attempts/{id}`。
- 场景版本变更返回 `409 scenario_version_mismatch`；客户端创建新 attempt，旧证据保留。
- UI 请求期间禁用提交按钮，服务端仍执行全部幂等检查。

## 6. 能力与证据规则

- `practice` 中完成任务最高更新为 `practiced`。
- `verification` 使用未见变体、没有提示且满足标准时才更新为 `demonstrated`。
- 请求提示后，该 attempt 的 `assisted` 永久为 `true`。
- 选择正确但解释暴露误解时，可以进入澄清节点，不立即升级能力。
- 模型输出无效、缺少证据或超时，保持原状态并显示 fallback 或澄清问题。
- Evidence 保存原文或选项、场景节点、虚构政策条款和 assisted，不保存个人品格推断。

## 7. Godot 调用样例

```gdscript
func respond_choice(attempt_id: String, revision: int, choice_id: String) -> void:
    var request := HTTPRequest.new()
    add_child(request)
    request.request_completed.connect(_on_respond_completed.bind(request))
    var body := JSON.stringify({
        "client_event_id": Uuid.v4(),
        "expected_revision": revision,
        "kind": "choice",
        "choice_id": choice_id
    })
    var headers := [
        "Content-Type: application/json",
        "Authorization: Bearer %s" % SessionStore.token
    ]
    request.request(
        API_BASE + "/api/v1/attempts/%s/respond" % attempt_id,
        headers,
        HTTPClient.METHOD_POST,
        body
    )

func _on_respond_completed(
    result: int,
    response_code: int,
    _headers: PackedStringArray,
    body: PackedByteArray,
    request: HTTPRequest
) -> void:
    request.queue_free()
    if result != HTTPRequest.RESULT_SUCCESS:
        show_retry("网络连接异常，回答仍保留在输入框中")
        return
    var payload = JSON.parse_string(body.get_string_from_utf8())
    if response_code == 200:
        TrainingState.apply_server_response(payload)
    elif response_code == 409:
        restore_attempt(payload["error"]["latest_attempt_url"])
    else:
        show_api_error(payload)
```

`Uuid.v4()` 与 `SessionStore` 是计划新增的本地工具，不是 Godot 内置 API。一个 `HTTPRequest` 节点同一时刻只处理一个请求；对话、恢复和心跳使用不同节点，或动态创建后在完成时释放。

## 8. 标准错误

```json
{
  "error": {
    "code": "revision_conflict",
    "message": "Attempt revision is stale.",
    "request_id": "req-8f49a7",
    "retryable": true,
    "latest_attempt_url": "/api/v1/attempts/02dcc3ab-00b2-42e6-88ee-c519c07d1e65"
  }
}
```

| 状态 | 场景 | Godot 行为 |
|---:|---|---|
| 400 | 当前节点不允许该动作 | 显示消息并保留输入 |
| 401 | 会话缺失或过期 | 创建新会话并说明旧进度已失效 |
| 404 | 资源不存在或不属于会话 | 返回地图并刷新任务 |
| 409 | revision、幂等或场景版本冲突 | 拉取最新 attempt，版本冲突时重开任务 |
| 422 | FastAPI 请求验证失败 | 开发阶段记录并修正契约 |
| 429 | 达到会话调用限额 | 按 `Retry-After` 等待 |
| 503 | 强制 dense RAG 暂不可用 | 等待 `/ready` 恢复后重试 |

## 9. FastAPI 文件映射

- `server/main.py`：FastAPI app、CORS、健康检查与路由挂载。
- `server/api/models.py`：与 OpenAPI schema 对应的 Pydantic 模型。
- `server/api/routes.py`：HTTP 编排，不包含评分规则。
- `server/core/scenario_engine.py`：节点、分支、revision、rewind。
- `server/core/evaluator.py`：选择题规则和自由回答评估。
- `server/core/memory.py`：证据事件与能力投影。
- `server/core/recommendations.py`：规则选任务、AI 解释推荐原因。
- `server/storage.py`：SQLite 会话和事务。

FastAPI 生成的 `/openapi.json` 应与 `docs/openapi.yaml` 做结构 diff；不一致时测试失败。

## 10. 当前文档验证

```bash
python - <<'PY'
from pathlib import Path
import yaml
spec = yaml.safe_load(Path("docs/openapi.yaml").read_text())
assert spec["openapi"] == "3.1.0"
operations = [
    operation["operationId"]
    for path in spec["paths"].values()
    for method, operation in path.items()
    if method in {"get", "post", "delete", "put", "patch"}
]
assert len(spec["paths"]) == 12
assert len(operations) == len(set(operations)) == 13
print("OpenAPI structure OK: 12 paths, 13 operations")
PY
```

后端完成后追加 `pytest server/tests -q` 与 `curl -fsS http://localhost:8000/ready`。
