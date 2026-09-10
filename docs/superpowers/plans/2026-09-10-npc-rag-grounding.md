# NPC RAG Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 四位 NPC、开场题、辅导、提示与评估共用可追溯文档依据，并在 512MB 部署环境验证真实混合检索。

**Architecture:** 内容节点声明知识锚点及节点级评分标准；服务器构造唯一 EvaluationContext，将场景事实、完整依据和评分标准送入评估器。展示使用短摘录，评分使用完整段落；状态与证据仍由现有引擎和存储掌管。

**Tech Stack:** Python/FastAPI/Pydantic、JSON 内容、SQLite、React/TypeScript、model2vec、Docker。

---

## 基线与实施边界

- 已核实分支 feat/npc-rag-skills，原有工作区修改只有 `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/policy.py`；保留其实现，先补测试再纳入独立提交。
- 55 项测试通过沿用用户给出的结果；本次规划没有重新执行测试、真实模型调用或部署。
- `/Users/wang/Documents/ChatGPT/AI hacthon/server/requirements.txt` 已包含 model2vec；缺的是模型资产进镜像、确定离线加载和部署验收。
- 当前 scenarios.json 的节点尚无 knowledge 字段，实施第 2 项时须同时给现有节点补首批锚点，而非仅替换空数组。
- 下列阈值是现有语料的内容设计候选，不是本计划对现行法律准确性的背书。语料自身将礼品金额标为行政/实践指引，并将 AML 部分标为从 2027 年 7 月起；题目必须保留这些限定。
- 本轮不增加态度、信任度或新的技能维度；现有三个 skill_id 保持稳定，避免无意改变 passport 和推荐投影。

## 文件职责

全部路径基于实际工程目录，实施时使用以下绝对路径。

| 文件 | 职责 |
|---|---|
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/content/scenarios.json` | NPC 任务、节点 facts/knowledge/rubric/hint、分支及版本 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/policy.py` | 保留真实 id 优先解析；输出真实来源卡片 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/grounding.py`（新建） | 构建节点评估上下文，集中确定引用集合 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/scenario_engine.py` | 启动内容验证、版本匹配、现有确定性分支 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/model_evaluator.py` | 使用上下文评分和核验引用，移除生产路径虚构白名单 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/evaluator.py` | 节点级确定性评分，不继续套用餐饮关键词 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/api/routes.py` | node/hint/respond 统一接线 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/api/models.py` | 卡片、readiness、版本冲突响应契约 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/knowledge.py` | 保留 RRF 参数；明确本地加载及运行状态 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/server/main.py` | 启动预热、readiness |
| `/Users/wang/Documents/ChatGPT/AI hacthon/docs/openapi.yaml` | 与实现同步 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/Dockerfile` | 固定模型资产并离线验收 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/fly.toml` | 生产要求 dense、readiness 探测 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/tools/answer_matrix.py` | 新场景真实模型回归 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/docs/DEMO_SCRIPT.md` | 新的演示路径及反例 |
| `/Users/wang/Documents/ChatGPT/AI hacthon/docs/DEPLOY.md` | 资源验收与回滚操作 |

## Task 0：内容准确性门槛（开始接线前确定，不另起重构）

- [ ] 对本轮要引用的段落逐条记录：文档 id、依据类型、适用地区/主体、适用日期、阈值运算符、例外、官方来源及核验日期。存入新文件 `/Users/wang/Documents/ChatGPT/AI hacthon/server/content/knowledge_sources.json`，不要作为普通 Markdown 混入检索索引。
- [ ] 优先核验官方原文：礼品金额的适用范围，AML 实施日期和受益所有人 25%/15% 的条件，拆单与刑责的表述。发现语料与原文冲突，修订语料和对应题目，不让模型自行调和。
- [ ] 题干明确“依据所附文档、在指定地区/日期/组织规则下”。fictional=false 只表示来源于引用文档，不代表该文档是官方法规。
- [ ] 增加来源完整性测试，未核实条目不得进入演示题目清单。不能用只带标题的 source 冒充已核验官方来源。

## Task 1（对应原第 2 项）：先让卡片真正到达学习者

**修改：** policy.py、routes.py、scenarios.json；测试 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_api.py` 和新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_policy.py`。

- [ ] 写失败测试：真实 id 返回非空 source、fictional=false；未知 id 保持不生成卡片；重复 id 只显示一次；读取及恢复 attempt 得到相同卡片。
- [ ] 给现有学习节点补 knowledge 数组，以 ANNEX-1.1、ANNEX-1.2、ANNEX-1.3 为第一条垂直切片；完成页可为空，决策和辅导节点要求非空。
- [ ] `_node_view()` 的核心改动如下，顺序去重放在统一解析入口也可：

```python
"policy_cards": get_policy_cards(list(dict.fromkeys(node.get("knowledge", [])))),
```

- [ ] 将提示改为节点内容 `hint: {text, clause_id}`；hint.clause_id 必须属于节点 knowledge。删掉 request_hint 中按三个 skill_id 映射虚构卡片的逻辑，避免所有领域收到餐饮提示。
- [ ] 验证错误提示节点在 mark_assisted 之前就失败，正常提示仍记录 assisted 和 revision。
- [ ] 执行并确认通过：

```bash
cd '/Users/wang/Documents/ChatGPT/AI hacthon'
.venv/bin/python -m pytest server/tests/test_policy.py server/tests/test_api.py -q
```

- [ ] 审阅原有 policy.py 差异，与本任务测试和接线一起显式提交，不使用 git add .。

## Task 2（对应原第 1 项）：按文档重写题目，而非换几个金额

**修改：** scenarios.json、DEMO_SCRIPT.md；测试新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_scenario_content.py`。

每个节点新增 `knowledge: list[str]`、`facts: object`、`rubric: object`、`hint: object`。facts 包含适用主体/地区/日期和题目条件；rubric 包含 question、required、forbidden_claims、deterministic_checks。text_rule 仍是原有学习技能 id，不再决定法律标准。

| NPC | 主问题覆盖 | 必备反例 | 候选知识 id |
|---|---|---|---|
| Alex | 公务员礼品 €25 边界；私营 €30；商务餐 €100/人；现金礼品；登记和预审批 | 在明确适用组织规则、无待决业务、已披露条件下的低值礼品/餐饮，允许而非一律拒绝 | ANNEX-1.1、ANNEX-1.2、ANNEX-1.3 |
| Sam | 现金 €10,000 / €3,000 边界；关联 4×€3,000；受益所有人条件 | 指定规则及生效时间下，€2,500、身份已核验、无关联拆分/可疑因素，可接受 | ANNEX-4.1、ANNEX-4.2、ANNEX-4.3 |
| Mira | GDPR 知悉后计时与风险判断；NIS2 三阶段及其各自时间起点 | 加密有效、密钥未泄漏，且经评估对个人权利与自由不太可能产生风险：内部记录，不机械对外通报 | ANNEX-2.1、ANNEX-5.1、ANNEX-5.3 |
| Jo | 举报确认/反馈、禁止报复；平均周工时和连续休息 | 指定参考期平均未超限且休息满足要求的安排；正确受理、期限未到且持续处理的举报，不自动升级 | ANNEX-6.1、ANNEX-6.3 |

表中的候选 id 先经过 Task 0 校核；尤其“拆单有刑责”不得直接写成自动定罪。

- [ ] 先写内容测试，要求四个领域和四类允许反例都存在；金额边界题覆盖 below/equal/above，日期题覆盖起算事件、临界点、例外。
- [ ] 每个领域至少安排 3 个决策节点：典型判断、条件变化、允许反例；需要时增加节点，不为凑三个节点把所有阈值塞进同一题。
- [ ] 所有结果节点、分支反馈、policy_clause_ids、提示、NPC 描述一并重写。保留 pass/miss/overgeneralized 三种结果，不再用“所有礼品都拒绝”检测覆盖所有领域。
- [ ] 开场保持三题：Alex 金额与身份、Sam 关联现金、Mira 风险与时限；不宣称三题覆盖四领域。Jo 从地图进入，演示脚本包含一次 Jo 判断。
- [ ] Mira 保留辅导任务并新增数据事件任务；辅导优先取最近需要练习的真实答题证据对应节点及其 rubric/knowledge，无证据显示中性引导。需检查并扩展 `/Users/wang/Documents/ChatGPT/AI hacthon/server/storage.py` 中证据查询；不从 skill_id 猜用户答过哪个领域。
- [ ] 同步场景版本。最小版本策略：已存在且版本不匹配的 attempt 在恢复/回答/提示/回退前返回明确 scenario_version_mismatch；前端引导新开 attempt，保留历史 passport 证据。禁止仅改 JSON version 后用新题解释旧状态。
- [ ] 执行 `.venv/bin/python -m pytest server/tests/test_scenario_content.py server/tests/test_api.py -q`，验证所有分支可达、有明确完成路径、回退指向正确问题。
- [ ] 单独提交内容及版本兼容变更。

## Task 3（对应原第 3 项）：评估、检索和反馈使用同一份依据

**修改：** grounding.py、model_evaluator.py、evaluator.py、routes.py；测试 test_model_evaluator.py 和新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_grounding.py`。

