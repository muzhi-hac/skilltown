# SkillTown API 接口文档 v1

> 状态：实现契约，接口尚未编码。机器可读定义见 [`openapi.yaml`](openapi.yaml)。

## 1. 技术约定

- 后端：FastAPI，业务接口统一使用 `/api/v1`。
- 客户端：Godot 4.5 Web Export，通过 `HTTPRequest` 调用 JSON API。
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
| GET | `/health` | 否 | 部署健康检查 |
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

`feedback_mode` 表示反馈来源：`ai` 为真实模型理解，`scripted` 为预审选择题反馈，`fallback` 为模型异常后的固定知识卡。fallback 不产生负面学习判定。

### 幂等与冲突

- `client_event_id` 在一个会话内唯一。
- 相同 ID 和 payload 重试返回第一次响应，不重复写入。
- 相同 ID 配不同 payload 返回 `409 idempotency_conflict`。
- `expected_revision` 过期返回 `409 revision_conflict`；客户端随后调用 `GET /attempts/{id}`。
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
| 409 | revision 或幂等冲突 | 拉取最新 attempt |
| 422 | FastAPI 请求验证失败 | 开发阶段记录并修正契约 |
| 429 | 达到会话调用限额 | 按 `Retry-After` 等待 |
| 503 | AI 服务暂不可用 | 显示 fallback，不判员工答错 |

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
assert len(spec["paths"]) == 11
assert len(operations) == len(set(operations)) == 12
print("OpenAPI structure OK: 11 paths, 12 operations")
PY
```

后端完成后追加 `pytest server/tests -q` 与 `curl -fsS http://localhost:8000/health`。
