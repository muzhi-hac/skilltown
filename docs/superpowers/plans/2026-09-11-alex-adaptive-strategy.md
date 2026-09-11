# Alex Adaptive Strategy Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with test-first checkpoints. Execute inline unless the user explicitly requests delegation. Commit or push only when requested.

**Goal:** 仅让 Alex 根据学习者已提供的证据选择策略：充分即通过、明确违规承诺进入后果、其余追问；四轮是有效回答上限。

**Architecture:** 共用现有评估器和状态机。新增一个 Alex 纯策略模块、节点评分点分组和可校验的行动信号；一次模型调用返回判定、策略提议和对白，服务端重算路由与策略。保持既有 API 响应、SQLite 表、其他 NPC 行为。

**Tech Stack:** Python / FastAPI / Pydantic / pytest；既有 React 结果卡不重构。

---

## 当前基线及边界

工作目录：`/Users/wang/Documents/ChatGPT/AI hacthon`。
基线提交：`23ad7e7`；上一轮本地验证 84 tests passed。
- pass 已经当轮推进；不是新功能。
- 非 pass 目前末轮前都施压；策略按轮次选择。
- covered/missing 在模型层校验后丢弃，需保留。
- deferred 留在原节点，不增加有效轮数、不写学习证据。
- 本次不改法律语料、不扩角色、不新增第二次生成调用、不做用户画像。
- 不修改密钥、部署配置或运行真实付费探测作为默认单测。

## 行为契约

优先级：deferred → pass → 已验证的明确违规承诺 → 达到轮数上限 → 选择追问策略。
- pass：当前情境所需证据充分，立即推进；不强制再施压。
- 明确违规：当前学习者原文明确承诺执行此节点配置中的禁止行动，进入已有 miss 后果分支。
- 信息不足、模糊表态、假设提问、一律拒绝：都不等于明确违规。
- 上限仍未通过：使用现有后果卡作为复盘入口，解释“本次证据仍不足”，不说用户已接受礼物。
- deferred：不显示角色结算，不记录失败，不消耗轮次，保留现有草稿行为。
- 已通过/失败的情境不继续调用生成策略。

同一节点多轮证据：Alex 使用当前未 resolved 的学习者发言与本次回答进行重评。不得纳入 NPC 发言、其他节点、已 rewind 的旧弧、Mira 复盘或上一次尝试。新的明确撤回/相反决定优先于旧回答，不能简单并集 covered。每轮都重新评估完整相关学习者记录。通过引用只接受这些学习者发言里的连续原文；提前失败引用必须来自本次回答。该语义判断仍依赖模型，原文校验不代表自动证明语义正确。

## 文件职责

以下路径均位于 `/Users/wang/Documents/ChatGPT/AI hacthon`：
- 新建 `server/core/alex_strategy.py`：纯策略选择、静态规则描述。
- 修改 `server/core/evaluator.py`：为 EvaluationResult 添加带默认值的字段，不破坏其他 NPC。
- 修改 `server/core/grounding.py`：给 EvaluationContext 加可选 adaptive_policy；仅 Alex 的 dinner-invitation 压力节点启用。
- 修改 `server/core/model_evaluator.py`：结构化字段、Alex 专属提示、验证和对白回退；两 provider 共用。
- 修改 `server/content/scenarios.json`：Alex 策略配置和五个节点的评分点分组；其他 NPC 不变。
- 修改 `server/core/content_validation.py`：配置引用和备用对白校验。
- 修改 `server/api/routes.py`：Alex 策略决定提前失败/继续，其余保持旧逻辑。
- 新建 `server/tests/test_alex_strategy.py`：纯决策表测试。
- 扩展 `server/tests/test_model_evaluator.py`、`server/tests/test_api.py`、`server/tests/test_content_validation.py`。

## 数据设计

EvaluationResult 新字段（放在已有非默认字段之后）：
```python
covered: tuple[str, ...] = ()
missing: tuple[str, ...] = ()
strategy_id: str = ""
committed_violation: bool = False
```
RubricVerdict 新字段（不可信提议）：
```python
strategy_id: str = ""
action_intent: str = "unclear"
action_rule_id: str = ""
action_quote: str = ""
```
`action_intent` 的允许值为 unclear / conditional / compliant / committed_violation。
服务端只有在有效 Alex 配置、已校验判定、非 pass、非 overgeneralized、规则 ID 属于当前节点、本轮原文引用存在时，才接受 committed_violation。pass 与 committed_violation 同时出现属于矛盾输出：整条判定走现有确定性回退。越界规则/错误枚举/伪造 quote 同样回退，而不是偷偷当成普通 miss。

`covered` 与 `missing` 必须不相交且全集恰好为 required（只对 adaptive Alex 加强，旧角色行为不变）。passed=false 但 covered 已全且无其他已定义错误时视为矛盾，回退；不得替模型自动抬分。现有来源引用与通过原文核验继续生效。

## 五个节点的评分点分组

分组用于选策略，不更改 rubric；允许行动与理由分组重叠，但每个 required 至少落入一个组。

