# 知衡·ProofGraph 合并代码审计（2026-08-15）

## 1. 本次合并结论

### 输入代码
- 包 A：`H-SmartLearn---2026HarmonyOS-main.zip`
- 包 B：`H-SmartLearn---2026HarmonyOS-main (1).zip`

两个压缩包不是简单的“新版本覆盖旧版本”，而是并行分支：
- 包 B 更完整地实现了持久化 LearnerModel、自适应诊断 API、信息增益选题、120 题题库、工作流暂停/恢复、前端诊断类型定义，以及更完整的 Planner/Retriever。
- 包 A 增加了独立的 Beta/BKT 算法服务，并将固定测评评分从经验加权分升级为按难度更新的 BKT/Beta 后验。

### 合并策略
以包 B 为主干，保留其自适应诊断和数据库模型；从包 A 合入：
1. `backend/app/services/bkt_service.py`
2. `backend/tests/test_diagnosis_service.py`
3. 固定测评 API 的 BKT/Beta 顺序更新逻辑
4. 固定测评错误标签 → `misconceptions` 聚合输出
5. assessment schema 的 `misconceptions` 字段

没有直接用包 A 的旧 `DiagnosisAgent` 覆盖包 B，因为包 B 已把“选什么题”和“答案如何更新学情”拆成 `InformationGainDiagnosisService` + `LearnerModelService`，直接覆盖会破坏持久化自适应诊断主链。包 A 的目标/先修逻辑在包 B 的 prerequisite-aware diagnosis 与 posterior-driven planner 中已有对应实现。

## 2. 合并后的验证结果

已通过：
- `python tools/validate_project.py`
  - status: passed
  - ETS: 26
  - registered pages: 10
  - button contracts: 69
- `python -m compileall -q app tests`
  - 通过
- `python -m pytest -q tests/test_diagnosis_service.py`
  - `33 passed`
- `python backend/tools/validate_ros2_knowledge_data.py`
  - EvidenceUnit: 300
  - Concept: 50
  - Skill: 10
  - AssessmentItem: 120
  - PracticeTask: 20
  - ValidatorSpec: 10
  - benchmark seed: 100
  - skill/concept graph DAG: true
  - 结构/引用完整性校验 PASS

未能在当前隔离环境执行全部 DB 测试：`tests/test_information_gain.py` 收集阶段缺少 `aiosqlite`。项目 `requirements.txt` 已声明该依赖，因此这里记录为“环境依赖未安装”，不能据此判定代码失败。

特别注意：知识库结构校验 PASS 只证明 schema/引用关系一致，不等于 300 条 claim 已人工逐条核验，也不等于 validator 已真正执行。

## 3. 对照项目报告的实现状态

状态定义：
- ✅ 已实现：核心代码路径存在且可基本运行；不代表报告里的量化验收指标已经被实验验证。
- 🟡 部分实现：已有主要骨架，但缺关键机制、工程闭环或正式验收。
- ❌ 未实现：报告要求的核心机制尚无对应代码/流水线。
- ⏸ 可延后：报告明确属于 P1/P2/离线增强，不应阻塞 P0。

