# RAG and Evaluation Transparency Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in the current task. Steps use checkbox (`- [ ]`) syntax for tracking. No parallel delegation is required.

**Goal:** 让用户明确知道本次回答如何检索依据、由 AI 还是审核示例完成评估，以及结果是否通过引用校验，同时保持右侧页面简洁。

**Architecture:** 检索器和评估器各自返回本次调用的结构化事实，路由组装一份绑定作答前节点的 processing trace，并随答案结果原子持久化。前端仅展示该 trace，不从引用卡片、全局 readiness 或反馈文案猜测执行方式。

**Tech Stack:** 现有 Python / FastAPI / Pydantic / SQLite、React / TypeScript；复用现有 BM25、model2vec、RRF，不引入向量数据库、流式接口或新评分模型。

---

## 0. 与现有方案的关系

- 本文是待执行方案，不是已实现或已测量的报告。
- 配套 UI 基础方案：`/Users/wang/Documents/ChatGPT/AI hacthon/docs/superpowers/plans/2026-09-11-lesson-ux-p1.md`。
- 保留自由回答、默认折叠资料和固定作答区。技术详情放在可滚动阅读区，不增加作答区高度。
- 保留题目 facts/rubric/knowledge 白名单、全文上下文、固定分支和现有评分结果。检索 query 仍不使用学习者答案。
- 不将此次改动宣传为“根据答案动态检索整个知识库”；当前检索主要给本题预审依据排序，未命中条款通过 ID 补齐。
- 不重构模型预算及费用计数，不新增记忆，不更改推荐算法；只准确报告本次评估调用。

## 1. 用户体验合同

### 首屏摘要

| 实际结果 | 主文案 |
|---|---|
| AI 结果校验通过 | AI 评估 · 引用 N 条依据 |
| 完整审核示例匹配成功，包括匹配到错误答案示例 | 审核示例匹配 · 引用 N 条依据 |
| 备用评估未匹配完整示例 | 暂未完成评估 · 本次未记录学习结果 |
| 旧选择接口的固定分支 | 固定规则反馈 |
| 尚未回答 | 不显示评估摘要；资料标为“本题预设依据” |

“审核示例匹配”不等于回答正确；通过/待练习由原反馈呈现。引用 N 从最终反馈的去重 clause_id 计算，不使用候选数量冒充引用数量。

### 折叠技术详情

```text
▸ 本次处理详情
  对应问题：上一题的简短题干
  依据范围：本题预设条款
  查询来源：题目、场景条件、评分问题（不使用你的回答）
  检索方式：BM25 + 向量融合 / 仅关键词 / 仅向量 / 无搜索命中
  搜索命中：条款编号列表
  指定条款补齐：条款编号列表
  最终引用：条款编号列表
  评估方式：AI / 审核示例 / 固定分支
  AI 输出校验：通过 / 未通过 / 未执行
  耗时：依据准备 X ms · 评估 Y ms
```

- 不展示完整 rubric、标准答案、完整评分 prompt、学习者原文副本、密钥、内部 URL、文件系统路径或原始异常。
- “校验通过”只表示引用范围与输出结构等程序检查通过，不表示法规权威认证或语义绝对正确。
- 提交中只显示“正在处理回答…”。现有接口不是流式，禁止用定时动画假称当前已完成检索/正在校验。
- 展示在反馈卡内，绑定刚提交的问题；服务端可能已经返回下一题，不能把旧 trace 标在下一题资料上。

## 2. API 合同：新增可空 processing

在 AttemptResponse 新增 `processing: ProcessingTrace | None = None`。创建任务、旧记录没有 trace 时返回 null。旧客户端忽略新增字段即可。

建议 Pydantic 模型（所有枚举以这些取值为唯一来源，TS 保持一致）：

