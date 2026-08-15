# 赛题评分映射与答辩口径（当前单运行链路版）

## 作品完整性

- 画像：创建、编辑并进入统一 LearnerModel。
- 诊断：双领域题库、服务端判分、自适应诊断与错题解析。
- 协作职责：Orchestrator 控制 Risk Router、Generation、ProofGraph、Review、Critic、Judge 等角色和服务。
- 资源：讲义、实操、测试、Evidence 溯源、笔记与收藏。
- 闭环：测试/实操/主观反馈写回掌握度，并生成后续学习动作。

## 技术创新性

- Orchestrator 集中控制状态迁移、预算和有限修订，避免 Agent 自由互调。
- Fast / Standard / Strict 风险路由按需激活审核角色。
- Claim → Evidence → Validator → ValidationResult 形成 ProofGraph 发布约束。
- BM25、向量、图扩展、版本过滤、RRF、MMR、ConceptGain 与 SourceGain 形成混合检索链。
- 可插拔领域包使 ROS2 与 C 语言复用同一工作流。
- 可配置服务端模型；未配置 LLM 时仍在同一 API、同一状态机和同一验证链中使用证据约束确定性生成器。

## 用户体验

- 只有一套正常运行链路，不存在独立模拟后端或假数据模式。
- HarmonyOS 模拟器、真机只是访问同一 FastAPI 后端的不同网络入口。
- 所有按钮具有按压、焦点和禁用反馈；选择项具有持续高亮。
- 失败页面提供重试、重新诊断、API 检查或离线快照恢复等真实路径。
- 测试、实操、证据、笔记和学习路径均可交互。

## 工程价值

- 本地开发可使用 SQLite，Docker 部署使用 PostgreSQL；二者都是同一后端代码路径。
- Admin 文档上传、切片、审核和统一知识检索。
- 60 组运行时功能回归作为内部一致性检查。
- 反馈幂等、掌握度原子 upsert、生产 Admin 鉴权、上传大小限制和本地路径脱敏。
- `tools/validate_project.py` 明确禁止重新引入独立 Demo runtime。

## 答辩边界

- 内部回归指标验证系统功能一致性，不等同于独立专家教学质量评测。
- 只有实际配置外部模型时才声明使用对应 LLM。
- `LLM_PROVIDER=disabled` 表示同一后端使用证据约束确定性生成器，不是另一套演示系统。
- 离线能力限于反馈队列、工作流快照、笔记和收藏；不宣称后端断开后仍能生成新的正式学习资源。
