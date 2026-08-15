# ProofGraph 核心闭环改进说明（2026-08-15）

本版本基于 `H-SmartLearn-ProofGraph-merged-20260815` 继续收敛，目标不是增加更多数学模块，而是把报告中 P0 的“风险路由 → 声明图 → 确定性验证 → 条件 Critic/Judge → 发布”真正接入运行链。

## 1. 已完成改动

### 1.1 风险自适应路由

新增：

- `backend/app/services/risk_router_service.py`
- `backend/app/agents/risk_router_agent.py`

运行时按以下公式计算：

`PreRisk = 0.35*DomainRisk + 0.25*Uncertainty + 0.25*RetrievalWeakness + 0.15*Novelty`

并划分：

- `fast`：模型调用预算 ≤ 1
- `standard`：模型调用预算 ≤ 2，启用定向 Critic
- `strict`：模型调用预算 ≤ 4，启用 Critic + Judge

危险命令、磁盘/固件/网络级操作可直接强制进入 strict。

### 1.2 ClaimGraph / ProofGraph 闭环

新增：

- `backend/app/services/claim_graph_service.py`
- `backend/app/agents/proofgraph_agent.py`

现在生成结果会拆成可追踪声明：

- 讲义段落声明
- 实操步骤声明
- 测试解释声明

每条声明记录：

- `claim_id`
- `path`
- `risk_level`
- `evidence_ids`
- `validator_ids`
- `validation_results`
- `final_disposition`

最终裁决为：

- `PASS`
- `DOWNGRADE`
- `NEED_CONFIRMATION`
- `REJECT`

发布资源中同时保存完整 `claim_graph` 和摘要指标。

### 1.3 Validator 从“规范 ID”变成可执行静态门

新增：

- `backend/app/services/validation_service.py`

已实现的低成本验证：

- Shell 危险命令检测
- `bash -n` 静态语法检查（不执行命令）
- Python AST 语法检查
- JSON / YAML / XML 解析检查
- ROS 环境/版本静态检查
- Launch / URDF 命令形态检查
- 设备、sudo、网络配置、固件操作人工确认门

需要真实 ROS 图、TF、QoS、Nav2、SLAM 运行状态的验证器不会假装成功，而返回 `unknown`，由高风险声明发布门决定是否需要人工确认。

### 1.4 条件 Critic + Judge

新增：

- `backend/app/agents/critic_agent.py`
- `backend/app/agents/judge_agent.py`

Critic 只复查未支持、未验证或高风险争议声明，不重新审全文。

Judge 仅在 strict 路径启用，融合：

- Review 结果
- Critic 结果
- ProofGraph 高风险未决状态

### 1.5 MMR 改为“相关性 + 去重 + 概念增益 + 来源增益”

改动：

- `backend/app/services/mmr_service.py`
- `backend/app/agents/retrieval_agent.py`

现在在线重排包含：

- relevance
- redundancy penalty
- ConceptGain
- SourceGain
- soft source quota

检索结果同时输出 `selection_signals`，便于审计为什么某条证据被选中。

### 1.6 固定测评与自适应学情统一

改动：

- `backend/app/core/database.py`
- `backend/app/api/assessments.py`
- `backend/app/api/resources.py`
- `backend/app/agents/generation_agent.py`

Assessment seed 现在保留 `concept_ids`；固定测评答案直接更新 `LearnerModelService` 的 Beta 概念后验。

规则：

- 有 `concept_ids`：LearnerModel 为知识掌握事实源
- 老数据没有 `concept_ids`：才回退到 BKT 兼容路径

资源测试在反馈确认后也会把题目结果写入 LearnerModel，避免固定测评、自适应诊断、资源测试长期各算各的。

### 1.7 HarmonyOS 演示界面补充

改动：

- `entry/src/main/ets/pages/WorkflowProcessPage.ets`
- `entry/src/main/ets/pages/ResourceViewPage.ets`
- `entry/src/main/ets/service/ApiService.ets`

工作流页新增显示：

- 风险路由服务
- ProofGraph 验证
- 条件 Critic
- 条件 Judge

资源“溯源”页新增显示：

- Fast / Standard / Strict 路径
- PreRisk
- Claim 数量
- 高风险溯源率
- 未决高风险声明数

未启用的 Critic / Judge 在成功完成后显示 `SKIP`，避免误解为未运行失败。

## 2. 当前验证结果

已通过：

```text
python tools/validate_project.py
status = passed
ETS files = 26
registered pages = 10
button contracts = 69
```

Python 静态编译：

```text
python -m compileall -q app tests
PASS
```

不依赖数据库驱动的回归与新增 ProofGraph 测试：

```text
43 passed
```

新增测试：

- Fast/Strict 风险路由
- 危险命令静态阻断
- Claim-Evidence-Validator 绑定
- 高风险命令 REJECT
- MMR ConceptGain / SourceGain

完整 pytest 在当前审计容器中仍受 `aiosqlite` 未安装影响；项目 `requirements.txt` 已包含 `aiosqlite==0.19.0`，因此这是审计环境依赖缺失，不是本次代码编译错误。

## 3. 仍未完成 / 下一阶段

### P0 剩余

1. 真正隔离执行沙箱：当前只做静态检查，未执行任意用户命令。
2. ROS 在线 Validator：需要目标 ROS2 机器实际查询 Node / Topic / QoS / TF / Lifecycle。
3. Agent 历史可靠性：Brier Score、错误发现质量和可靠性权重尚未形成持久统计。
4. 标准路径 Critic 当前是确定性定向复查；若启用 LLM，应只发送争议 Claim，不允许全文重复调用。

### P1

1. 300–500 个任务级盲测样例。
2. 幻觉率 95% 置信区间。
3. Adaptation / Coverage 分画像报告。
4. Risk Router vs 全 Agent 消融。
5. MMR + ConceptGain vs Top-k 消融。
6. P95、token、模型调用数自动统计面板。

### 暂不做

继续保持离线/关闭：

- TDA
- OT / Sinkhorn
- 随机矩阵
- Fourier / 小波
- 挂谷方向覆盖
- 精确 POMDP
- 深度多智能体强化学习
- 自然梯度

这些模块不应阻塞核心提交版本。
