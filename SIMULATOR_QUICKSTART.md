# HarmonyOS 模拟器快速启动

## 一、启动后端

在项目根目录双击：

```text
start.bat
```

看到以下内容表示服务已启动：

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

## 二、配置 HarmonyOS 模拟器

应用中打开：

```text
我的 → API 设置
```

填写：

```text
http://10.0.2.2:8000
```

点击“测试 API 并保存”。

`10.0.2.2:8000` 与宿主机的 `127.0.0.1:8000` 指向同一套 FastAPI 服务，只是模拟器访问宿主机时使用不同网络地址。

连接失败时检查：

- `start.bat` 窗口是否仍在运行；
- 浏览器 `/health` 是否成功；
- 防火墙是否允许 TCP 8000；
- 8000 端口是否被其他程序占用。

项目没有内置模拟后端；后端断开时客户端会直接报告连接错误。