```python
class PassageTrace(StrictModel):
    clause_id: str
    origin: Literal["search", "anchor"]
    sparse_rank: int | None = Field(default=None, ge=1)
    dense_rank: int | None = Field(default=None, ge=1)
    fused_rank: int | None = Field(default=None, ge=1)

class RetrievalTrace(StrictModel):
    query_source: Literal["node_context"] = "node_context"
    mode: Literal["hybrid", "sparse", "dense", "none"]
    passages: list[PassageTrace]
    grounding_ms: float = Field(ge=0)
    search_ms: float = Field(ge=0)
    dense_status: Literal["used", "unavailable", "error", "no_hits"]

class EvaluationTrace(StrictModel):
    method: Literal["ai", "reviewed_example", "unassessed", "scripted"]
    reason: Literal[
        "none", "disabled", "missing_credentials", "budget_exhausted",
        "circuit_open", "timeout", "request_error", "invalid_output",
        "validation_failed"
    ]
    validation: Literal["passed", "failed", "not_run"]
    model_invoked: bool
    evaluation_ms: float = Field(ge=0)
    model_ms: float | None = Field(default=None, ge=0)
    cited_ids: list[str]

class ProcessingTrace(StrictModel):
    schema_version: Literal[1] = 1
    answer_revision: int = Field(ge=1)
    scenario_version: str
    node_id: str
    question: str
    retrieval: RetrievalTrace | None = None
    evaluation: EvaluationTrace
```

- answer_revision 是此次 respond 成功产生的 revision；hint 可以增加当前 revision，但不修改原 trace 的 answer_revision。
- question 使用作答前 node.text，不用 rubric.question，不包含隐藏答案。
- search_ms 是 grounding_ms 的组成部分，两者不要相加。model_ms 是 evaluation_ms 的组成部分，也不要相加。
- model_invoked 仅表示本次进入 SDK 请求方法；SDK 内部重试数量和计费另行统计，不把它标成真实 HTTP 请求次数。
- method=unassessed 必须对应 assessment_status=deferred 且 learning_updates 为空；method=ai 必须 validation=passed；脚本分支 retrieval=null。

## 3. 文件职责

| 绝对路径 | 改动 |
|---|---|
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/knowledge.py` | 新增带结果元数据的搜索函数，保留旧 search 包装 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/grounding.py` | 带入实际搜索来源/排名/耗时，修复 hybrid 误标 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/evaluator.py` | EvaluationResult 增加评估元信息 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/model_evaluator.py` | 分支原因、实际调用标识、计时与校验结果 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/api/models.py` | ProcessingTrace 及子模型 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/api/routes.py` | 组装 trace，绑定作答前节点 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/storage.py` | trace 随当前展示状态原子存储 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/api.ts` | 对齐新增类型 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/ProcessingDetails.tsx`（新） | 摘要、技术详情、解释文案 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/Lesson.tsx` | 在反馈中挂载新组件、移除误导标签 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/styles.css` | 紧凑样式与详情滚动 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_retrieval_trace.py`（新） | 搜索来源、排名与结果不变 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_grounding.py` | 白名单、补齐和 trace 一致性 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_model_evaluator.py` | 各备用原因、校验、计时 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_api.py` | 持久化、恢复、幂等与隔离 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_contract.py` | 新字段/枚举/可空契约 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/ProcessingDetails.test.tsx`（新） | 文案、折叠、旧响应兼容 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/docs/openapi.yaml`、`/Users/wang/Documents/ChatGPT/AI hacthon/docs/API_CONTRACT.md` | 同步协议和语义 |

## 4. Task A：让检索器返回真实执行信息

- [ ] 在 test_retrieval_trace.py 先写失败测试：稀疏/向量同时有结果、向量缺失、向量查询异常、只有向量有结果、空 query、无命中。
- [ ] knowledge.py 新增 `search_with_trace(query, limit=3, within="")`，返回不可变结果对象，含最终 chunks、各 ID 的 sparse/dense/fused rank、实际 mode、dense_status、search_ms。rank 均从 1 开始。
- [ ] 将旧 search 算法原样移动至新函数：保留 depth=max(limit*3,6)、RRF_K=60、DENSE_WEIGHT=2.0 和原 tie-break；不要为了元信息再次调用搜索或编码。
- [ ] 旧 search 仅执行 `return list(search_with_trace(query, limit, within).chunks)`，保证现有基准和其他调用者兼容。
- [ ] mode 由本次贡献结果的通道决定：双方有结果 hybrid；只有 sparse 为 sparse；只有 dense 为 dense；最终没有命中为 none。模型已加载不等于本次使用向量，禁止从 /ready 推断。
- [ ] 搜索元信息只存在本次返回值，不用全局 last_trace；保留现有全局 runtime failure 机制，但它不承载会话、query 或条款排名。
- [ ] 测试固定 fake ranking 下结果顺序与旧算法一致，搜索/编码各执行一次，异常按原有策略处理。生产强制 dense 失败仍按现有路由返回 503，不改成继续评分。

