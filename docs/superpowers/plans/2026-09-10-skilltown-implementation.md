# SkillTown 实现方案 v0.3：两人 × 两天的 AI 教育网页 Demo

仓库落点：当前工作区即仓库根目录，实施时直接建立 web/、server/、shared/，不再嵌套 skilltown/。

状态：待审核；v0.3 在保留 v0.2 产品范围的基础上，确定两人职责、接口契约、16 小时双人排期和交付门槛。本轮仅更新计划，未开始应用开发。

## 1. 最新范围

- 两天交付可访问的网页，不使用 Godot 桌面客户端作为交付物。
- 合规培训为主要学习路径；明显区分“伦理与合规”“个人发展”。
- 点击 NPC 直接开启任务，或 WASD/方向键移动、靠近后按 E；输入框聚焦时暂停移动快捷键。
- 员工通过 NPC 选择题、追问和短回答接受训练。
- 先用少量情境筛查已有知识，再根据回答更新证据和个人学习建议。
- 无主管端、无团队看板、无企业绩效接口。
- 有剧情后果和重试，但不因一次错误永久封锁学习；答题表现不等于实际违规行为。

## 2. 产品主张

“一个记得你为什么选错、只教你还没掌握内容的 AI 学习小镇。”

必须展示三种区别：普通选择题游戏只有对错；本项目还有理由理解、跨题记忆和定向补学。AI 不是无限闲聊或生成任意合规结论，而是在审核过的场景与知识卡范围内解释、追问和推荐。

## 3. 地图、分类和 NPC

一屏二维小镇，四名 NPC，两个明确分区：

| 分类 | 地点/NPC | 内容 | 优先级 |
|---|---|---|---|
| 伦理与合规 | 餐厅/合作伙伴 Alex | 宴请、利益输送信号 | P0 主线 |
| 伦理与合规 | 礼品店/供应商 Sam | 礼品、披露和审批 | P0 主线 |
| 伦理与合规 | 市政厅/伦理教练 Mira | 针对缺口解释、复测、个人方案 | P0 |
| 个人发展 | 工作室/沟通教练 Jo | 表达边界、给出建设性回复 | P0 轻量支线 |

分类以文字、图标和颜色共同表达；不只依赖颜色。每个 NPC 显示分类、任务标题、预计时长和新任务/建议复习状态。底部常驻点击与键盘说明。地图采用少障碍布局，避免为两天 Demo 开发复杂寻路。

## 4. 员工完整体验

1. 用昵称进入游客会话，明确只使用虚构业务情境，可清除自己的记录。
2. 欢迎卡提供“先试试我会什么”和“直接探索小镇”。
3. 筛查包括 3 个短情境，每个覆盖一个知识点；最多 1 个追问，不做长问卷。
4. 结果用“已有理解证据/建议练习/尚未验证”表示，不把三道题称为完整能力测评。
5. 地图高亮推荐 NPC，但其他地点可自由进入，允许跳过推荐。
6. 对话采用选择、主动追问、简短自由回答三种输入。通过交互逐步揭示关键事实。
7. 根据动作推进预设剧情；错答有情境后果、针对性解释和新案例复测。
8. NPC 读取同一员工的最小能力摘要，下一题针对该缺口；个性化不需要 NPC 全天自主运行。
9. 学习护照展示证据和用时，最后生成 2–3 个具体建议，每项能直接进入对应任务。

## 5. 主线案例：“项目成功了，去吃龙虾吧”

说明：仅凭“吃龙虾”不构成足够判断信息。场景必须交代谁邀请、谁付款、决策关系、透明度和所适用的内部政策。首版显示“虚构公司培训政策”，所有通过标准来源于该政策，不作为普遍法律结论。

### 节点 A：信息不足

Alex：今天项目很成功，我们去吃个龙虾庆祝吧，我来安排。

选项：
- 直接接受。
- 先确认：谁付款，参与者是谁，是否涉及待审批事项，政策是否允许？
- 直接断定所有商务聚餐都属于受贿。
- 自己说一句（自由输入）。

以补齐信息为最佳下一步，而不是强制把所有邀请判断成违规。过度一概而论也触发澄清训练。

### 节点 B：存在明确风险条件

Alex：我们公司付，你也快要审批续约了；别走报销，免得麻烦。

虚构政策条款 ETH-01：与待决业务决定相关、要求隐瞒的利益安排应暂停接受，并通过指定内部渠道咨询或报告；本场景不设通用金额阈值。

