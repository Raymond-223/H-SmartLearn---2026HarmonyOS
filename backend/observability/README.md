# Observability Layer（只读旁路）

本目录是与 `backend/app/` 核心业务链分离的可观测层。

设计边界：

- 核心 Workflow / Agent / LearnerModel / Retriever / ProofGraph **不依赖** `observability`。
- 可观测层只读取已经持久化的 `WorkflowSession.state_data`、`AgentRun`、自适应诊断记录和已发布资源。
- 不向核心数据库写入日志字段，不修改 Agent 输入，不改变状态机，不参与任何发布裁决。
- HTTP 读取使用 rollback-only session；即使未来误加入 ORM 修改，也不会在该请求中提交。
- 展示内容仅包含结构化输入、输出、评分、证据、风险与裁决，不展示模型隐式推理过程。

唯一接线点在 `backend/app/main.py`：

```python
from observability.router import router as observability_router
app.include_router(observability_router)
```

这使控制台复用正式后端 `8000` 端口，而不是创建第二套“演示模式”或假后端。

## 页面

正式后端启动后打开：

```text
http://127.0.0.1:8000/observability
```

## API

```text
GET /api/observability/workflows/recent
GET /api/observability/workflows/{workflow_id}
GET /api/observability/workflows/{workflow_id}/human-log
GET /api/observability/workflows/{workflow_id}/export
```

## 展示内容

- LearnerModel：掌握度、不确定性、薄弱概念。
- Adaptive Diagnosis：逐题选择评分、答题结果、疲劳状态。
- Planner：目标技能和学习路径。
- Retriever：BM25/Vector/图扩展/MMR 配置和最终 Evidence。
- Risk Router：四项风险构成、PreRisk、Fast/Standard/Strict 和原因。
- Agent Runtime：每次 AgentRun 的结构化输入/输出、状态、置信度和耗时。
- ProofGraph：Claim、Evidence、Validator、Disposition 与高风险可溯源率。
- 人类日志：面向研发、答辩和故障定位的分层文本日志。