## 5. Task B：将 trace 接入 grounding

- [ ] build_context 调用 search_with_trace，原有 query 构造、节点知识白名单、exact 补齐逻辑保持不变。更新现有 monkeypatch 测试，避免还在 mock 旧 search 导致假通过。
- [ ] Passage 的 retrieval 字段改为 `search / anchor`，通道排名独立记录，不再用 hybrid 同时表示“搜索命中”和“实际检索模式”。
- [ ] 只在最终实际装入 EvaluationContext 的 passages 上返回 trace；被白名单排除的候选不出现在前端“使用依据”中。
- [ ] anchor 补齐项所有 rank 为 null；search 项保留对应搜索排名。补齐不算检索命中；最终可用依据数量由去重后的 passages 计算。
- [ ] grounding_ms 用 perf_counter 包围整个 build_context，含锚点读取与搜索；保留 search_ms 独立值。使用可注入 clock 或 monkeypatch perf_counter 做测试，不硬编码机器耗时。
- [ ] 测试：搜索命中域外条款→过滤，节点条款补齐；重复结果去重；纯 sparse 标 sparse；更换学习者回答不改变 query；加入 trace 后 context 全文、允许引用集合和顺序不变。

## 6. Task C：评估路径准确分类

- [ ] EvaluationResult 增加内部元信息对象；不把新字段传入模型 prompt，不要求模型自报执行方式、原因或耗时。
- [ ] build_evaluator 区分 disabled 和 missing_credentials，并给备用评估器配置相应 reason；直接调用确定性评估器的单元测试可使用 reason=disabled。
- [ ] ClaudeTextEvaluator 的分支设置：预算禁止→budget_exhausted；熔断→circuit_open；超时→timeout；网络/SDK错误→request_error；JSON/结构化输出失败→invalid_output；本地引用或通过条件校验失败→validation_failed。
- [ ] 用 dataclasses.replace 将调用元信息附加到备用结果，保留原 passed/assessed/outcome/feedback，不重写评分。完整示例匹配设置 method=reviewed_example，未匹配设置 unassessed。
- [ ] `_verified()` 成功：method=ai、validation=passed；结构可解析但本地验证失败：validation=failed；未进入验证：not_run。失败原因只返回枚举，不回传原始异常。
- [ ] model_ms 仅包围一次 `_ask` 的整个 SDK 调用和解析，异常时也在 finally 计时；未调用为 null。evaluation_ms 包围完整 evaluator.evaluate，包含模型等待、验证和备用匹配。
- [ ] 保留现有超时/重试/熔断配置，不在本包修预算计数。文档明确不提供 token、费用或实际重试次数统计。
- [ ] 为每个原因写独立 fake-client 测试，验证“调用失败再匹配示例”仍 model_invoked=true；预算阻止调用为 false；所有 unassessed 不记录学习结果。

## 7. Task D：API、存储、刷新与幂等

- [ ] models.py 按第 2 节添加模型；routes.respond 在拿到 evaluated 后构造 trace，始终使用跳转前 node_id/question/scenario_version，answer_revision=expected_revision+1。
- [ ] cited_ids 使用最终 feedback.policy_clauses 的去重 ID。AI 和确定性分支的最终引用可能不同，不能直接照抄所有 context IDs。
- [ ] `_attempt_response` 增加 processing 输出；初次打开、hint 的独立响应不伪造 trace。选择分支可生成 method=scripted、retrieval=null 的 trace。
- [ ] 复用六项 P1 方案的 presentation_json，将 processing 同 feedback/effect 一起在 apply_transition 的事务内写入，并进入 events.response_json。若基础方案尚未实施，先完成其 Task E1，不另建第二套快照表。
- [ ] GET 从服务端持久化恢复 processing；hint 保留最近 trace；rewind 清理 trace；新 attempt 为 null。旧记录缺失时前端显示“此记录没有处理详情”，不猜测排名和原因。
- [ ] 同 client_event_id 重放直接返回原 trace，不重复搜索/模型调用，不重新计算毫秒数；409 不将旧 trace 附到新回答上。
- [ ] 测试 GET 后 trace 完整相同、提示后仍绑定旧 answer_revision、回退清空、跨 session 读取被阻止、幂等计数为一次、事务失败不残留 trace 或新证据。
- [ ] 同步 openapi.yaml，扩展 test_contract.py，比较新增 schemas 的 properties/required/enum/nullability；仅 operationId 一致不足以通过。

