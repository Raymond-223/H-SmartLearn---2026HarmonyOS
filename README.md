# H-SmartLearn HarmonyOS Competition v1.7.3


## v1.7.3 补丁

根据 DevEco Studio 的真实编译日志，移除了 `Hyperlink` 不支持的 `.fontColor()` 属性。该链接仍可点击，URL 文本仍可复制。详见 `BUILD_FIX_REPORT_v1.7.3.md`。
面向 ROS2 机器人与 C 语言学习的可审计、自适应学习平台。客户端使用 HarmonyOS ArkTS/ArkUI，后端使用 FastAPI + SQLAlchemy。正式模式连接后端，免配置演示模式使用独立内置引擎，两种模式显式隔离。

## 本版本重点

v1.7.3 基于 DevEco Studio 的真实 `assembleHap` 日志修复 ArkTS 编译失败：

- 修复确认弹窗按钮缺少 `action` 的类型错误，并迁移到 `UIContext` 关联的 `PromptAction.showDialog`。
- 删除 4 处 `Row.minHeight` 非法属性，使用 API 12 可编译的尺寸属性。
- 删除 `Hyperlink.fontSize` 非法属性。
- 为 ArkData、Preferences、通知和日志指出的页面路由补充显式异常处理。
- 删除已弃用的全局 `animateTo` 调用。
- 保留 v1.7.1 对诊断题、资源测试、实操和画像选择状态的直接 `@State` 绑定修复。
- 恢复 Hvigor 默认类型检查，不通过关闭检查隐藏问题。

## 已实现功能

- 学习者画像：创建、读取、编辑；画像影响讲义风格、难度和学习时长分配。
- 诊断测评：双领域各 10 题，完整性校验、服务端判分、逐题答案与解析回看。
- 工作流：诊断、规划、检索、生成、审核五阶段主流程；失败可重试。
- 目标技能学习：知识图谱和学情报告节点可直接启动对应技能资源。
- 资源学习：讲义、逐步实操确认、可选择测试、服务端评分、证据溯源、本地笔记与收藏。
- 反馈闭环：测试与实操成绩由服务端计算，反馈幂等写入掌握度，并生成下一技能、补练或降难任务。
- 学情报告：掌握度、薄弱项、优势、难度曲线、路径与学习事件时间线。
- 离线韧性：反馈队列、工作流快照、本地笔记与收藏。
- 回归指标：运行 20 个技能 × 3 类画像，共 60 组检索—生成—审核用例。
- HarmonyOS：跨端续学最小状态、通知、ArkData、按压/焦点/禁用反馈。

## 后端启动

Windows：双击根目录 `start.bat`。

macOS / Linux：

```bash
cd backend
./start_backend_macos_linux.sh
```

健康检查：`http://127.0.0.1:8000/health`

HarmonyOS 模拟器默认后端地址：`http://10.0.2.2:8000`

## 验证边界

本交付环境完成了 Python 回归、Python 编译、ArkTS 静态结构/导入/路由检查，以及选择状态源码契约检查。当前环境没有 DevEco Studio、HarmonyOS SDK、模拟器和真机，因此不能把静态检查表述成真实触控验证。请在开发机按 `INTERACTION_ACCEPTANCE_CHECKLIST_v1.7.3.md` 执行最终验收。