数据流：

```text
node facts + question + rubric
          ↓ 服务端固定查询（学习者回答不扩张允许引用范围）
现有 hybrid search → 排名候选 + knowledge 精确锚点读取
          ↓ 合并、校验、按节点范围过滤
EvaluationContext → 模型评估 / 确定性评估
          ↓ 引用核验 + learner quote 核验
既有确定性分支 → evidence + feedback cards
```

接口目标：`evaluate(rule, text, allow_model=True, *, context)`，两种 evaluator 共用；context 包含 node_id、scenario_version、question、facts、rubric、passages。passages 使用完整 Chunk.text，卡片继续用 excerpt()，防止 700 字截断丢失阈值或例外。

- [ ] 测试首先断言：同一 skill 的两个节点能有不同 rubric 与引用集合，节点问题和全文都出现在请求中。
- [ ] knowledge 是人工审过的可引用范围；混合检索负责排序，精确锚点补齐必需段落。允许集合是实际装入 context 的 passage id，不是全库 id，也不是静态 RUBRICS.clause_ids。明确记录 hybrid 排名来源与 exact 补齐来源，避免把直接查 id 伪装成语义检索命中。
- [ ] 引用锚点为空或丢失时作为内容错误处理，不切回虚构条款。启动校验应让此错误在接收请求前暴露。
- [ ] 移除 Fictional training policy clauses 措辞；prompt 只允许引用提供的真实文档片段，保留 learner_answer 是数据的约束。
- [ ] `_verified()` 检查引用属于 context；陌生引用触发明确验证失败并进入对应节点的确定性路径，不用全部白名单替模型补造引用。passed 与 missing/overgeneralized 自相矛盾时也走验证失败。
- [ ] 回答引文校验保持，但明确它只证明引用来自学习者，不证明语义正确；用答案矩阵检验否定、矛盾和数字碰巧出现的误判。
- [ ] routes.py 当前有 text_branches 时会覆盖评估引用，需将“分支解释用的预审条款”和“模型实际引用条款”区分：AI feedback 使用 verified ids；scripted feedback 使用 branch ids。两者均限定在作答前节点的 context，不用跳转后节点的条款核验上一题反馈。
- [ ] 确定性评分改用每节点审核过的 checks，含允许行动、错误行动、关键条件与边界值；不允许只命中金额或几个关键词就通过。无法可靠判定的回答不得自动生成通过证据；注明未确认并允许重试，且不当成学习者已被证明答错。
- [ ] 覆盖模型关闭、预算用尽、超时、熔断、畸形响应、未知引用的全路径；这些路径仍返回真实卡片且不伪称 AI 输出。
- [ ] 执行 `.venv/bin/python -m pytest server/tests/test_grounding.py server/tests/test_model_evaluator.py server/tests/test_api.py -q`，再提交。

## Task 4（对应原第 4 项）：把内容完整性变成启动和 CI 门槛

**修改：** scenario_engine.py、api/models.py、docs/openapi.yaml；测试 test_contract.py、test_scenario_content.py、test_policy.py。

- [ ] 启动校验遍历所有 scenario/node：knowledge id 唯一且存在；真实 source 非空；决策节点 knowledge 非空；hint id 和 branch policy ids 属于节点集合；rubric 完整；text_branches/next_node/rewind/coaching 目标存在；语料 chunk id 不重复。
- [ ] PolicyCard 加模型级约束：fictional=false 时 source.strip() 非空。旧虚构卡片仅保留明确 legacy 测试，不允许新的演示内容引用。
- [ ] 当前契约测试只比 operationId；补比较 PolicyCard 的 required/properties/default 和 ScenarioNode/Feedback/Hint 的引用关系及新增错误响应，避免只更新 YAML 而未测试响应。
- [ ] 由 create_app().openapi() 生成候选规范并审阅合并，保留原规范中人工描述及示例，不无差别覆盖。
- [ ] 全量验收命令：

```bash
cd '/Users/wang/Documents/ChatGPT/AI hacthon'
.venv/bin/python -m pytest server/tests -q
npm --prefix client run lint
npm --prefix client run build
.venv/bin/python -m tools.retrieval_bench
```

预期：原有行为回归通过，新契约/场景测试通过；混合检索现有 16 题基准不低于已记录的 15/16，新增领域问题单独报告，不把旧基准分母偷偷替换。

- [ ] 提交测试、内容校验和契约同步。

## Task 5（对应原第 5 项）：合并前证明线上不是 sparse-only

**修改：** Dockerfile、requirements.txt、knowledge.py、main.py、api/models.py、fly.toml、DEPLOY.md；测试新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_rag_runtime.py`。

- [ ] 写测试覆盖：本地权重成功；权重缺失；编码失败；矩阵维度不匹配；生产强制 dense 与开发允许 sparse 两种模式。
- [ ] 固定兼容 Python 3.13 的依赖版本和模型不可变 revision，并记录模型许可证与 SHA256；先解析真实 revision 再写入构建配置，不用浮动 main。
- [ ] Docker 构建阶段取得并保存模型至 `/app/models/potion-base-8M`，最终镜像显式复制；当前 Dockerfile 只复制 server/client，本机模型文件存在不代表进了镜像。
- [ ] 生产 `_encoder()` 仅从显式本地模型目录加载，去掉请求期间尝试远端仓库的路径。应用启动时加载模型、建立矩阵并跑一次固定 query。
- [ ] 新增 SKILLTOWN_REQUIRE_DENSE=true；强制模式预热失败则启动失败或 readiness=503。开发允许 sparse，但 readiness payload 明示 retrieval_mode 与降级原因，不只记日志。
- [ ] `/health` 保留活性；新增 `/ready` 表示语料和检索可用，部署探测指向 `/ready`；公开状态仅含模式、模型版本、chunk 数及准备状态，不暴露路径或凭据。
- [ ] 构建并运行离线、内存受限验证：

```bash
cd '/Users/wang/Documents/ChatGPT/AI hacthon'
npm --prefix client run build
docker build -t skilltown:rag-check .
docker run --rm --network none --memory 512m --memory-swap 512m \
  -e SKILLTOWN_REQUIRE_DENSE=true skilltown:rag-check \
  python -c 'from server.core.knowledge import dense_available,search; assert dense_available(); assert search("cash identification threshold")'