选择：
- 按对方建议隐瞒参加。
- 不接受该安排，保留事实并按给定渠道咨询/报告。
- 只要自付一部分就一定没问题。
- 自己写一段回复。

剧情按预审规则推进。正确选择进入回应和记录环节；错误选择进入“未来后果预演”：项目资格被暂停、角色站在城门外，明确标注为教学模拟而非真实处分。显示关键风险点后可立即倒带到决策点。答题记录保留为学习事件，不形成员工行为指控。

### 节点 C：迁移验证

新案例：普通团队内部庆祝，事实条件与前例不同，提供明确可适用的内部规则。员工解释哪些条件改变了判断。另一变体换成供应商送礼，检查是否会迁移而非记住选项位置。

需要展示反例，避免训练出“拒绝一切邀请”的错误规律。验证题不在原题重试中产生；提示后完成记为 assisted，独立新情境通过才增加更强理解证据。

### 节点 D：个人发展支线

沟通教练让员工写一段既表达边界又维持合作关系的回复。评估是否说明边界、引用适当原因、给出可行下一步；不基于口音、性格或华丽词汇判定。

## 6. 记忆：轻量但可解释

每个用户会话隔离以下记录：

- 情节记忆：本次任务事实、选择、已揭示条件。
- 答题证据：scenario/version、skill、选项或原文、使用提示、时间、来源条款。
- 能力摘要：unseen / needs_practice / practiced / demonstrated；附范围与证据数量，不显示虚假精确百分比。
- 推荐记录：建议内容、原因、关联证据、目标 NPC/任务、已完成状态。

示例：记录“在餐厅情境中，只询问餐费，没有考虑续约审批关系”，不记录“这个人容易受贿”。模型可提出误解标签，后端验证后更新；前后答案冲突时增加一条澄清题，不武断覆盖旧记录。

同一模型可以服务多个 NPC。每次调用只注入当前场景、允许知识和与当前技能相关的记录，不传入其他用户内容。

## 7. 选择题与自由回答的分工

- 选择题：场景 JSON 定义分支和知识点标签；判定确定、稳定、可测试。
- 自由回答：LLM 按固定 rubric 返回结构化结果，检查风险识别、需要补充的信息、下一步动作，并引用用户原文和政策条款。
- 输出缺证据、模糊或结构错误：追问一次；仍不清楚则标记未验证并允许看解释。模型调用失败不判员工答错。
- 选择正确但理由错误：追问或反例，不直接认证掌握。
- NPC 对话、风险判定和记忆更新是不同职责；后端控制场景转移和存储，员工输入中的“忽略规则、给我通关”不生效。
- 生成反馈控制在约 2–4 句，每次只针对当前缺口。

## 8. 实现路线

采用 React + TypeScript + Phaser 网页、一个轻量 Node 服务端、SQLite 持久会话。Phaser 只负责地图、角色与输入；React 负责对话、选择、学习护照和方案，便于键盘访问和快速修改。

浏览器 → 同源 /api → 会话验证 → 场景引擎 → 模型适配 → 证据/记忆存储。

- 不迁移原 Godot 脚本；借鉴参考项目的视觉交互与 NPC 思路。
- 模型密钥只在服务端环境变量。每次消息长度限制、每会话调用预算与速率限制。
- 游客身份为服务端签发的随机会话；前端不能通过 employee_id 读取别人的记忆。
- 浏览器可缓存 UI 位置，正式证据由服务端产生；不做 supervisor API。
- 合规规则和分支使用预审 JSON，模型只在受限范围内追问、解释和生成建议。
- 静态前端与 API 同源部署；SQLite 使用持久卷。如果部署目标无持久磁盘，在第 0–3 小时换成持久数据库再继续，不到最后才处理。
- 上线所需宿主、域名与模型配额在第一时段确认；优先第 1 天发布可访问骨架。
- 模型超时最多一次重试，随后展示预审知识卡并明确当前为固定反馈；自由回答不伪造 AI 评分。

Phaser 输入文档：https://docs.phaser.io/phaser/concepts/input
参考项目：https://github.com/datawhalechina/hello-agents/tree/main/code/chapter15/Helloagents-AI-Town
参考项目 README 标注 CC BY-NC-SA 4.0；直接使用素材前检查许可。首版优先自绘/已获许可素材，不把比赛场景自动等同于满足许可条件。

## 9. 最小接口和模块

