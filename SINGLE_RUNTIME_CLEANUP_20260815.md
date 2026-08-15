# 单运行链路清理记录（2026-08-15）

## 目标

删除客户端独立内置演示运行时。HarmonyOS 模拟器、真机和本机调试均访问同一 FastAPI 后端，默认业务端口统一为 8000。

## 已删除

- `entry/src/main/ets/service/DemoBackend.ets`
- `entry/src/main/ets/pages/DemoCenterPage.ets`
- `main_pages.json` 中的 `DemoCenterPage` 页面注册
- `ApiService.createDemo()`、`demoMode`、Demo 请求分支与 Demo runtime state
- `DataStore` 中 Demo profile / Demo fallback 配置
- 首页、画像页、诊断页、资源页、报告页、技能图谱页、API 设置页中的演示入口与演示路由参数

## 统一后的行为

- 客户端统一使用 `ApiService` 请求配置的 FastAPI 后端。
- 默认 HarmonyOS 模拟器地址：`http://10.0.2.2:8000`。
- 宿主机健康检查：`http://127.0.0.1:8000/health`。
- 两个地址访问的是同一个监听在 `0.0.0.0:8000` 的后端，不是两个运行模式。
- 后端不可达时返回真实连接错误；不会自动切换到本地模拟数据。
- 工作流缓存、离线反馈队列、笔记和收藏仍保留，它们是离线韧性能力，不是模拟后端。
- `LLM_PROVIDER=disabled` 时，Generation Agent 在同一后端工作流中使用证据约束确定性生成器，不产生第二套 API 或绕过 ProofGraph。

## 校验

`python tools/validate_project.py` 已增加单运行链路检查，禁止 ArkTS runtime 重新出现：

- `DemoBackend`
- `DemoCenterPage`
- `createDemo(`
- `demoMode`
- `SPRING DEMO`
- `embedded-demo`

当前结构校验结果：

```text
status: passed
ets_files: 24
registered_pages: 9
button_contracts: 60
interaction_contracts: diagnostic / resource_test / practice / profile
```

不依赖数据库异步驱动的核心测试：`43 passed`。

完整数据库相关测试在当前容器中仍受 `aiosqlite` 未安装影响；项目 `backend/requirements.txt` 已声明该依赖。