```

- [ ] 再以相同限制运行完整服务，用容器内客户端走 session→attempt→answer→hint→restore；预热后做至少 100 次检索及 5 路并发请求。记录 cgroup memory.peak（或等效峰值采样）、当前内存、OOM 状态、启动耗时、检索 p50/p95。模型响应使用 stub 可隔离检索资源，另做真实模型链路验收。
- [ ] 建议发布门槛：无 OOM，峰值不超过 400MiB，为 512MiB 留余量；至少单进程、预加载一次模型。超标先量化分配来源并收敛内存，再决定升配，不通过切 sparse 隐藏问题。
- [ ] 在 staging 实机重复 readiness 和资源验收，报告镜像 digest、架构、模型 revision、峰值。合并 main 前完成；本机断网 smoke 不替代实机测量。
- [ ] 回滚：保留上一镜像 digest；不删除数据卷；本轮避免破坏性数据库变更，出现错误回退镜像和配套内容版本。新版本 attempt 由版本不匹配机制隔离，不重解释历史证据。

## 后续独立批次（不塞进本次 RAG 主链）

1. **真实答案矩阵和手工验收：** 重写 answer_matrix.py 的旧场景答案，扩至四领域的正确/部分/过度概括/临界/无关/注入样本；20 次是旧矩阵规模，不是假定新矩阵仍只花 20 次。输出逐例预期、实际、引用、mode、耗时，fallback 不计为 AI 通过。跑完才更新 React 手工检查及截图/录屏，覆盖窄屏、刷新恢复、提示 assisted、回退、新旧版本冲突。人工手感验收仍由人给结论。
2. **模型调用展示及延迟：** 先纠正计数：当前只在 mode=ai 时 record_model_call，已发送但解析失败等调用未计入。将尝试次数、成功数、fallback、耗时分开；请求前原子预算预留，SDK 重试也纳入费用观测。会话只展示自己的统计，不展示 token。保持自由回答，先测模型等待/检索/网络/前端，再比较 effort、上下文长度、连接复用与评估质量，不预先承诺消掉 5–6 秒。
3. **薄记忆：** NPC 领域查询由节点 facts/领域标签生成；npc_notes 只存 session_id、npc_id、scenario_version、source_event_id、observed_fact、created_at，以事件 id 保证幂等；仅保留已发生的事实。已展示卡片按 session+clause_id+corpus_version 去重，默认折叠重复，不从当前问题或提示中移除必要依据。删除 session 时级联删除，无态度/信任度。
4. **旧客户端：** 建议本轮保留 godot/ 且继续不构建、不部署；在 README 标 legacy。演示稳定后用独立 PR 删除并保留 tag，不混入 RAG diff。
5. **凭据：** 与主线并行的运维优先项，先创建新凭据→更新部署 secrets→探测成功→撤销旧凭据；不在报告、日志、截图或命令参数中输出密钥值。

## 完成定义与自检

- [ ] 四领域、四个允许反例、三道开场、Mira 辅导均可走通，卡片来源可见。
- [ ] 同一个作答前节点的 context 约束 AI/fallback/分支反馈/证据，旧虚构白名单退出新内容运行路径。
- [ ] 全部引用和图结构经过启动校验；契约测试覆盖字段而非只看 operationId。
- [ ] 新旧 attempt 不串题；历史证据保留且不误作新版题目通过证明。
- [ ] dense 在镜像断网与 512MB 实机条件下均已验证；readiness 可判断实际模式。
- [ ] 计划覆盖原条目 1–12 与薄记忆；执行期间不把尚未跑的测试、矩阵或资源验收写成已完成。

---

# 执行手册 v2：给较弱 agent 的确定性工作包

本节把上文的架构方案细化为执行合同。发生冲突时，以本节的字段、顺序、状态约定为准；上文的内容准确性与发布门槛仍有效。本节代码是待实施蓝图，不表示业务代码已完成。

## A. 先读这些约束，避免走错路线

1. 只修改当前分支。不合并 main、不部署、不付费跑模型，直到对应发布检查点明确允许。
2. 不覆盖未提交的 policy.py；先查看 diff，保留真实 id 优先逻辑。
3. 不改 RRF_K=60、DENSE_WEIGHT=2.0，不替换检索库，不增加向量数据库。
4. 不增加 skill_id；领域是 scenario/node 内容维度，不是新的 passport 状态维度。
5. 不把内置 `source` 文档名当官方法规核验结果；真实来源卡与已核验法律事实是两个维度。
6. 不把学习者输入用作扩大引用白名单的检索查询。模型看到的条款全文来自服务器构建的 context。
7. 所有新生产节点最终都使用 context；旧 evaluator 接口仅在迁移中临时兼容，最后删掉 legacy 分支。
8. 每个工作包按“测试先红→最小实现→测试变绿→检查 diff→提交”执行。某包测试失败就停在本包修复，不以删除测试推进。
9. 不宣称自然语言关键词能可靠判断合规答案。最小降级方案只精确匹配审核过的完整答案样例；其余返回 deferred，不产生学习证据。待后续专门评估后再扩展规则。
10. 所有命令从 `/Users/wang/Documents/ChatGPT/AI hacthon` 执行；不要新建工程或重装全部依赖。
11. 每次提交列出文件，禁止 `git add .`；不提交 `.env`、数据库、缓存、模型密钥或对话记录。
12. 上文 Task 0 核验所需的官方来源和模型 revision 是外部事实，实施 agent 必须真实查询后记录；不要用占位 URL、推测的 revision 或臆造的法律适用范围填充。

## B. 工作包依赖与大小

每个编号是一批可独立审阅的改动；内部每个勾选项是一项动作。B01–B05 不依赖真实模型服务。

| 包 | 产出 | 前置 | 建议提交标题 |
|---|---|---|---|
| B01 | 解析器测试、卡片下发、节点提示 | 当前基线 | feat: expose real policy cards and node hints |
| B02 | 不可变 EvaluationContext 与构建器 | B01 | feat: build node-scoped grounding context |
| B03 | deferred 评估与无证据状态路径 | B02 | feat: preserve progress when grading is deferred |
| B04 | 模型 prompt / 引用 / 一致性核验 | B03 | feat: ground model grading in node passages |
| B05 | 版本拒配和 React 明确恢复动作 | B04 | fix: reject stale scenario versions |
| B06 | 官方依据核验及全部领域内容 | B05、Task 0 | feat: replace demo scenarios with sourced cases |
| B07 | 三题筛查、Mira 按证据辅导 | B06 | feat: ground screening and coaching in real cases |
| B08 | 强内容校验、契约、回归矩阵 | B07 | test: enforce grounding and scenario contracts |
| B09 | 镜像语料/权重、离线模式、readiness | B08 | build: package and require hybrid retrieval |
| B10 | 资源报告、真实模型矩阵、演示验收 | B09 | docs: record grounded demo release evidence |

为何顺序微调：先实现 context/deferred 再批量启用新问题，避免在某个中间提交里用“礼品关键词”评分 AML/GDPR。B06 的内容草稿可先写在计划旁，但生产 scenarios.json 要到 B04 后再切换。

## C. 固定内部字段（不要自行换名字）

### C1. 新节点内容结构

保留现有 npc_id/category/text/choices/allow_text/text_rule/text_branches/branches 等字段。新增以下字段：

```json
{
  "knowledge": ["ANNEX-2.1"],
  "facts": {
    "domain": "data_incidents",
    "reference_date": "2026-09-10",
    "scope": "Personal data breach assessment under the cited training reference",
    "awareness_time": "2026-09-10T10:00:00Z",
    "incident_time": "2026-09-09T08:00:00Z",
    "risk": "high",
    "encryption_effective": false
  },
  "rubric": {
    "question": "Does the answer distinguish awareness, authority notification and communication to affected people?",
    "required": ["awareness_clock", "authority_window", "individual_notice"],
    "criteria": {
      "awareness_clock": "Use the stated awareness time, rather than the earlier incident time, as the clock start.",
      "authority_window": "Explain the authority notification window and applicable risk condition in the cited passage.",
      "individual_notice": "Distinguish the high-risk communication duty from the authority deadline."
    },
    "forbidden_claims": ["The clock starts at the earlier incident time.", "Every breach automatically requires notifying every affected person."],
    "reference_answers": [
      {
        "text": "I start from when we became aware, notify the authority within 72 hours, and inform affected people without undue delay because this case is high risk.",
        "outcome": "pass"
      },
      {"text": "I notify everyone about every incident regardless of risk.", "outcome": "overgeneralized"},
      {"text": "I wait one month before doing anything.", "outcome": "miss"}
    ]
  },
  "hint": {
    "text": "Separate the start of the clock from the risk conditions for each recipient.",
    "clause_id": "ANNEX-2.1"
  }
}
```

以上是接口和评分结构示例；B06 发布内容仍需 Task 0 核验。`required` 用稳定 criterion id，模型 covered/missing 返回这些 id；不得把自然语言长句当跨模块键。

### C2. 建议直接采用的 grounding.py 核心代码

文件：`/Users/wang/Documents/ChatGPT/AI hacthon/server/core/grounding.py`。

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from server.core import knowledge


class GroundingError(ValueError):
    pass


@dataclass(frozen=True)
class Passage:
    clause_id: str
    title: str
    text: str
    source: str
    retrieval: Literal["hybrid", "exact"]


@dataclass(frozen=True)
class ReferenceAnswer:
    text: str
    outcome: Literal["pass", "miss", "overgeneralized"]


@dataclass(frozen=True)
class EvaluationContext:
    scenario_id: str
    scenario_version: str
    node_id: str
    question: str
    facts_json: str
    grading_question: str
    required: tuple[str, ...]
    criteria: tuple[tuple[str, str], ...]
    forbidden_claims: tuple[str, ...]
    reference_answers: tuple[ReferenceAnswer, ...]
    passages: tuple[Passage, ...]

    @property
    def allowed_clause_ids(self) -> tuple[str, ...]:
        return tuple(p.clause_id for p in self.passages)


def build_context(
    scenario_id: str,
    scenario_version: str,
    node_id: str,
    node: dict[str, Any],
) -> EvaluationContext:
    ids = tuple(dict.fromkeys(node["knowledge"]))
    if not ids:
        raise GroundingError(f"{scenario_id}/{node_id}: empty knowledge")
    chunks = {}
    for cid in ids:
        chunk = knowledge.get(cid)
        if chunk is None or not chunk.source.strip():
            raise GroundingError(f"{scenario_id}/{node_id}: unresolved source {cid}")
        chunks[cid] = chunk
    rubric = node["rubric"]
    required = tuple(rubric["required"])
    facts_json = json.dumps(node["facts"], ensure_ascii=False, sort_keys=True)
    # The learner answer is intentionally absent from this query.
    query = f"{node['text']}\n{facts_json}\n{rubric['question']}"
    hits = knowledge.search(query, limit=max(3, len(ids)))
    ranked = tuple(dict.fromkeys(c.id for c in hits if c.id in chunks))
    ordered = ranked + tuple(cid for cid in ids if cid not in ranked)
    passages = tuple(
        Passage(
            clause_id=cid,
            title=chunks[cid].title,
            text=chunks[cid].text,
            source=chunks[cid].source,
            retrieval="hybrid" if cid in ranked else "exact",
        )
        for cid in ordered
    )
    return EvaluationContext(
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        node_id=node_id,
        question=node["text"],
        facts_json=facts_json,
        grading_question=rubric["question"],
        required=required,
        criteria=tuple((key, rubric["criteria"][key]) for key in required),
        forbidden_claims=tuple(rubric["forbidden_claims"]),
        reference_answers=tuple(ReferenceAnswer(**x) for x in rubric["reference_answers"]),
        passages=passages,
    )
```