| 阶段 | 状态 | 当前代码已有 | 主要缺口 |
|---|---|---|---|
| 00 指标/风险/基线 | 🟡 | benchmark seed、基础测试与数据校验 | 冻结三类基线、Cohen κ、统一指标字典、完整统计口径与自动回归报告 |
| 01 技能本体/数据契约 | 🟡 | 50 concepts、10 skills、300 evidence、120 assessments、20 practice、10 validator specs | 报告目标 500–800 原子证据；`human_verified=0`；schema migration/provenance 验收仍需加强 |
| 02 先修图/证据图/通信图 | 🟡 | 技能 DAG、概念 DAG、图扩展检索、Planner prerequisite path | 正式 Claim/Evidence 异构证明图、动态 Agent 通信图、发布前图验收自动化 |
| 03 概率学情数字孪生 | ✅/🟡 | 持久化 concept Beta 后验、掌握概率/不确定性、skill 聚合；固定测评已合入 BKT | 低维能力向量 θ、显式置信区间、Huber/截尾等鲁棒更新、ECE/Spearman/95% coverage 实验 |
| 04 信息增益自适应诊断 | ✅/🟡 | 自适应 session、prerequisite-aware 候选、期望不确定性下降 + coverage/time/fatigue、停止条件、120 题库 | 当前实现更准确地说是“expected uncertainty reduction”而非严格互信息；缺题量降低 40%、Top-3 误概念召回等验收 |
| 05 混合检索 | ✅/🟡 | BM25 + vector + RRF + graph expansion + version filter + MMR | 向量索引仍需持久化/增量化；显式 LearnerFit/Risk 通道不足；Recall@10/版本冲突/P95 尚未正式测量 |
| 06 MMR/概念覆盖 | 🟡 | 标准 MMR、来源/概念轻量后处理 | 报告公式中的贪心 `ConceptGain`、`SourceGain`、概念位图、来源配额未完整落进 MMR 选择器；缺 25ms/覆盖消融 |
| 07 稀疏多 Agent | 🟡 | Diagnosis/Planner/Retrieval/Generation/Review/Feedback + Orchestrator，trace 存在 | 尚未形成报告定义的 DomainExpert/Tutor/Critic/Judge 逻辑职责 + 1/2/4 风险路由；缺结构化 token 预算/贡献评估 |
| 08 ProofGraph + 关键声明验证 | 🟡 | 证据引用、版本信息、risk_level、validator_ids、Review 的危险命令/版本/回滚检查 | 无正式 `ClaimGraph/claim_id` 主模型；ValidatorSpec 多为数据，缺真实静态验证器/隔离沙箱；缺条件 Critic/Judge 与确定性融合 |
| 09 对抗审核/稳定停止 | ❌/🟡 | 工作流有有限修订思路 | 无 JS 分歧触发、NewEvidence/RiskReduction 停止量、角色历史可靠性/Brier、标准1轮/严谨2轮的统一机制 |
| 10 个性化学习路径 | 🟡 | 基于先修 DAG + learner posterior 的合法路径；mastered prerequisite 可跳过 | 无一至两步前瞻；无“最快/最稳/最深入”Pareto 多路径；学习增益/完成率验收未做 |
| 11 冷启动/迁移 | 🟡 | Beta 先验冷启动；领域包已支持 ROS2/C 基础结构 | 线性/树校准器、第二领域正式迁移实验、5题推荐准确率；OT 按报告可离线延后 |
| 12 鲁棒/安全/尾部风险 | 🟡 | Review 对 sudo/版本/回滚等有规则；实践资源带 risk/validator/rollback | 真正无外网/只读/限时 sandbox；prompt injection 策略；漂移/异常画像保护；CVaR/DRO 可保持离线 |
| 13 性能/通信/缓存 | 🟡 | 结构化 workflow state、trace；部分 `lru_cache` | 检索/画像/风险并行；query/version/ability cache；token/LLM-call/P95 监控；1/2/4 调用预算；向量索引避免每请求重建 |
| 14 高阶数学审计 | ⏸ | 未做 | 报告明确为离线 P2，不应抢 P0 时间；暂不实现是正确取舍 |
| 15 统计评测 | 🟡/❌ | benchmark seed=100、已有测试 | 300–500 task blind set、数千 claim 标注、双人标注、95% CI/UCB、分层报告、自动回归与核心消融流水线 |
| 16 因果评估 | ⏸/❌ | 无正式流水线 | A/B、倾向、双重稳健等；初赛前可做最小 A/B，不应早于 P0 闭环 |
| 17 工程交付/可观测性 | 🟡 | FastAPI、HarmonyOS 前端、Docker Compose、workflow trace、profile/report/resource/graph 等页面 | 自适应诊断前端 API 已定义但 QuizPage 仍主要走固定 assessment；缺完整 observability 管理页、Validator service、clean-room 一键部署证明、版本哈希事件溯源 |

## 4. 当前已经比较有竞争力的部分

1. **M2（轻量学情 + 自适应诊断）已经不是空壳**
   - 持久化 Beta 后验
   - 题目按先修关系筛选
   - 根据当前不确定性动态选下一题
   - 题量有停止条件
   - 120 题题库
   - 固定测评也已合入 BKT，不再使用纯经验权重

2. **M3（混合检索）主体已成型**
   - BM25
   - 向量检索
   - RRF
   - 图扩展
   - 版本过滤
   - MMR
   - cited evidence pinning

3. **知识库已经具备可工程化的数据骨架**
   - Evidence / Concept / Skill / Assessment / Practice / Validator 之间引用基本闭合
   - DAG 校验通过
   - 两个来源域（docs.ros.org / docs.nav2.org）

4. **工程形态已经超过“几个 Prompt 串联”**
   - 后端 API、数据库模型、workflow state、Agent trace、HarmonyOS 页面、领域包、校验脚本、测试均存在。

## 5. 当前最大缺口（按答辩风险排序）

