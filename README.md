# H-SmartLearn · ProofGraph

面向 ROS2 智能机器人技能学习的个性化知识生成与多智能体协同决策系统。HarmonyOS 客户端负责学习者交互，FastAPI 后端负责学情建模、诊断、检索、风险路由、多 Agent 协同、ProofGraph 验证与反馈更新；独立的只读 Observability Layer 负责全链路可视化与人类可读日志。

## 当前运行方式

项目只有一套正常运行链路，不存在独立的内置演示模式、模拟后端或 Demo 端口。

所有客户端业务请求统一访问同一个 FastAPI 后端，默认监听：

```text
0.0.0.0:8000
```

不同地址只是访问同一个 8000 端口的网络入口：

- 本机浏览器：`http://127.0.0.1:8000`
- HarmonyOS 模拟器访问宿主机：`http://10.0.2.2:8000`
- HarmonyOS 真机：`http://<开发机局域网IP>:8000`

客户端后端地址可在“API 设置”页面修改并测试。连接失败时会直接提示后端不可用，不会切换到本地假数据。


## 全链路可观测层

项目新增了与核心业务代码分离的 `backend/observability/`。它不是第二套运行模式，也不是模拟后端，而是正式系统上的**只读旁路**。

核心主链仍然只有一条：

```text
HarmonyOS / API 请求
        ↓
backend/app 核心闭环
        ↓
正式数据库中的 WorkflowState / AgentRun / Diagnosis / ProofGraph
        ├────────→ 正常业务输出
        └────────→ Observability 只读展示
```

Observability 不参与风险路由、Agent 调度、ProofGraph 验证或发布裁决，只读取已经持久化的数据，因此关闭可视化页面不会改变任何业务结果。

后端启动后直接打开：

```text
http://127.0.0.1:8000/observability
```

仍然使用同一个正式后端 `8000` 端口，不增加 Demo 端口。页面可实时查看：

- LearnerModel 的掌握度、不确定性、薄弱概念；
- Adaptive Diagnosis 每一道题的选择评分与答题结果；
- Planner 的目标技能与学习路径；
- Retriever 的 BM25 / Vector / Graph / Version / MMR 输出及最终 Evidence；
- Risk Router 的 DomainRisk、Uncertainty、RetrievalWeakness、Novelty、PreRisk 和路由原因；
- 每一次 AgentRun 的结构化输入、输出、置信度与耗时；
- ProofGraph 的 Claim → Evidence → Validator → Disposition；
- 面向研发和答辩的分层人类可读日志。

可观测 API：

```text
GET /api/observability/workflows/recent
GET /api/observability/workflows/{workflow_id}
GET /api/observability/workflows/{workflow_id}/human-log
GET /api/observability/workflows/{workflow_id}/export
```

> 安全边界：只展示结构化输入、输出、评分、证据和裁决依据，不展示模型隐式推理过程。

## 核心闭环

```text
学习者画像 / 学习目标
        ↓
LearnerModel：Beta/BKT 学情与不确定性
        ↓
Adaptive Diagnosis：自适应诊断与信息价值选题
        ↓
Planner：先修约束与个性化学习路径
        ↓
Retriever：BM25 + Vector + Graph + Version Filter
        ↓
Evidence Selection：RRF + MMR + ConceptGain + SourceGain
        ↓
Risk Router：Fast / Standard / Strict
        ↓
Generation Agent：讲义 / 实操指南 / 分阶测试
        ↓
ProofGraph：Claim → Evidence → Validator → ValidationResult
        ↓
Review / Critic / Judge（按风险条件启用）
        ↓
资源发布
        ↓
测试 / 实操 / 主观反馈
        ↓
LearnerModel 更新并进入下一轮学习
```

## 已实现模块

### 学情与诊断

- 学习者画像创建、读取与修改。
- 概念级 Beta 后验与技能级掌握度聚合。
- BKT/Beta 学情更新。
- 自适应诊断：候选题筛选、先修约束、信息价值、覆盖、时间与疲劳因素。
- 诊断结果回写统一 LearnerModel。

### 检索与知识组织

- ROS2 / C 语言领域知识包。
- Concept、EvidenceUnit、AssessmentItem、PracticeTask、ValidatorSpec 等结构化数据。
- BM25、向量检索、图扩展、版本过滤与 RRF 融合。
- MMR 去重，并加入 ConceptGain、SourceGain 与来源控制。
- 技能先修图与学习路径可视化。