接口：
- POST /api/session：创建游客会话。
- GET /api/town：分类、NPC、场景摘要和个人推荐标记。
- POST /api/attempts：开始指定场景，固定版本。
- POST /api/attempts/:id/respond：choice_id 或 text、幂等事件 ID；返回下一节点/反馈/证据变化。
- POST /api/attempts/:id/hint：记录帮助并返回相关知识卡。
- GET /api/passport：个人能力摘要、证据、时长。
- POST /api/recommendations：根据已验证记录生成可点击学习方案。
- DELETE /api/session：清除该会话记录并退出。

模块：TownScene、DialoguePanel、LearningPassport、LearningPlan；服务端 ScenarioEngine、AnswerEvaluator、MemoryStore、RecommendationService、SessionGuard。不新增多智能体调度平台或向量库。

## 10. 两人、两天交付计划

按每人每天约 8 小时，合计 32 人时预算；不按连续 48 小时开发安排。A 为偏前端成员，B 为偏 AI/后端成员；实际姓名不影响边界。全部界面和剧情默认中文，政策明确为虚构训练政策。

| 时段 | A：体验、游戏与发布操作 | B：内容、AI、状态与数据 | 联合交付门槛 |
|---|---|---|---|
| Day 1 0–1h | 定布局、颜色、角色、页面流程 | 定能力标签、主线分支、模拟政策 | 共同冻结场景 ID、API 字段和删减清单 |
| Day 1 1–3h | React/Phaser 骨架、NPC 点击、分类标签；部署静态页 | Node API、游客会话、SQLite、返回真实场景 JSON；部署 health | 一个公网域名能打开页面和请求 API |
| Day 1 3–5h | 对话框、选项、输入框、提示/倒带按钮；先接真实 API | 场景引擎、主线分支、事件幂等、证据记录 | 联调：一次选择真实保存，下一节点真实返回 |
| Day 1 5–7h | WASD/E、输入焦点隔离、后果预演、轻量动画 | 接一个真实模型调用，固定 rubric 评短回答并给反馈 | 同一网页至少跑通一次真实 AI 回答 |
| Day 1 7–8h | 修主线 UI 和部署问题 | 修状态、超时、证据问题 | 在线跑通“筛查→主线→反馈→结果”的基础闭环 |
| Day 2 0–2h | 学习护照、结果分组、证据和时长 | 能力聚合、跨 NPC 记忆、个性化任务推荐 | 两种不同历史产生不同推荐 |
| Day 2 2–4h | 可点击方案、NPC 推荐状态、个人发展轻支线 | 完成礼品迁移案例、短回答校验和支线反馈 | 所有四名 NPC 有可用内容，主线可复测 |
| Day 2 4–6h | 输入/刷新/窄屏/键盘测试；冻结 UI 功能 | 会话隔离/模型失败/重试/评分测试；冻结 API | 功能冻结，后续只修缺陷 |
| Day 2 6–8h | 演示截图、录屏、交互排练、发布检查 | 环境变量、持久化、成本上限、演示重置检查 | 公网链接、完整路演和故障备选路径 |

每日最后一小时都用已部署版本验收，而不是各自在本机展示。时段为工作窗口，不是保证完成时间；排期假设已有可使用的模型额度、允许部署的账号和基本网页开发经验。

## 11. 验收

1. 新浏览器打开部署链接即可进入；页面明确两个 learning 分类。
2. 点击 NPC 与 WASD+E 都可打开同一任务；输入文字不会触发移动。
3. 合规主线至少有“补齐信息、识别风险、纠正过度拒绝”三类决策。
4. 正确答案进入下一场景，错误答案有解释、预演和立即重试，不永久锁出。
5. 原题重试通过只标记练习完成；新案例独立回答才标记 demonstrated。
6. 再访另一个 NPC 时能展示基于已发生答案的定向提示，而非预设假记忆。
7. 个人方案的每条建议都有证据和可进入任务；没有答过的能力显示未验证。
8. 两个浏览器会话互不见数据；刷新保留自身进度；删除清除记录。
9. 模型故障、重复点击、无效回答不导致误判或重复写入；模拟反馈有标识。
10. 准备约 20 条自由回答测试，覆盖正确、误解、模糊、提示注入和场景外问题；展示失败计数和人工复核，不宣称教育效果已经实验证实。
11. 总用时分列活动与等待，不把离开页面算作学习；不把通关次数当培训有效性证明。

## 12. 路演重点

三分钟演示：收到龙虾邀请 → 做出有问题的选择 → 出现可倒带的后果预演 → AI 指出具体遗漏 → 换一个 NPC，系统记得该遗漏并针对性追问 → 独立新案例通过 → 生成个人学习方案。

