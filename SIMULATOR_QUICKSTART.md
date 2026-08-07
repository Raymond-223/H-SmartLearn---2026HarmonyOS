# HarmonyOS 模拟器快速启动

## 一、启动真实后端

在项目根目录双击：

```text
start.bat
```

首次启动会创建 Python 虚拟环境并安装依赖。看到以下内容表示服务已启动：

```text
Uvicorn running on http://0.0.0.0:8000
```

浏览器验证：

```text
http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok","version":"1.7.3","mode":"hybrid-agent-platform"}
```

## 二、配置模拟器

应用中打开：

```text
我的 → 真实 API 设置
```

填写：

```text
http://10.0.2.2:8000
```

点击“测试真实 API 并保存”。

正式应用不会自动使用模拟数据。连接失败时请检查：

- `start.bat` 窗口是否仍在运行；
- 浏览器健康检查是否成功；
- Windows 防火墙是否允许 Python 访问专用网络；
- 8000 端口是否被其他程序占用。

## 三、运行独立演示

首页或画像页点击：

```text
春日演示中心
```

该流程与真实 API 完全隔离，题目、Agent、资源、报告和图谱均来自内置模拟数据。
