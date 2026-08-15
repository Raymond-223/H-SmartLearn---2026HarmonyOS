# 知衡 ProofGraph 改进后代码完成度审计

## 结论

相较上一合并版，本次最重要变化是：项目已经从“有证据字段、有多 Agent 名称”推进到“风险路由 + ClaimGraph + 静态 Validator + 条件 Critic/Judge”的可运行闭环。

当前建议工程完成度：

| 模块 | 状态 | 说明 |
|---|---|---|
| 概率学情 | 核心完成 | Beta 概念后验、Skill rollup、固定测评/自适应诊断统一 |
| 自适应诊断 | 核心完成 | 信息价值、覆盖、时间/疲劳、停止条件 |
| 混合检索 | 基本完成 | BM25、向量、图扩展、版本、MMR、ConceptGain、SourceGain |
| 风险路由 | 核心完成 | PreRisk + Fast/Standard/Strict + 1/2/4预算 |
| ClaimGraph | 核心完成 | 声明、证据边、验证器边、发布 disposition |
| Validator | 部分完成 | 静态安全/语法/版本已实现；ROS在线/隔离执行未完成 |
| Critic | 基本完成 | 条件定向复查，不做全文重复审核 |
| Judge | 基本完成 | Strict路径确定性融合 |
| 学习路径 | 部分完成 | 先修图路径已存在；Pareto三路径/有限步前瞻可继续加强 |
| 性能统计 | 部分完成 | 有调用预算结构；P95/token/缓存消融尚未形成完整仪表盘 |
| 统计验收 | 未完成 | 盲测、置信区间、双标注、核心消融仍是主要缺口 |
| 高阶离线数学 | 暂不做 | 与报告性能优先策略一致 |

## 最优下一步

不建议再扩展数学模块。接下来优先：

1. 在真实 ROS2 环境接入只读 Validator。
2. 建立 benchmark runner，自动记录 hallucination / adaptation / coverage / latency / calls / token。
3. 构造错误版本、危险命令、缺证据、Agent 超时四类故障注入。
4. 做 Risk Router、ProofGraph、MMR ConceptGain 的核心消融。
5. 固化 10 分钟答辩路径。