核心卖点是“错误能变成个性化教学记忆”，不是 NPC 数量、处罚力度或全镇自治。未来商业化可销售企业场景包与定制政策，但本次不增加组织管理功能。


## 13. 分工、文件归属和协作

### A：前端体验负责人 + 发布操作负责人

交付：地图、分类、四 NPC、点击/WASD/E、对话选择与输入、后果预演、学习护照、推荐方案、公网页面。

文件归属（计划路径，尚未创建）：
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/game/TownScene.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/components/DialoguePanel.tsx
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/components/ConsequenceOverlay.tsx
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/components/LearningPassport.tsx
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/components/LearningPlan.tsx
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/api.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/web/src/styles.css
- /Users/wang/Documents/ChatGPT/AI hacthon/web/public/assets/
- /Users/wang/Documents/ChatGPT/AI hacthon/web/tests/e2e.spec.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/Dockerfile
- /Users/wang/Documents/ChatGPT/AI hacthon/README.md

A 不在 UI 中实现“正确答案→能力升级”的逻辑，UI 只渲染服务端返回。搭建期间可使用同契约 fixture，但界面应显示“开发模拟”，正式 Demo 使用真实 API。

### B：AI/后端负责人 + 学习内容负责人

交付：预审剧情和政策、服务端会话、场景引擎、模型输出校验、记忆、个性化方案、持久化及失败回退。

文件归属：
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/index.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/session.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/scenario-engine.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/evaluator.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/memory-store.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/recommendations.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/src/db.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/content/scenarios.json
- /Users/wang/Documents/ChatGPT/AI hacthon/server/content/demo-policy.md
- /Users/wang/Documents/ChatGPT/AI hacthon/server/tests/engine.test.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/tests/evaluator.test.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/server/tests/session.test.ts

B 使用一个模型服务，不引入 HelloAgents 运行时、向量数据库或自治 Agent 调度框架，借鉴参考项目的角色与记忆设计即可。Node/TypeScript 与前端统一语言，Express 为薄 HTTP 层、Zod 校验输入和模型输出、SQLite 存储；包版本在首小时实测锁定。

### 共享边界

B 负责契约初稿，A 评审；契约定稿后 B 单点修改并通知 A：
- /Users/wang/Documents/ChatGPT/AI hacthon/shared/contracts.ts
- /Users/wang/Documents/ChatGPT/AI hacthon/shared/fixtures.json

A 负责根构建/部署文件，B 提供服务端启动命令、端口、数据库路径和环境变量清单。第一小时确定后双方避免同时改同一文件。A 分支 codex/web-experience；B 分支 codex/learning-engine；建议各自 checkout，不共享正在切换的工作目录。每 2–3 小时集成一次，不等第二天下午才合并。

## 14. 内容预算：有深度的一条主线，而非大题库

能力标签固定：
- clarify_context：先补齐关键信息。
- conflict_awareness：识别决策关系和隐瞒安排。
- communicate_boundary：表达边界并提出合适下一步。

内容限定为：
- 三个筛查题；每题一个不同关键能力。
- 餐厅主线约六个节点：邀请、追问、风险揭示、后果、解释、继续。
- 礼品店两个短变体：风险迁移＋条件不同的反例，防止学成一律拒绝。
- 市政厅一份根据缺口选择的辅导卡和复测入口。
- 工作室一个自由回答任务，写一段回应。

每个节点至多三个主要选项加一个自由输入入口。正式自由回答评估优先覆盖风险判断和回应表达两个关键节点，其他节点可用确定选择；这是控制 B 工作量的主要措施。预筛和独立复测使用不同节点 ID/题面。

B 写内容，A 在第一天首小时和发布前做逻辑复核。虚构政策集中为少量带 ID 的条款，不做 PDF 自动导入、政策管理或法律检索产品。

## 15. 最小契约：前后端第一小时共同确认

### RespondRequest

字段：client_event_id（随机 UUID）、expected_revision（整数）、kind（choice/text）、choice_id 或 text，二选一。attempt_id 在 URL，员工身份仅来自服务端会话。

### RespondResponse 样例

以下为明确标注的接口演示数据，不是已运行结果。

```json
{
  "attempt_id": "attempt-demo-01",
  "revision": 3,
  "node": {
    "id": "dinner-risk-02",
    "npc_id": "alex",
    "category": "ethics_compliance",
    "text": "我们公司付，你也快要审批续约了；别走报销，免得麻烦。",
    "choices": [
      {"id": "accept_hidden", "label": "接受并按对方要求隐瞒"},
      {"id": "pause_consult", "label": "不接受该安排，并按给定渠道咨询"},
      {"id": "split_bill", "label": "只要自付一部分就一定没问题"}
    ],
    "allow_text": true
  },
  "feedback": null,
  "effect": "none",
  "learning_updates": [],
  "is_complete": false,
  "feedback_mode": "scripted"
}
```

