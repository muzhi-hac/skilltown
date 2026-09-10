# API 契约草案 v0.1

状态：实现前供 A/B 审核，不代表接口已经可用。B 维护 shared/contracts.ts，A 审核后冻结。全部 API 通过服务端会话确认当前访客，不接受前端传用户 ID 决定权限。

## 固定枚举

- 分类：ethics_compliance / personal_development。
- NPC：alex / sam / mira / jo。
- 技能：clarify_context / conflict_awareness / communicate_boundary。
- 学习状态：unseen / needs_practice / practiced / demonstrated。
- 效果：none / consequence_preview / rewind_available / completed。
- 反馈模式：scripted / ai / fallback。

## 路由

| 路由 | 作用 |
|---|---|
| POST /api/session | 创建游客会话 |
| GET /api/town | 分类、NPC、可用任务和推荐标记 |
| POST /api/attempts | 建立固定场景版本的尝试 |
| GET /api/attempts/:id | 刷新或冲突后恢复本人状态 |
| POST /api/attempts/:id/respond | 选择或自由回答 |
| POST /api/attempts/:id/hint | 获取提示并记录帮助 |
| GET /api/passport | 个人能力、证据和时长 |
| POST /api/recommendations | 生成可进入已有任务的方案 |
| DELETE /api/session | 清除会话及相关学习记录 |

## 回答请求

client_event_id（UUID）、expected_revision（整数）、kind（choice/text）、choice_id 或 text（二选一）。服务端校验节点可用选项和会话归属。同事件键重试返回原结果；不同内容复用同 key 返回 409。

## 回答响应

attempt_id、revision、node、feedback、effect、learning_updates、is_complete、feedback_mode。
node 包含 id/npc_id/category/text/choices/allow_text；不返回正确答案或隐藏 rubric。
learning_updates 包含 skill_id/state/evidence_id/assisted；只由服务端评估流程写入。

## 错误处理

- 401：重新建立会话或提示会话失效。
- 404：尝试不存在或不属于当前会话。
- 409：拉取最新 attempt 后恢复，保留未提交输入。
- 429：等待并保留输入。
- 503：AI 暂不可用，不记为答错；可返回明确标注的固定教学反馈。

## AI 与推荐

自由回答按固定标准评估，并关联用户原文和虚构政策条款。缺证据时追问或标记未验证。推荐先由规则选已有 task_id，AI 解释原因；服务端校验所有 task_id/evidence_id，避免生成不存在的任务。