| 节点 | reasons | decision | execution |
|---|---|---|---|
| alex_public_gift | recipient_role, applicable_limit | decline_or_surrender | record |
| alex_private_gift | benchmark_not_safe_harbour, context | 空 | register |
| alex_business_meal | per_person, business_purpose | 空 | approval_and_record |
| alex_cash_gift | cash_gift_distinction | prohibited_action | next_step |
| alex_permitted_meal | no_pending_decision | allow_with_conditions | record |

每个节点配置 permitted `action_rule_id` 及含义：
- public_gift: accept_over_limit（明确接受当前超限礼物）；conceal_record（明确隐瞒/不登记）。
- private_gift: conceal_record。接受礼物本身不触发提前失败。
- business_meal: bypass_required_approval。不要把推荐性批准说成强制；该规则只能对应当前场景明确要求的流程。
- cash_gift: accept_cash_gift（明确接受本场景禁止的现金礼物）。
- permitted_meal: conceal_record。允许有条件接受；拒绝属于待澄清/过度概括，不是收受违规利益。

## 策略和备用台词

| strategy_id | 触发 | 备用对白 |
|---|---|---|
| clarify_decision | 未覆盖任何评分点或缺少明确决定 | So what are you actually proposing we do with the offer? |
| probe_conditions | overgeneralized | Is that your answer in every case, or is there something about this offer that matters? |
| probe_reason | 已表达决定，但理由仍缺 | What is it about this offer that makes you say that? |
| probe_action | 理由完整，但执行步骤缺失 | All right. What would you actually do next? |
| probe_gap | 其他混合缺口 | Talk me through how you reached that decision. |
| concede | pass | All right. I hear your decision. Let's leave it there. |
| close_violation | 明确违规承诺 | Then we have a decision. |
| close_review | 上限仍未通过 | We are not getting any further. Let's pause here. |
| retry | deferred | 空，不输出 NPC 台词 |

模型对白可以保持 Alex 的人情压力，但不能偷偷修改角色身份、金额、批准状态或其他评分事实；不得给出标准答案，不得依据轮数强制加价。同策略再次出现时利用对话历史换说法；备用句重复是已知降级，不增加模型调用。

## Task 1：纯策略函数与表驱动测试

- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_alex_strategy.py`，先写下列测试并确认失败。
```python
from server.core.alex_strategy import select_strategy

def test_pass_does_not_wait_for_four_rounds():
    assert select_strategy(True, True, False, False, False,
                           {'recipient_role'}, set(), {'recipient_role'}, set()) == 'concede'

def test_empty_coverage_is_not_a_violation():
    assert select_strategy(True, False, False, False, False,
                           set(), {'role'}, {'role'}, set()) == 'clarify_decision'

def test_overgeneralization_does_not_imply_concession():
    assert select_strategy(True, False, True, False, False,
                           set(), {'role'}, {'role'}, set()) == 'probe_conditions'

def test_deferred_on_last_round_is_not_failure():
    assert select_strategy(False, False, False, False, True,
                           set(), {'role'}, {'role'}, set()) == 'retry'
```
- [ ] 在 `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/alex_strategy.py` 实现：
```python
def select_strategy(assessed, passed, overgeneralized, committed_violation,
                    is_last_turn, covered, missing, reasons, decision):
    if not assessed:
        return 'retry'
    if passed:
        return 'concede'
    if committed_violation:
        return 'close_violation'
    if is_last_turn:
        return 'close_review'
    if overgeneralized:
        return 'probe_conditions'
    if not covered:
        return 'clarify_decision'
    if decision & covered and reasons & missing:
        return 'probe_reason'
    if reasons <= covered and missing:
        return 'probe_action'
    if decision & missing:
        return 'clarify_decision'
    return 'probe_gap'
