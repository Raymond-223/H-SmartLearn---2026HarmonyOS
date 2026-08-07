# ProofGraph Agent60 + KB2.1 整合状态

## 合并基线

- Agent 基线：`H-SmartLearn-Merged-v1.7.3-agent60-enhanced (1).zip`
- 知识数据基线：`H-SmartLearn-ProofGraph-v1.7.3-KB2.1-current(1).zip`
- 合并原则：以 Agent60 工程为主干，覆盖 ROS2 KB2.1 数据包，并修改数据加载、数据库种子、Workflow、Generation/Review/Retrieval、Knowledge API 与 HarmonyOS API 类型接口。

## 已完成

1. 保留 Agent60 新版 RetrievalAgent / ReviewAgent，并适配 KB2.1 Evidence 字段。
2. ROS2 KB2.1：300 Evidence、50 Concept、30 Assessment、20 Procedure、10 Validator Spec、100 Retrieval Seed、300 Human Review Queue。
3. Evidence 保留稳定 `evidence_id`、source/version/concept/risk/importance/applicability/verification/provenance。
4. DB seed 不再把数据无条件标成 verified；按数据原始 verification_status 入库。
5. `version_filter` 已贯通：HarmonyOS request -> Workflow API -> Orchestrator -> WorkflowState -> Retriever/Review。
6. Retrieval：BM25/Vector/RRF/Graph/MMR 兼容新数据；保留真实 verification_status；修复图扩展 prerequisite 方向；复用 query embedding。
7. Generation：会读取 `practice_tasks.jsonl` 和 `assessment_bank.jsonl`，输出 Procedure 的 evidence/validator/risk/version/rollback 信息；测试题保留 evidence_ids。
8. Review：对低风险 trusted_source 与中高风险证据分级；检查讲义、Procedure、Test 的 evidence IDs；中高风险 Procedure 检查 rollback；输出 severity + 结构化 revision。
9. Knowledge API 新增 concept graph、practice tasks、validator specs、dataset metadata。
10. HarmonyOS `ApiService.ets` 已补 version_filter、Procedure/Assessment 新字段和新 Knowledge API 方法。
11. 数据结构/引用完整性验证通过；Python compileall 通过；Generation->Review 数据接口 smoke test 在真实 KB Evidence 输入下通过（Review=approve）。

## 当前明确未完成

### P0：必须完成

1. 300 Evidence 尚未人工逐条核验：`human_verified=0`；需完成 claim -> 精确 source locator 审核。
2. 报告目标 500-800 原子 Evidence；当前 300，至少再补 200 条高价值证据。
3. Validator Registry 仍是 `spec_only`；未实现真实 deterministic validator / sandbox。
4. LearnerModel 还没有真正的 Beta/BKT 后验与置信区间。
5. Diagnosis 还没有候选题信息增益选择与动态停止。
6. Orchestrator 仍是固定 Diagnosis->Planner->Retriever->Generation->Review 流程，没有 PreRisk 1/2/4 风险路径。
7. 尚无正式 ClaimGraph / ProofGraph 运行时对象；高风险声明未形成 claim_id->evidence_id->validator_result 图。
8. 尚无条件 Critic / Judge 角色执行链；当前 ReviewAgent 主要是规则层审核。
9. 向量索引仍需要进一步做持久化/增量化；尚未实测 Recall@10、版本冲突召回、重复率、P95。
10. 当前知识集中于 Humble，缺 Foxy/Jazzy 等跨版本冲突金标集。

### P1：比赛验收前完成

1. Assessment 从 30 扩到至少 100-150 个高质量诊断题，干扰项应来自真实误概念。
2. 冻结 100+ Retrieval Gold Set，人工标注相关 Evidence IDs 与版本冲突。
3. 盲测 300+ 任务；双标注并计算 Cohen kappa。
4. 完整 Evaluation pipeline：幻觉点估计+95%CI/UCB、适配分画像/分难度、WeightedCoverage、严重度加权错误。
5. 消融：普通 RAG、固定多 Agent、风险路由/ProofGraph；Retrieval Top-k/Hybrid/Graph/MMR/ConceptGain；Critic on/off。
6. Observability：trace/token/latency/evidence/disagreement/refusal/error 指标记录和面板。
7. 前端补齐：后验区间、Evidence/version/risk 展开、激活 Agent/验证状态、管理指标、三画像一键切换。
8. 增加独立故障排查树资源；当前系统主输出是讲义/实操/测试，学习路径已有但排错树仍需正式资源化。
9. Docker Compose 在干净环境做一次完整部署回归并记录版本 hash。

## 当前验证结果

数据校验：
- Evidence 300 / Unique IDs 300 / Unique Claims 300
- Concepts 50
- Skills 10
- Assessments 30
- Practice Tasks 20
- Validator Specs 10
- Retrieval Seeds 100
- Review Queue 300
- Human Verified 0
- Skill DAG PASS
- Concept DAG PASS

代码校验：
- Python `compileall`: PASS
- Generation -> Review KB interface smoke: PASS（使用目标 Skill 的真实 KB evidence；Review approve）
- DB-dependent pytest: 未在当前执行环境完成。原因是运行环境缺 `aiosqlite`，而项目 requirements 已声明该依赖；pytest 在 collection 阶段停止。不能据此宣称完整测试通过。

## 下一步建议

当前优先进入 M2，而不是继续堆 Retriever 功能：

1. 实现 Beta/BKT LearnerModel + mastery confidence。
2. 将 30 题扩展并实现近似 information gain 动态选题。
3. 同时开始 300 Evidence 人工审核；先审核所有 medium/high-risk + 演示链路 Evidence。
4. M2 稳定后冻结 Retrieval gold set，再做 M3 性能检索评测与索引持久化。
5. 再进入 M4 Risk Router + ClaimGraph + Validator。
6. M5 做条件 Critic/Judge 与学习路径有限步策略。
7. 最后做性能收敛、盲测、消融、演示。