补充约束：retrieval=hybrid 表示经过 search 接口排序，不代表 dense 一定运行；实际 dense/sparse 模式以 readiness 为准。不得用这个标签掩盖 sparse 降级。

### C3. 评估结果新增一个字段

`/Users/wang/Documents/ChatGPT/AI hacthon/server/core/evaluator.py` 的 EvaluationResult 在已有默认字段之后新增：

```python
assessed: bool = True
```

`outcome` 属性首先执行：

```python
if not self.assessed:
    return "deferred"
```

其余 pass/miss/overgeneralized 保留。API `/Users/wang/Documents/ChatGPT/AI hacthon/server/api/models.py` 的 AttemptResponse 新增：

```python
assessment_status: Literal["assessed", "deferred", "not_requested"] = "not_requested"
```

前端 `/Users/wang/Documents/ChatGPT/AI hacthon/client/src/api.ts` 的 Attempt 同步新增：

```typescript
assessment_status: "assessed" | "deferred" | "not_requested";
```

create/get 默认为 not_requested；respond 明确传 assessed/deferred。get 恢复接口本来不返回上一条 feedback，保持此行为，不假装 deferred 状态持久化在 attempts 表。

## D. B01–B05 具体动作与测试

### B01：卡片及提示

- [ ] 查看原有 policy.py diff，不重写 POLICY_CARDS 表。
- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_policy.py`，先加入：

```python
from server.core.policy import get_policy_cards


def test_real_card_has_provenance():
    cards = get_policy_cards(["ANNEX-1.2"])
    assert len(cards) == 1
    assert cards[0]["clause_id"] == "ANNEX-1.2"
    assert cards[0]["fictional"] is False
    assert cards[0]["source"].strip()


def test_unknown_id_is_not_invented():
    assert get_policy_cards(["NOT-A-REAL-CLAUSE"]) == []


def test_repeated_ids_are_stable_and_unique():
    cards = get_policy_cards(["ANNEX-1.2", "ANNEX-1.2", "ANNEX-1.1"])
    assert [c["clause_id"] for c in cards] == ["ANNEX-1.2", "ANNEX-1.1"]
```

- [ ] 运行 `.venv/bin/python -m pytest server/tests/test_policy.py -q`，预期重复项测试红，另两项绿。
- [ ] 将解析器循环改为 `for clause_id in dict.fromkeys(clause_ids):`，不改变未知 id 行为。
- [ ] routes._node_view 替换空数组；旧节点先补对应礼品文档锚点和 hint。
- [ ] request_hint 在读取 node 后先验证 hint 存在且卡片可解，再调用 mark_assisted；无 hint 的完成页返回 ApiError(400, "hint_not_available", "This node has no hint.")。
- [ ] Lesson.tsx 的 Hint 按钮至少在 is_complete 或 !node.allow_text 时禁用，防止完成页空数组下标错误。
- [ ] test_api 新增开始/恢复卡片相等、hint.source 非空、完成页 hint 不改变 revision 三个测试；原有“feedback fictional=True”先保持直到 B04 更换反馈来源，不把半接线误当完成。
- [ ] 单独提交 B01。

### B02：上下文

- [ ] 新建 grounding.py，使用 C2 的接口；禁止在构建器内读用户会话或写数据库。
- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_grounding.py`；用 monkeypatch 固定 search，避免测试下载模型。
- [ ] 首个完整测试如下：