```
- [ ] 补每条分支测试；同一 covered/missing 在第1和第2轮应得到相同策略；末轮分支除外。
- [ ] 执行 `.venv/bin/python -m pytest server/tests/test_alex_strategy.py -q`，全部通过。

## Task 2：配置、内容校验、上下文

- [ ] 按上表给 Alex persona 增加 `adaptive_policy`，含策略列表；五个压力节点增加 `adaptive_rubric`（reasons/decision/execution/action_rules）。
- [ ] 将 dinner-invitation version 从 2.0.0 提升到 2.1.0，保证旧学习尝试触发既有版本更新流程。
- [ ] 在 EvaluationContext 添加可选配置字段，build_context 仅在 persona.npc_id == 'alex'、scenario_id == 'dinner-invitation' 且 pressure 非空时赋值。Mira 的复制节点不启用。
- [ ] 校验：分组只引用当前 required、覆盖全部 required；策略 ID 唯一；所需九种策略齐全；retry 之外都有非空备用对白；action_rules 的 ID 和描述非空且唯一。
- [ ] 增加删除分组、错误评分点 ID、重复策略、缺备用句、非 Alex 保持原配置的测试，再实现校验。
- [ ] 执行 `.venv/bin/python -m pytest server/tests/test_content_validation.py server/tests/test_grounding.py -q`。

## Task 3：单调用评估和策略校验

- [ ] 加上述 RubricVerdict / EvaluationResult 字段，保留旧角色默认值。
- [ ] 仅对 Alex adaptive context，在 prompt 中传全部可用策略、决策优先级、当前节点评分点分组、action_rules；不要同时传入旧轮次选定的唯一 tactic。
- [ ] 提供本节点当前未结算的学习者历史用于证据重评；NPC 历史只用于对白连贯，明确禁止作为学习证据。固定情境内容始终来自服务端。
- [ ] 先验证判定，再用 select_strategy 重算预期策略。模型 strategy_id 相同且台词过滤通过时采用台词；否则仅替换为预期策略的备用对白，不丢弃有效判定，也不重新调用模型。
- [ ] 对 Alex 台词过滤移除 context/register 等普通评分点子串匹配，保留条款号模式检测，例如 `\bANNEX-\d+(?:\.\d+)*\b`（忽略大小写）；拦显式评分话术如 'the correct answer is'。这些是有限过滤，不宣称阻止全部语义泄露。
- [ ] 策略与失败规则 ID 不进入 town/node 的公开响应；内部日志只记录 node/strategy/accepted_or_fallback，避免记录密钥和完整回答。
- [ ] 用 fake transport 验证每个回答只触发一次模型请求（传输层现有重试不计为新增策略调用）。
- [ ] 两 provider 的 schema 测试必须覆盖新字段；不得另写 provider 专属判定逻辑。
- [ ] 测试：伪造 quote、NPC 台词作为证据、跨节点证据、历史正确但本轮撤回、允许接受、假设性接受、否定接受、未知规则、策略不匹配、普通 register 单词允许、条款号回退。
- [ ] 执行 `.venv/bin/python -m pytest server/tests/test_model_evaluator.py server/tests/test_alex_strategy.py -q`。

## Task 4：接入路由，保证 Alex 之外不变

- [ ] 先写第一轮正确通过、第一轮明确违规进入后果、信息不足继续、末轮deferred原地等待的 API 测试。
- [ ] respond 内仅对 adaptive Alex 使用服务端确定的 strategy_id：concede 走 pass；close_violation/close_review 走 miss；retry 走原 deferred；其他保留本节点并记录 learner/NPC 一对对白。
- [ ] 结束对白使用相应策略验证后的台词或备用句，不使用旧 persona.closing（它可能声称用户接受了礼物）。
- [ ] Alex 的解释中不再使用 _with_rounds 的 held/gave way 断言；close_review 用 `The practice ended without sufficient evidence of mastery.`，close_violation 保留经验证的本轮决定说明。
- [ ] 确定性回退：审核样例 pass 仍直接过；miss/overgeneralized 没有可信 covered 时走中性澄清或边界追问；不从普通 miss 猜提前违规。达到上限用 close_review。
- [ ] 不给API增加策略字段，不改 evidence/skill_projection 表，不改原幂等与 revision 控制。
- [ ] 测试 rewind 后旧历史不参与新弧；同一事件重放不增加轮次或调用；Sam/Nina/Jo 的固定阶梯保持不变。
- [ ] 执行 `.venv/bin/python -m pytest server/tests -q`，基线全部通过且新测试通过。

## Task 5：验收与交付

- [ ] `cd client && npm run build && npm run lint`：构建成功，无新增 lint 警告。
- [ ] 使用临时数据库、SKILLTOWN_MODEL_ENABLED=false 启动本地服务，跑现有 smoke_api.py 与 e2e_room.py；不对共享学习记录执行清空测试。
- [ ] 经用户允许后进行最小真实模型验收，记录每轮 strategy、是否使用模型台词、延迟及跳转；不输出完整密钥。
- [ ] 真实轨迹A：充分决定→第1轮过；B：简短拒绝→追问理由→补事实→追问执行→补记录后过；C：明确收下并隐瞒→第1轮后果；D：允许情境的有条件接受→通过而非提前失败；E：模型失败→deferred原地。
- [ ] 更新 README：Alex 自适应、其他 NPC 固定阶梯；最多四轮；结构校验不保证模型永不误判。
- [ ] 审查差异仅限上述文件；不新增模型权重、秘密文件或构建产物。
- [ ] 交付测试输出、配置示例、真实模型验收记录（如已获准），不自动推送。

## 回滚

增加运行时开关 `SKILLTOWN_ALEX_ADAPTIVE_ENABLED`（默认 false）；只有显式 true 且 Alex 配置有效才启用新行为。关闭时模型字段使用默认值、prompt/策略/路由全部走现有路径；不依赖数据库回迁。已因场景版本升级而失效的旧 attempt 不通过关闭开关复活，使用已有“开始更新后的任务”入口。

## 交付顺序

先完成 Task 1–3，保持开关关闭；再完成 Task 4–5 并验证后开启。用户如要求分批提交，建议三个提交：纯策略与配置、模型与路由集成、回归与文档。未完成前不把设计或测试样例标成已实现功能。
