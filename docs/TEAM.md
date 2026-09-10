# 两人分工与协作

## 成员

- A：前端与游戏负责人，GitHub：[@muzhi-hac](https://github.com/muzhi-hac)。
- B：AI、后端与内容负责人，GitHub：[@Isso-W](https://github.com/Isso-W)。
- 已向 Isso-W 发出仓库 write 邀请，目前待接受。A 的 GitHub Assignee 已绑定；B 的 #3/#5/#6 已在标签和正文明确分工，但邀请未接受，实际 Assignee 暂为空；共同任务 #1/#8 当前仅绑定 A。接受邀请后再补绑 B。

## 文件归属

A：web/、Dockerfile、根构建/部署配置、README 中的启动与发布说明。
B：server/、shared/contracts.ts、shared/fixtures.json、内容和评分配置。
共享契约由 B 提交、A 审核。改变字段、枚举、错误码前通知对方；不要各自维护独立 ID 列表。

## 分支

- A：codex/web-experience
- B：codex/learning-engine
- 集成：main

每人使用自己的克隆目录。在角色分支工作，通过 PR 集成到 main。每 2–3 小时集成一次，避免最后才合并；PR 写明关联 Issue、测试和演示方式。没有配置强制分支保护时也遵守此流程。

## 第一天

共同首小时：虚构政策、主线剧本、三个能力标签、接口契约。
A：地图、分类、点击/WASD/E、对话框、选项、后果预演、页面发布。
B：会话、场景引擎、主线分支、持久记录、一次真实 AI 自由回答。
联合验收：部署链接上能走完主线；一次选择保存并返回下一节点；一次自由回答收到真实 AI 反馈。

## 第二天

A：护照、来源证据、个人方案、推荐入口、轻量支线和交互测试。
B：跨 NPC 记忆、礼品迁移案例、方案生成、异常回退和隔离测试。
最后半天冻结功能，联合测试与路演。预计总开发预算 32 人时，不按连续 48 小时工作安排。

## 避免踩坑

- 前端不保存隐藏答案，不自行判断技能升级。
- 模型不自由修改政策或业务状态；服务端核验输出。
- 训练后原题通过不等于新情境独立验证。
- 不上主管端、语音、大题库、向量数据库或全镇自治框架。
- 模型故障不判答错，固定反馈与录屏明确标识。
- 两个访客不串记忆，进度刷新可恢复，可清除自己的数据。
- 前端构建与后端同源，部署宿主/模型额度/持久存储第一天前半段确认。

## 任务查找

Issues 标签 owner:A、owner:B、owner:joint；milestone 分为 Day 1 与 Day 2。具体依赖和验收以各 Issue 为准。

## 已创建任务

| Issue | 负责人 | 内容 |
|---|---|---|
| [#1](https://github.com/muzhi-hac/skilltown/issues/1) | @muzhi-hac + @Isso-W | [共同][D1] 冻结主线剧本、能力标签与 API 契约 |
| [#2](https://github.com/muzhi-hac/skilltown/issues/2) | @muzhi-hac | [A][D1] 网页小镇、分类与点击 / WASD 交互 |
| [#3](https://github.com/muzhi-hac/skilltown/issues/3) | @Isso-W | [B][D1] 游客会话、场景 API 与持久任务状态 |
| [#4](https://github.com/muzhi-hac/skilltown/issues/4) | @muzhi-hac | [A][D1] 培训对话、选项与可倒带后果预演 |
| [#5](https://github.com/muzhi-hac/skilltown/issues/5) | @Isso-W | [B][D1] 合规主线内容与真实 AI 自由回答评估 |
| [#6](https://github.com/muzhi-hac/skilltown/issues/6) | @Isso-W | [B][D2] 学习记忆、迁移复测与个性化推荐 |
| [#7](https://github.com/muzhi-hac/skilltown/issues/7) | @muzhi-hac | [A][D2] 学习护照、证据与可点击个人方案 |
| [#8](https://github.com/muzhi-hac/skilltown/issues/8) | @muzhi-hac + @Isso-W | [共同][D2] 联调、安全边界、部署与三分钟路演 |