```python
from server.core import knowledge
from server.core.grounding import build_context


def test_context_pins_sources_and_preserves_full_text(monkeypatch):
    node = {
        "knowledge": ["ANNEX-2.1"],
        "text": "When does the clock start?",
        "facts": {"domain": "data_incidents"},
        "rubric": {
            "question": "Identify awareness.",
            "required": ["awareness"],
            "criteria": {"awareness": "The clock starts at awareness."},
            "forbidden_claims": [],
            "reference_answers": [{"text": "At awareness.", "outcome": "pass"}],
        },
    }
    # Force an unrelated hit: it must not expand this node's sources.
    monkeypatch.setattr(knowledge, "search", lambda *a, **k: [knowledge.get("ANNEX-1.2")])
    context = build_context("data-incidents", "2.0.0", "privacy_clock", node)
    assert context.allowed_clause_ids == ("ANNEX-2.1",)
    assert context.passages[0].retrieval == "exact"
    assert context.passages[0].text == knowledge.get("ANNEX-2.1").text
    assert context.scenario_version == "2.0.0"
```

- [ ] 追加四个测试：unknown id 抛 GroundingError；empty knowledge 抛 GroundingError；相同 text_rule 的两个 node 产生不同 required；search 返回重复命中不产生重复 passages。
- [ ] 在 routes.respond 中仅当 node 有 rubric 时构建 context，并暂时保留 legacy 调用；B08 必须删掉此临时分支。
- [ ] 单独提交 B02。

### B03：确定性与 deferred

**决定：** 不实现通用正则法律评分器。新增的 reference_answers 只允许整个回答规范化后精确匹配；匹配 pass/miss/overgeneralized 才算 assessed=True，其他一律 deferred。这是有限覆盖而非通用评估。

- [ ] 在 evaluator.py 新增规范化函数，保留否定、金额、标点语义，不使用去掉所有非字母符号的清洗：

```python
def normalise_answer(text: str) -> str:
    return " ".join(text.casefold().split())
```

- [ ] FallbackTextEvaluator.evaluate 新签名临时使用 `context=None`；context 非空时完整回答匹配审核样例，空时保留旧测试行为至 B08。
- [ ] context 路径的核心实现：

```python
matched = next(
    (item for item in context.reference_answers
     if normalise_answer(item.text) == normalise_answer(text)),
    None,
)
if matched is None:
    return EvaluationResult(
        passed=False,
        assessed=False,
        interpretation="The deterministic checker has not assessed this wording.",
        feedback="Your answer has not been graded. Review the references and retry; no learning result was recorded.",
        policy_clause_ids=list(context.allowed_clause_ids),
        mode="fallback",
    )
return EvaluationResult(
    passed=matched.outcome == "pass",
    assessed=True,
    overgeneralized=matched.outcome == "overgeneralized",
    interpretation="Matched a reviewed whole-answer example for this node.",
    feedback="This answer was checked against a reviewed example for this scenario.",
    policy_clause_ids=list(context.allowed_clause_ids),
    mode="fallback",
)
```

