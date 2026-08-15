# 2026-08-15 可观测层改造记录

## 目标

在不侵入主链算法代码的前提下，让评委/研发人员看到每一层的真实结构化输出，并提供人类可读日志。

## 架构决策

采用**只读旁路**，不在 LearnerModel、Diagnosis、Planner、Retriever、RiskRouter、Agent、ProofGraph、Validator 内插入日志调用。

数据来源直接使用主链已经持久化的数据：

- `workflow_sessions.state_data`
- `agent_runs.input_json / output_json`
- `diagnosis_sessions / diagnosis_responses`
- `generated_resources`

因此 Observability 即使关闭，主链行为和最终输出完全不变。

## 新增文件

```text
backend/observability/
├── __init__.py
├── repository.py      # 只读数据库访问
├── presenter.py       # 各层结构化视图
├── human_log.py       # 人类可读日志
├── router.py          # 只读 API + 控制台入口
├── dashboard.html     # 无第三方前端依赖的实时控制台
├── README.md
└── tests/
    ├── test_presenter.py
    └── test_boundary.py
```

## 核心代码改动

核心业务文件中只修改：

```text
backend/app/main.py
```

用途仅为挂载 `observability_router`。没有修改：

- `app/workflow/orchestrator.py`
- `app/workflow/state.py`
- `app/agents/*`
- `app/services/*`
- `app/validators/*`
- HarmonyOS 正常学习页面

## 正式入口

```text
http://127.0.0.1:8000/observability
```

与正式业务 API 共用 8000 端口，不存在第二套 Demo/Mock 服务。

## 可视化内容

1. LearnerModel：掌握度、不确定性、薄弱概念。
2. Adaptive Diagnosis：逐题选择评分、答题结果、疲劳状态。
3. Planner：目标技能和学习路径。
4. Retriever：检索方法、版本、图扩展、MMR、最终 Evidence。
5. Risk Router：四项风险分量、PreRisk、路由和显式原因。
6. Agent Runtime：结构化 input/output、置信度、耗时、重试次数。
7. ProofGraph：Claim、Evidence、Validator、Disposition 图和明细。
8. Human Log：可直接用于研发排错和答辩说明的分层文本日志。

## 边界保护

`test_boundary.py` 会检查除 `app/main.py` 外的核心 `app/*.py` 不得反向 import/引用 `observability`，防止以后为了展示把日志逻辑重新塞回主链。