### 多 Agent 与 ProofGraph

- 风险路由：Fast / Standard / Strict。
- Generation、Review、Critic、Judge 等逻辑角色按风险条件启用。
- ClaimGraph：将关键声明与 Evidence、Validator、ValidationResult 关联。
- 发布裁决：PASS / DOWNGRADE / NEED_CONFIRMATION / REJECT。
- 危险 Shell、Python、JSON/YAML/XML、ROS 版本与配置类静态校验。
- 高风险内容可降级、要求确认或拒绝发布。

### 学习资源与反馈

- 个性化讲义。
- 可执行实操指南。
- 分阶测试。
- 测试与实操结果回写掌握度。
- 本地笔记、收藏与离线反馈队列。
- 学情报告、薄弱知识点、学习路径与学习事件记录。

## 项目结构

```text
H-SmartLearn-ProofGraph
├── entry/                       # HarmonyOS ArkTS / ArkUI 客户端
│   └── src/main/ets/
│       ├── pages/               # 画像、诊断、工作流、资源、报告等页面
│       ├── service/             # API、技能图谱等客户端服务
│       ├── business/            # 本地状态与离线队列
│       └── integration/         # 通知、跨端续学等集成
├── backend/
│   ├── app/
│   │   ├── agents/              # Generation / Review / Critic / Judge 等
│   │   ├── api/                 # FastAPI 路由
│   │   ├── services/            # LearnerModel、检索、MMR、RiskRouter、ProofGraph
│   │   ├── validators/          # 确定性校验逻辑
│   │   └── workflow/            # Orchestrator 与状态机
│   ├── domain_packages/         # 领域知识、题库、技能图与实操任务
│   ├── observability/           # 只读旁路：可视化、Trace、人类日志
│   ├── tests/                   # Python 回归测试
│   └── docker-compose.yml
├── tools/validate_project.py    # ArkTS 路由、交互契约与 Python 语法检查
└── README.md
```

## 启动后端

### Windows

在项目根目录双击：

```text
start.bat
```

或进入 `backend` 后运行：

```text
start_backend_windows.bat
```

### macOS / Linux

```bash
cd backend
./start_backend_macos_linux.sh
```

启动后检查：

```text
http://127.0.0.1:8000/health
```

正常响应示例：

```json
{
  "status": "ok",
  "version": "1.7.3",
  "mode": "hybrid-agent-platform"
}
```

## Docker 启动

```bash
cd backend
docker compose up --build
```

Docker Compose 会启动 PostgreSQL 与 FastAPI；业务 API 和只读 Observability 控制台都复用正式后端 `8000` 端口。

## LLM 配置

后端模型能力由环境变量配置：

```env
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=...
```

如果 `LLM_PROVIDER=disabled`，系统仍走同一套后端 API、同一工作流和同一 ProofGraph 验证链，只是 Generation Agent 使用证据约束的确定性生成器。它不是另一套演示模式，也不会绕过风险路由、检索、审核或反馈闭环。

## 项目验证

运行结构检查：

```bash
python tools/validate_project.py
```

该检查会验证：

- ArkTS 页面和相对导入完整性；
- 页面路由注册；
- 诊断、资源测试、实操和画像交互状态契约；
- 单一运行链路，不允许重新出现 `DemoBackend`、`DemoCenterPage`、`demoMode` 等独立演示运行时代码；
- Python 后端语法。

运行 Python 测试：

```bash
cd backend
python -m pytest -q
```

## 当前工程边界

已经完成 P0 主链：学情 → 诊断 → 路径 → 检索 → 风险路由 → 生成 → ProofGraph 验证 → 条件审核 → 发布 → 反馈更新。

仍需继续加强：

- ROS2 在线只读 Validator（Node / Topic / TF / QoS / Lifecycle）；
- 高风险 Evidence 人工金标与更大规模证据库；
- 300–500 个任务级正式盲测与 Claim 级双标注；
- 在现有 Observability 基础上继续补充 P50/P95、Token、缓存命中率等跨请求聚合性能指标；
- Risk Router、ProofGraph、MMR、信息增益诊断等核心模块的消融实验。

## 说明

HarmonyOS 模拟器只是客户端运行环境，不等于“演示模式”。模拟器、真机和浏览器检查访问的都是同一个后端服务；最终业务逻辑不存在本地假后端自动接管。