约定：
- category 仅 ethics_compliance / personal_development。
- effect 仅 none / consequence_preview / rewind_available / completed。
- feedback_mode 仅 scripted / ai / fallback；AI 失败时前端明确显示固定反馈。
- learning_updates 返回 skill_id、state、evidence_id、assisted，不返回评分隐藏答案。
- effect 仅驱动画面，不具有更改学习状态权限。
- HTTP 409：前端拉取 GET /api/attempts/:id 恢复最新状态；新增该读取接口用于刷新和冲突恢复。
- HTTP 429：显示等待并保留输入；HTTP 503：提示模型暂不可用，保留回答，记录为未验证。
- 前端重复 client_event_id 不重复写入；同一 key 配不同内容返回 409。
- NPC 和任务展示信息由 /api/town 返回，避免 A/B 各自硬编码不同 ID。

方案生成采用“规则选任务，AI 解释原因”：服务端依据未覆盖/待练习技能选择已有任务，模型只润色与证据相符的建议。后端核验 task_id 和 evidence_id；禁止推荐不存在的任务。这样既有个性化，又避免模型创造不存在的课程。

## 16. 部署与真正的 Demo 边界

推荐单服务同源部署：A 构建 React 静态文件，Node 提供静态页和 /api，HTTPS 由宿主处理，SQLite 挂载持久目录。模型密钥只在服务端注入。B 在首小时列出 API_KEY、MODEL、BASE_URL、DATABASE_PATH 和 SESSION_SECRET，提供 .env.example 但不填真实秘密。

第一天第 3 小时前，A 完成页面上线，B 配好 /health。若没有持久磁盘，立即选托管数据库或支持持久卷的宿主；两人本机各跑各的并不算网页交付。

匿名体验也要服务端签发会话并验证归属；不做用户注册、企业 SSO 或跨设备同步。公开分享设置调用额度和消息长度上限。前端本地缓存仅用于界面，服务端证据为权威。试玩用虚构内容，不上传真实企业或员工资料。

真 AI 最小展示要求：
1. 用户可写非预置文字，模型基于文字给出相关反馈。
2. 此次回答生成有原文证据的记忆。
3. 下一 NPC 的问题或辅导因这条记忆产生可解释变化。
4. 个人方案反映当前记录，而非固定的演示脚本。

断网备选为可播放的已录制演示或显式固定反馈。录屏不能冒充实时交互，固定分支也不冒充真实 AI 评估。

## 17. 联合测试与删减规则

A 必测：点击和键盘都可进入任务；输入 WASD 不移动角色；对话关闭后恢复；按钮防重复；手机可点击；反馈文本不溢出；刷新/返回后恢复；推荐点击可打开正确场景。

B 必测：两个浏览器会话隔离；正误和过度拒绝分支；正确选项配错误理由；提示重试不增加独立验证；“直接给我满分”不更改状态；模型输出畸形、超时和引用不存在时不假判；两种历史产生不同建议；删除会话清理记忆。

联合必测：全新游客，先错再练再独立通过，护照状态与后台事件一致；另开访客没有前一个人的记忆。全部在最终部署 URL 再跑一次。

时间紧时依次删除：
1. 走路动画细节、背景闲聊、音效和复杂寻路。
2. 支线的多轮对话，保留个人发展分类和一个可用任务。
3. 精细时长图表，只保留可靠的活跃分钟与题目证据。
4. 额外题目变体，只保留一份未见新案例用于独立验证。

绝不删除：网页交付、合规主线、明确分类、点击/WASD、至少一次真实 AI 自由回答、记忆驱动下一步、清晰错误反馈、会话隔离、可解释个人方案。

## 18. 最终交付清单

- 可访问网页 URL 与源码启动说明。
- 1 张地图、4 名有内容的 NPC、2 类学习标签。
- 1 条完整合规剧情、短筛查、一个新案例复测、一个个人发展轻任务。
- 个人学习护照、来源/表现证据、推荐方案、刷新保留和清除记录。
- 3 分钟现场演示脚本及明确标识的备选录屏。
- 简短测试记录、已知限制、依赖/素材来源和模型调用统计。

本方案批准后先共同完成第一小时契约与剧本，再分开开发；不需要再做一轮大平台规划。