- [ ] routes.respond 的 text 路径：在 has_text_branches 判断之前，先处理 `not evaluated.assessed`，设置 next_node_id=node_id、effect="none"、skill_id=None、learning_state=None、clause_ids=evaluated.policy_clause_ids、反馈来自 evaluated。只有 assessed 才进入 resolve_text。
- [ ] 继续使用 store.apply_transition：它本来在 skill_id/state 均有值时才写 evidence。deferred 仍写幂等 event 并增加 revision，但不更新 skill_projection。禁止直接 return 未落库响应，避免重放产生不同结果。
- [ ] `_attempt_response` 增加 assessment_status；respond.build_response 明确传该字段。
- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/test_evaluator.py`，覆盖完整样例命中、大小写/空白、加一句相反意思后 deferred、只答金额 deferred、跨节点答案不命中。
- [ ] test_api 覆盖 deferred 节点不变、revision+1、learning_updates=[]、passport 不变、重复 client_event_id 返回同一响应。
- [ ] Lesson.tsx 不在 submit() 立即清空 draft。用 attempt.revision/assessment_status 在响应后清空已评估答案；deferred、网络错误保留草稿；切换 attempt_id 清空上一任务草稿。通过 attempt.is_complete 时也清空。
- [ ] 单独提交 B03。

### B04：模型评估器

- [ ] 使用 `TYPE_CHECKING` 导入 EvaluationContext，避免 evaluator.py 与 grounding.py 循环依赖。
- [ ] evaluate、_ask、_prompt、_verified 全链透传 context；每个 self._fallback.evaluate 调用都传 context。用 `rg -n '_fallback.evaluate|def evaluate|def _ask|def _prompt|def _verified' server/core/model_evaluator.py` 检查漏项。
- [ ] prompt 内容以 JSON 对象序列化：scenario_id/version/node_id、question、facts、grading_question、criteria、forbidden_claims、passages（含全文与 source）、learner_answer。不要把 reference_answers 发给模型，它是降级用例不是用户作答。
- [ ] SYSTEM_PROMPT 保持当前输入隔离规则，新增 covered/missing 只能是 criterion id、passed 必须覆盖全部 required、仅从 passages 引用。
- [ ] _verified 的验证顺序固定：feedback 非空→所有 covered/missing id 合法且集合不交叠→引用非空且全部属于 context→passed 时 required 全覆盖且 missing 为空且 overgeneralized=false→passed 的 quote 在回答中→生成 EvaluationResult。
- [ ] 任意核验失败使用同一 context 的 fallback；不要“删除陌生引用后补全白名单并继续声称 AI”。
- [ ] routes 对 context 路径：AI 使用 evaluated.policy_clause_ids；已评估 fallback 的文案可用预审 branch.feedback，引用用 branch.policy_clause_ids；deferred 使用 evaluated 反馈。存储证据引用与实际展示反馈引用一致。
- [ ] 原 FakeClient/FakeResponse 继续复用；所有 context 测试 monkeypatch knowledge.search，禁止真实调用。
- [ ] 修改旧断言的明确清单：invented_policy_clauses 由 mode=ai 改为 fallback；prompt 由 ETH-03 改为真实节点 id 和全文；成功 verdict.covered 必须包含全部 required；超时不再普遍断言 passed=True，只对完整审核样例断言通过。
- [ ] API 中 StubEvaluator 签名增加 `*, context=None`，返回引用从 context.allowed_clause_ids 获取，避免 stub 继续给 ETH-03。
- [ ] 单独提交 B04。

### B05：版本与恢复

- [ ] ScenarioEngine 新增 `assert_version(scenario_id: str, version: str) -> None`；定义独立 `ScenarioVersionError`。不复用 ScenarioError，否则会变成 400。
- [ ] main.py 注册 ScenarioVersionError → 409、code=scenario_version_mismatch、retryable=false、英文信息“Scenario content changed. Start a new attempt; previous evidence is retained.”。
- [ ] get/respond/hint/rewind 在解引用 node 前做版本检查。respond 的幂等成功重放保持最优先：相同旧 event 可返回原响应；新的答题 event 必须检查版本。
- [ ] recordActivity 只记时可继续，不需要读取旧 node；不因统计请求使前端陷入版本恢复循环。
- [ ] 在 test_api 中直接通过 store.connect 把测试 attempt.scenario_version 改成 0.0.0，再逐个请求 get/respond/hint/rewind，断言 409 和证据条数不变。
- [ ] App.tsx 单独处理 scenario_version_mismatch，显示“Start updated task”按钮。由点击调用 api.startAttempt(attempt.scenario_id, attempt.mode)，不自动删除 session、不循环 getAttempt。
- [ ] 新建 attempt 的按钮成功后清空旧反馈/草稿，保留 passport；其他 revision_conflict 分支保持现有 resync 行为。
- [ ] 单独提交 B05。

## E. B06：题目清单与内容生成约束

### E1. 保持外部 task id，避免无谓迁移

| scenario_id（保留） | 新显示标题 | NPC | 新版本 |
|---|---|---|---|
| dinner-invitation | Gifts and hospitality | alex | 2.0.0 |
| supplier-gift | Cash and customer checks | sam | 2.0.0 |
| boundary-response | Speaking up and working time | jo | 2.0.0 |
| ethics-review | Review a case from your record | mira | 2.0.0 |
| screening | Three-question starting check | 按节点 | 2.0.0 |
| data-incidents（新增） | Privacy and incident response | mira | 2.0.0 |

保留旧 id 是兼容策略，不表示 Sam 仍教礼品。TASK_BY_SKILL 暂时保留映射，校验映射目标存在；推荐文案必须说“练习这一通用技能”，不宣称已诊断某领域知识缺口。Mira 的 scenario_ids 为 data-incidents、ethics-review，确保 UI 的任务选择仍能访问两者。

技能显示词同步到 storage.py 的 labels 和 Lesson.tsx 的 SKILL_LABELS：clarify_context = Gather relevant facts；conflict_awareness = Recognize risks and applicable conditions；communicate_boundary = Explain the decision and next step。保留旧证据文本原样，不追溯重写历史。

### E2. 明确 node id 和评分点

以下每行是一个决策节点。题目最终英文措辞依据核验后的文档撰写，不改这些 node id。每题 rubric.required 取本行明确列出的 criterion id，criteria 写清本行描述。每题提供三个完整审核答案样例，对应 pass/miss/overgeneralized；完整样例只能用于测试和有限降级，不展示为选项。

| scenario | node_id | 题目事实与必需评分点 | knowledge |
|---|---|---|---|
| dinner-invitation | alex_public_gift | 适用已核实组织指引，公务员 €26 礼品。recipient_role；applicable_limit；decline_or_surrender；record | ANNEX-1.1, ANNEX-1.2, ANNEX-1.3 |
| dinner-invitation | alex_private_gift | 私营 €30、无待决业务、披露。benchmark_not_safe_harbour；context；register | ANNEX-1.1, ANNEX-1.2 |
| dinner-invitation | alex_business_meal | €100/人，题干明确采用的公司规则及审批状态。per_person；business_purpose；approval_and_record | ANNEX-1.2, ANNEX-1.3 |
| dinner-invitation | alex_cash_gift | €5 现金礼品。cash_gift_distinction；prohibited_action；next_step | ANNEX-1.1 |
| dinner-invitation | alex_permitted_meal | 低值、私营、业务已结束、审批记录齐全。allow_with_conditions；no_pending_decision；record | ANNEX-1.1, ANNEX-1.2, ANNEX-1.3 |
| supplier-gift | sam_cash_limit | 文档适用日期和主体明确，单次 €10,001。scope_and_date；over_limit；non_cash_next_step | ANNEX-4.1 |
| supplier-gift | sam_kyc_boundary | €3,000，身份尚未核验。at_threshold；identify_before_acceptance；not_cash_ban | ANNEX-4.1 |
| supplier-gift | sam_linked_payments | 同一交易 4×€3,000。aggregate_12000；no_splitting_evasion；escalate_process | ANNEX-4.1, ANNEX-4.3 |
| supplier-gift | sam_beneficial_owner | 明确标准/高风险类别，只使用核验后的比例规则。ownership_and_control；applicable_threshold；risk_scope | ANNEX-4.2 |
| supplier-gift | sam_permitted_cash | €2,500，已 KYC，无关联/可疑因素。allow_with_conditions；no_linked_payments；retain_record | ANNEX-4.1 |
| data-incidents | mira_privacy_clock | 发生和知悉时间不同，高风险。awareness_clock；authority_window；individual_notice | ANNEX-2.1 |
| data-incidents | mira_nis2_stages | 适用 NIS2 主体，重大事件。warning_24h；notification_72h；final_from_notification | ANNEX-5.1 |
| data-incidents | mira_encrypted_backup | 有效加密、密钥完整，经评估风险不太可能。risk_assessment；internal_record；no_automatic_external_notice | ANNEX-2.1, ANNEX-5.3 |
| boundary-response | jo_report_receipt | 已收到符合流程的举报。acknowledgement_window；feedback_window_and_start；confidential_process | ANNEX-6.3 |
| boundary-response | jo_no_retaliation | 因举报被威胁排班惩罚。identify_retaliation；protect_reporter；report_internal_concern | ANNEX-6.3 |
| boundary-response | jo_rest_hours | 排班只留 10 小时连续休息、题设无适用例外。daily_rest；adjust_schedule；not_just_weekly_total | ANNEX-6.1 |
| boundary-response | jo_average_hours | 单周超过 48h，但明确参考期平均低于 48h且休息满足，无其他违规。average_not_single_week；reference_period；allow_with_conditions | ANNEX-6.1 |

- [ ] 每题 scope/date/主体是 facts 的真实字段，也要在用户可见题干出现；不能只放进 prompt 让学习者猜。
- [ ] 每个 domain 选一个独立验证版本或确保 verification 使用未在 practice 中展示的变式；如果同题重做，保留现有模式但 UI 不称“新题迁移验证”。先不增加自动迁移成效宣称。
- [ ] 金额临界测试放在答案矩阵/fixture 中，不必给每个边界复制完整地图场景；但主题链必须覆盖上表所有知识点。
- [ ] Sam 的“刑责”和受益所有人 15% 若官方核验不支持原文的概括，改文档和 criteria 的具体限定，不能为了满足原候选数字照抄错误法律陈述。

### E3. 分支生成的固定算法

为每个主场景增加一个 `{prefix}_complete` 结束节点。每个决策节点 D 建立：

```text
D + pass              → 下一个决策节点；最后一题 → prefix_complete
D + miss              → D_consequence（非答题节点，rewind_to=D）
D + overgeneralized   → D（保留题干，用专用 feedback 指出过度概括）
D + deferred          → D（由 routes 处理；不走 JSON branches）
```

branch 的 skill_id 按节点评分任务选择现有三个之一；state=pass 或 needs_practice；policy_clause_ids 是 knowledge 子集，最小实现可与 knowledge 相同。

- [ ] branches 固定键 pass/miss/overgeneralized；text_branches 同名映射；choices=[]、allow_text=true。
- [ ] consequence 节点 allow_text=false、choices=[]、knowledge 与原题相同、rewind_to=原题；文本只描述教学后果，不凭空声称真实停职/刑罚已发生。
- [ ] complete 节点 id 必须以 `_complete` 结尾，现有 Store 依赖该约定；末题 pass.effect="completed"。
- [ ] 允许反例必须在 pass 主路径上，不藏在答错才会进入的分支里。
- [ ] 一次性构建 JSON 时可写小生成脚本，但不让运行时随机生成题目。最终提交的是可审阅的 JSON 和生成脚本（若保留）。
- [ ] 推荐新建 `/Users/wang/Documents/ChatGPT/AI hacthon/tools/build_grounded_scenarios.py` 为显式构建工具：读审核后的结构化题目定义，输出 scenarios.json；必须支持 `--check` 比较当前输出并在不一致时 exit 1。若不写生成器，则直接编辑 JSON，不留半生成的双重真源。

## F. B07：开场与辅导落地

### F1. 开场三题

保留现有 screen_clarify/screen_conflict/screen_boundary/screen_complete 节点 id。

- screen_clarify：从 alex_public_gift 制作变式；text_rule=clarify_context；重点要求先确认身份、适用规则、金额，不要求仅凭金额下判决。
- screen_conflict：从 sam_linked_payments 制作变式；text_rule=conflict_awareness；识别关联累计和规避。
- screen_boundary：从 mira_privacy_clock 制作变式；text_rule=communicate_boundary；用一句实际工作回复说明行动、理由和下一步。

- [ ] 每题必须重写自己的 rubric，而非只改 text_rule。借用数据题素材的“沟通题”也按沟通任务评分。
- [ ] 已评估的 pass/miss/overgeneralized 都前往下一题；只记录相应结果，不中断三题流程。deferred 留在当前题，不伪造筛查结果。
- [ ] screen_boundary 保留 category=personal_development，保持两个分类的既有产品结构；npc_id=mira 与 category 不必机械一致。
- [ ] 开场三题不写“已掌握所有法规”；提示这是起点，地图包含独立 Jo 任务。

### F2. Mira：用真实证据选题，静态辅导节点承载内容

不新增 npc_notes 表来完成本步骤。使用 evidence 与 attempts JOIN 得到来源版本；静态复制所有 B06 决策节点成为 ethics-review 的辅导节点，便于恢复与验证。

- [ ] 新建 `Store.coaching_candidates(session_id: str, skill_id: str) -> list[dict]`，SQL 如下：

```sql
SELECT e.id AS evidence_id, e.scenario_id, e.node_id,
       e.observed_response, e.interpretation, e.created_at,
       a.scenario_version