### P0-1：Risk Router + ProofGraph + Validator 执行闭环
这是当前最大的结构性缺口。

建议最小实现：
1. `PreRisk = 0.35*DomainRisk + 0.25*Uncertainty + 0.25*RetrievalWeakness + 0.15*Novelty`
2. 三档：fast / standard / strict
3. fast：DomainExpert 1 次
4. standard：生成 + 对争议声明 Critic 1 次
5. strict：关键声明验证 + 条件 Judge，最多 4 次模型调用
6. 新增 `Claim`、`ClaimEvidenceLink`、`ValidationResult`
7. 高风险 claim 没有 evidence 或 validator 失败 => 删除/降级/拒答
8. trace 记录 route、风险分数、evidence、validator、最终 disposition

### P0-2：把 ValidatorSpec 从“字段”变成“真的执行”
当前 `validator_ids` 很多，但真正可执行验证还不足。

建议先做最小白名单：
- shell 静态检查
- ROS2 命令格式/发行版检查
- YAML/XML/JSON schema 检查
- Python `compile()` / AST 检查
- 受限 subprocess：timeout、无设备、临时目录、资源限制

不要一开始做通用 Docker 沙箱；先让 10 个 validator specs 真能产生 `pass/fail/unknown + reason + runtime_ms`。

### P0-3：把 M3 做成“可测的检索系统”
当前功能多，但比赛需要指标证据。

必须补：
- ≥100 条 retrieval gold set
- Recall@10
- 版本冲突召回率
- Top-10 重复率
- MMR 选择耗时
- 总 P95
- Top-k vs MMR+ConceptGain 消融

工程优化：**禁止每次请求重建全部向量索引**，改成启动时/数据变更时构建，query 只编码一次。

### P0-4：补齐概念位图 + 来源配额
把当前 MMR 从：
`relevance - redundancy`
升级为：
`relevance - redundancy + concept_gain + source_gain`

实现很轻：
- 每条 evidence 预存 `concept_bitset`
- greedy 时 `new_bits = evidence_bits & ~covered_bits`
- 同一来源设置软/硬 quota
- 达到 token budget 或核心概念覆盖饱和立即停止

这比上 DPP/TDA/挂谷都更符合报告。

### P0-5：统一“固定测评 BKT”和“自适应 concept Beta”两个状态源
合并后两套机制都存在，这是好事，但现在还有一致性风险。

建议固定测评提交后：
- 根据 assessment item 的 `concept_ids`
- 同步调用 `LearnerModelService.update_from_answer()`
- 这样 Planner/Diagnosis 读到的是同一套持久化 posterior

否则可能出现：固定测评报告说“会”，LearnerModel 仍是 0.5 prior。

## 6. 可完善但暂时不要优先做的内容

### P1
- Beta 95% credible interval
- 鲁棒画像更新（response time median/MAD、单步变化上限）
- 三条 Pareto 路径：fastest / safest / deepest
- 管理端 observability dashboard
- prompt injection corpus + failure injection
- 自动消融脚本和 CI regression
- 自适应诊断的 HarmonyOS 真正交互页（当前 API/types 已有，主要页面尚未完全接入）

### P2 / 初赛可不做
- OT/Sinkhorn
- TDA
- 随机矩阵
- Fourier/小波
- 挂谷方向覆盖
- 自然梯度
- 深度 POMDP / 强化学习
- 通用范畴论框架

这些在项目报告里本来就不是在线主链路；提前实现反而偏离“性能优先、P0 闭环优先”的设计原则。

## 7. 建议下一轮开发顺序

1. 跑通合并代码全部依赖和 DB tests，消灭 integration regression。
2. 固定测评 → LearnerModel posterior 同步。
3. M3 gold set + 检索指标，先证明当前 BM25/vector/RRF/version/MMR 真达标。
4. MMR 加 concept bitmap/source quota，并做 Top-k 消融。
5. 实现 PreRisk 三路径路由和 1/2/4 预算。
6. 实现 ClaimGraph + 最小 Validator executor。
7. Review 拆成条件 Critic；冲突才启用 Judge。
8. 做错误版本/危险命令/伪来源三类失败注入演示。
9. 之后再做路径多目标、dashboard、盲测统计。

**结论：当前代码已经把“学情—诊断—检索—生成—反馈”的前半个闭环做得比较实；真正决定 ProofGraph 名字能否成立的“风险路由—声明证据图—可执行验证—条件 Critic/Judge”还没有闭环。下一阶段不应继续堆高阶数学，应集中完成 M3 验收并尽快进入 M4。**