## 8. Task E：前端简洁展示

- [ ] api.ts 添加 ProcessingTrace 和可空 processing 字段；兼容服务器未返回该字段的旧响应。
- [ ] ProcessingDetails 接收 `processing: ProcessingTrace | null | undefined` 和反馈；摘要按第 1 节映射。没有 trace 时 AI 可沿用旧 ai 标签，其余统一“评估反馈”，不推断备用原因。
- [ ] `<details>` 默认关闭，用 summary 提供“本次处理详情”；按 schema 展示数据，reason 转成固定用户文案。展示搜索命中/指定补齐时附简短解释，不展示整段引用第二遍。
- [ ] 渲染原则示意：

```tsx
const methodLabels = {
  ai: "AI 评估",
  reviewed_example: "审核示例匹配",
  unassessed: "暂未完成评估",
  scripted: "固定规则反馈",
};
// processing 为空时仅呈现兼容摘要；非空才读取 processing.evaluation。
// 始终通过 React 文本节点渲染题干、ID、原因标签。
```

- [ ] 将组件放入 Lesson 的 feedback 内，资料仍由 ReferencePanel 展示；不将 processing 放进固定 answer 区。按 node_id+answer_revision 重置详情折叠，hint 不强制重置。
- [ ] 主摘要标注结果方式但不把“AI”本身涂成通过状态。deferred 用中性色提醒，只有真实评分结果决定正确/待练习颜色。
- [ ] 毫秒格式：不足 1ms 显示“<1ms”；较大值可转秒；缺失显示“未记录”，绝不填 0。不把 SDK 用时称为纯模型推理时间。
- [ ] 单元测试所有方式、原因、旧响应、默认关闭、题目归属、零/空耗时和重复引用计数。展开后长 ID 换行，固定提交按钮仍首屏可见。

## 9. 验收与交付

### 必测矩阵

| 场景 | 预期 |
|---|---|
| hybrid + 正常模型 | hybrid / ai / passed，展示实际引用 |
| dense 缺失且开发允许降级 | sparse，不冒称 hybrid |
| 搜索没命中指定条款 | anchor 补齐，不伪装搜索结果 |
| AI 关闭 + 完整示例匹配 | reviewed_example / disabled / not_run |
| AI 关闭 + 自由改写 | unassessed / deferred / 无学习证据 |
| 超时 + 示例匹配 | reviewed_example / timeout / model_invoked=true |
| 模型伪造引用 | validation_failed / failed，进入原备用路径 |
| 强制 dense 运行异常 | 503；没有成功评估 trace |
| 重复提交同事件 | 原响应和 trace，不再检索与调用 |
| 刷新、提示、回退 | 分别还原、保留、清除 trace |
| 下一题已出现 | trace 仍注明上一题，不误归属 |

### 命令

```bash
cd '/Users/wang/Documents/ChatGPT/AI hacthon'
.venv/bin/python -m pytest server/tests -q
.venv/bin/python -m tools.retrieval_bench
npm --prefix client run test
npm --prefix client run lint
npm --prefix client run build
git diff --check
```

客户端 test 脚本由六项 P1 基础方案 Task A 建立；未建立则先完成该任务，不能声称现有仓库已经有 npm test。

- [ ] 用 stub 的结果验证所有分支；仅把确实用真模型跑过的例子记录为真实 AI 验收，不因 UI 出现 ai 就宣称线上已验证。
- [ ] 浏览器桌面和窄屏分别检查默认折叠/展开截图，确认提交区未移动出首屏。
- [ ] 对同一套固定候选和答案 fixture 比较改动前后排序、outcome、next_node 和 evidence；本轮只允许 trace 与文案差异。
- [ ] 每包独立提交 A→B→C→D→E，最终更新 API_CONTRACT 和演示脚本；没有用户要求不推送、不部署。

## 10. 回滚、自检

- 后端字段可空、前端容忍缺失，支持滚动回退；search 包装保持原调用兼容。
- presentation_json 采用基础方案的可兼容增列策略，回滚保留数据库列和历史记录，不删除卷。
- 未引入全局可变请求 trace；未泄漏答案或凭据；未改变评估语义；未伪造阶段、耗时、检索命中或模型调用数。
- 方案完成条件：用户看见的是本次真实执行路径，而不是依据卡片推测出来的 RAG 标签。