FROM evidence AS e
JOIN attempts AS a ON a.id = e.attempt_id AND a.session_id = e.session_id
WHERE e.session_id = ? AND e.skill_id = ? AND e.scenario_id <> 'ethics-review'
ORDER BY e.created_at DESC, e.rowid DESC
```

- [ ] routes 继续先用 _weakest_skill 获取有证据且最弱技能，再按顺序遍历 candidates；选第一条与当前 scenario_version 一致且 node 存在、具 rubric 的来源。旧版本证据保留但不映射新版题干。
- [ ] 生成辅导节点 id=`coach__{scenario_id}__{node_id}`，复制 text/facts/rubric/knowledge/hint，npc_id=mira；text 前缀只说“Review this case from your record.”，不声称知道学习者未提供的想法。
- [ ] 在 ethics-review 增加 `coaching_sources` 映射，键=`scenario_id/node_id`，值为 coach 节点 id；ScenarioEngine 新增 `coaching_node_for_source(scenario_id, node_id)`，从该映射读，不临时拼出未经校验的节点。
- [ ] 辅导 pass→review_complete；miss/overgeneralized→自身；deferred 留自身；全部 policy ids 来自复制的来源节点。
- [ ] review_no_evidence 保留；找不到兼容来源时显示“没有可用于当前版本的答题记录，请先完成一题”，不谎称用户完全没有历史。
- [ ] create_attempt 增加可选关键字参数 `assisted: bool=False`，SQL assisted 从硬编码 0 改成占位参数；创建 ethics-review 一律传 True。只允许 practice 模式，避免辅导被记作独立验证。
- [ ] 测试四项：无证据→中性页；Sam 弱项→Sam 源题辅导而非礼品；他人 session 不可见；旧版本候选跳过；辅导通过最多 practiced。

## G. B08：校验、测试迁移和规范

### G1. 校验集中在一个入口

新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/content_validation.py`，入口：

```python
def validate_content(content: dict) -> None:
    """Raise ValueError with scenario/node/field context on invalid content."""
```

不要把 schema 校验散落在四个 route。ScenarioEngine.__init__ 在读取 content 后调用；B01–B07 可尚未开启全量必需字段，B08 开启后所有生产节点必须迁移完。

检查顺序固定：
1. corpus 非空、所有 chunk id 唯一；否则错误显示文档索引问题。
2. 每个 npc.scenario_ids、screening_task、TASK_BY_SKILL 的目标存在。
3. 场景 version/start_node/available_modes、所有 next_node/rewind/coaching 目标有效。
4. 学习节点 knowledge 非空且无重复；每个 id 可解析，fictional=false、source 非空。
5. facts.domain/scope/reference_date 是非空字符串；rubric.required 非空且唯一；criteria.keys 与 required 完全一致。
6. reference_answers outcome 属于三个集合；规范化相同文本不得赋予两个不同 outcome。
7. hint.clause_id、branch.policy_clause_ids 均在本节点 knowledge；所有决策节点有 hint。
8. text_branches 三个 outcome 都有；choices=[]，杜绝只藏选项却仍从浏览器接收选择 id 的新内容。
9. 每条主场景 pass 路径经过标记 `counterexample=true` 的允许反例，然后到 complete；不循环。
10. 所有节点从 start_node 或已声明 coaching 入口可达；完成页允许 knowledge=[]，错误后果页不要求 rubric。

### G2. 原测试迁移规则

- 原 test_api.py 有两个同名 answer helper：删除被后者覆盖的 choice 版本，只留 text 版本。
- 事务类测试（幂等、隔离、revision、计时）不删除；输入替换为对应新节点的 reference_answers，期望节点替换为 E2/E3 图。
- 内容类测试（旧 lobster、gift_benign、review_conflict）改成明确新领域测试，不保留虚构场景为生产运行依赖。
- 模型网络行为测试使用独立 test fixture context，保留 fenced JSON、preamble、max_tokens、cooldown、feature flag 全部覆盖。
- B08 结束时两个 evaluator 的 context 是必需关键字参数；删掉 legacy RUBRICS 和旧关键词评分。更新所有调用者及 StubEvaluator，不留下默认 context=None 掩盖遗漏。
- 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/tests/fixtures/grounded_cases.json`，每例明确 scenario_id、node_id、text、expected_outcome、allowed_clause_ids；不从被测 rubric 动态推导所有测试期望，至少边界和反例有独立审阅的固定期望。
- UI 的反例标签用内容字段 counterexample 标明只供内部内容审阅；不要提前告诉学习者哪一题预设允许。

### G3. Contract 测试必须覆盖的字段

- PolicyCard：fictional:boolean default=false；source:string default=""；条件约束通过 Pydantic model_validator 验证，JSON Schema 不表达此约束时由单元测试补足。
- AttemptResponse：assessment_status enum=assessed/deferred/not_requested。
- 409 场景版本冲突；hint_not_available 的 400；B09 /ready 的 200/503。
- 假如新增 response model 必须更新 client/src/api.ts；不向 ScenarioNode 暴露 rubric/reference_answers。
- 将生产 APIs 实际 JSON 响应经过 response_model 验证，确保 source 没被 schema 丢弃。

## H. B09：部署的逐项操作

### H1. 语料是否进镜像，先用证据回答

当前 `.dockerignore` 含 `*.md`，不能仅看本机 corpus 正常就认定镜像有语料。Docker pattern 的真实效果以镜像检查为准。

- [ ] 在 `.dockerignore` 最末添加精确放行 `!server/content/knowledge/*.md`；不放行所有 Markdown，更不放行 .env。
- [ ] 构建后的镜像执行以下命令，要求两个文档都存在、非空；不满足则修正 ignore/COPY 而不是降低预期：

```bash
docker run --rm --network none skilltown:rag-check python -c \
'from pathlib import Path; from server.core.knowledge import corpus; p=Path("/app/server/content/knowledge"); assert (p/"eu_regulation_reference.md").is_file(); assert (p/"eu_thresholds_annex.md").is_file(); assert len(corpus()) > 0; print("chunks",len(corpus()))'
```

### H2. 模型锁文件与构建

- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/content/dense_model.lock.json`，字段固定为 repo_id、revision、model2vec_version、files（相对路径→sha256）、license。真实读取远程模型元信息后写入值；将下载步骤与 runtime 分开。
- [ ] 新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/build_dense_model.py`，读取 lock：使用指定 revision 下载白名单文件到 `/app/models/potion-base-8M`；校验每个 SHA256；有缺失/不符直接 exit 非零。禁止运行时“自动更新 revision”。
- [ ] Dockerfile 在依赖安装后 COPY lock 和构建脚本，再运行下载脚本；这样修改题目不会重新下载模型。
- [ ] requirements.txt 的 model2vec 固定为实际验证版本；若下载脚本使用 huggingface_hub 则显式固定兼容版本，不仅依赖传递安装。
- [ ] knowledge.py 使用 SKILLTOWN_DENSE_MODEL_PATH 默认 `/app/models/potion-base-8M` 的生产值，本地开发默认工程 models/potion-base-8M；通过 Path.is_dir 校验本地目录，移除 from_pretrained 远程备选循环。
- [ ] 对 `_encoder()` 和 `_dense_matrix()` 异常分别记录 failure_reason；dense_available 仅表示 encoder 非空不足以宣称就绪，readiness 必须包括 encode 和矩阵 smoke 成功。

### H3. 预热与 health 的精确语义

新建 `/Users/wang/Documents/ChatGPT/AI hacthon/server/core/rag_runtime.py`，定义：

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RagStatus:
    ready: bool
    retrieval_mode: Literal["hybrid", "sparse", "unavailable"]
    chunk_count: int
    model_revision: str
    reason: str
```

入口 `warmup_rag(require_dense: bool) -> RagStatus`：
- corpus 空→ready=false、unavailable、reason=empty_corpus。
- encoder/矩阵/固定检索成功→ready=true、hybrid、reason=""。
- dense 失败且 require_dense=false、sparse 固定 query 有命中→ready=true、sparse、reason=dense_unavailable。
- dense 失败且 require_dense=true→ready=false、unavailable、reason=dense_required。

- [ ] 在 FastAPI lifespan 中 warmup 一次，将结果放 app.state.rag_status；不要每次 GET /ready 重新编码。
- [ ] /ready 返回上述字段（不返回本地路径和异常堆栈），ready=false 用 503；/health 原 JSON 不变，保证旧 liveness 测试不变。
- [ ] schema 生成 create_app().openapi() 不触发网络预热，预热必须放 lifespan 而非模块导入；单元测试默认 fake warmup，不需要真实权重。
- [ ] 运行期间 dense 搜索异常时，强制模式抛服务不可用并更新 readiness，不退回 sparse 后继续标 hybrid。开发模式允许切 sparse，同时更新状态。测试模拟“预热成功，后续 encoder.encode 抛错”。
- [ ] /ready route 在静态 mount 前注册，Fly 与 Docker HEALTHCHECK 一起指向 /ready，grace/start-period 根据实测冷启动增加。
- [ ] 在 fly.toml 增加 SKILLTOWN_REQUIRE_DENSE="true"；保持单机单 worker。不要误以为增加 worker 免费共享 numpy 矩阵内存。

### H4. 测试清单

新建 test_rag_runtime.py，至少 8 项：空语料、dense 正常、权重缺失且强制、权重缺失且非强制、编码失败、矩阵维度错误、预热后失败状态变化、ready 不触发重复加载。

执行全量 pytest；镜像断网 smoke；容器启动后 `/ready` 返回 hybrid。三者都成功才进入 B10。

## I. B10：报告格式与明确通过条件

新建 `/Users/wang/Documents/ChatGPT/AI hacthon/docs/reports/rag-release-validation.md`，每项只写实际测量，不预填 PASS。

### I1. 资源报告

记录 commit、image digest、CPU 架构、Python/model2vec 版本、model revision、文档 hash、chunk_count、容器内存限制。

测试场景固定为冷启动一次、预热一次、100 次顺序检索、5 并发×20 检索、完整 API 学习链；记录 cgroup memory.peak 或标明采样峰值的局限。

通过条件：语料完整、hybrid=true、零网络下载、零 OOM、峰值≤400MiB（建议门槛）、API 响应契约有效。超限报告真实数值并修正，不把峰值改成平均值。

### I2. 答案矩阵

把 tools/answer_matrix.py 改为读取 G2 的独立 fixture；每例以新会话或独立 attempt 运行，按明确的前驱 pass 样例走到目标 node。进入目标节点的铺路请求也计入真实调用成本，不再承诺总计只有 20 次。

先离线 stub 回归，再在明确模型费用预算下运行真实评估。输出字段：case_id、scenario_id、node_id、expected、actual、assessment_status、feedback_mode、quoted_evidence（如在内部测试适配器可得）、cited_ids、elapsed_ms、setup_call_count、evaluation_call_count。

通过条件：
- 所有允许反例正确通过；禁止把一律拒绝/一律上报当正确。
- 所有预审错误行动不得通过；注入样例不得越过引用/评分边界。
- 关键数字、知悉起点、NIS2 最终报告起点专项全部正确。
- deferred/fallback 单列；任何关键用例 deferred 代表真实模型验收未完成，不按 pass 统计。
- 不宣称矩阵通过证明广泛教育效果。

### I3. React 与演示

本工程 client/package.json 没有 test/e2e 脚本；不要写不存在的 npm test。使用现有 tools/e2e_room.py / smoke_api.py 前先阅读参数和旧节点断言，再更新它们。

手工检查表：360px/390px 宽度、桌面、长 source 卡片、键盘输入、网络失败保留草稿、deferred 保留草稿、刷新恢复、hint、rewind、版本冲突重开、Mira 两个任务均可访问。

录制路径：开场三题→Sam 关联付款→Sam 允许现金→Mira 加密反例→Jo 工时反例→查看真实 source 和 passport。脚本若太长分成主演示和补充片段，不用删反例压时长。

截图/录屏由执行阶段真实产出并检查可打开；规划阶段不创建伪素材。

## J. 每包交接模板（执行 agent 必须填写）

```text
完成包：Bxx
实际修改文件：逐项绝对路径
测试命令：原样记录
实际结果：通过/失败数量，是否调用真实模型
新行为：一个可复现请求或操作
已知限制：只列剩余事实，不冒充完成
提交：实际 commit hash；未提交则明说
下一包：编号与开始前要读取的文件
```

完成 B10 才能提出合并 main。薄记忆、模型统计展示、延迟优化、godot 删除各自另开工作包，遵循上文范围；凭据轮换不等待 RAG 内容完成，但需独立运维执行且不泄漏值。
