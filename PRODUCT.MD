# Tinyclaw 产品文档

## 目标
Tinyclaw 提供一个最小可用的“Agent + Channel + Web Terminal”框架：
- `Agent` 负责和真实执行体交互（当前为终端进程）。
- `Channel` 负责客户端和 Agent 之间的数据转发。
- `Web Terminal` 通过浏览器使用 WebSocket 连接 Channel。

## 目录结构
- `gateways/`：网关服务端实现（如 FastAPI）。
- `clients/web_terminal/`：网页终端客户端资源。

## 当前能力
1. 支持 `terminal_agent`：
- 可启动一个终端子进程（例如 `bash`、`codex`、`powershell`）。
- 可向终端写入输入并读取输出。

2. 支持 `web_terminal_channel`：
- 接收浏览器 WebSocket 输入。
- 将输入转发给 Agent，并把 Agent 输出回传到浏览器。
- 支持断线重连后回放历史输出（默认保留最近 200000 字符）。
- 历史回放保留终端控制序列，仅过滤已知噪声 `[?1;2c`。
- 页面刷新不会停止 Agent 进程，Agent 持续在后台运行。

3. 支持通过 `config.toml` 创建多个 Agent 和 Channel：
- 每个 Channel 可配置独立端口。
- 启动后每个端口提供一个网页终端入口。

4. 支持删除功能：
- `DELETE /api/channels/{channel_id}` 删除 channel。
- `DELETE /api/agents/{agent_id}` 删除 agent，并自动删除关联 channel。

## 配置示例
见 `config.toml`，核心字段如下：
- `[[agents]]`
  - `id`
  - `type`（当前 `terminal`）
  - `shell`（例如 `codex`/`bash`）
  - `cwd`（可选）
- `[[channels]]`
  - `id`
  - `type`（当前 `web_terminal`）
  - `agent_id`
  - `host`
  - `port`
  - `static_dir`

## API
- `GET /api/agents` 列出 agent 状态。
- `POST /api/agents` 创建 agent。
- `DELETE /api/agents/{agent_id}` 删除 agent。
- `GET /api/channels` 列出 channel。
- `POST /api/channels` 创建 channel。
- `DELETE /api/channels/{channel_id}` 删除 channel。
- `WS /ws/terminal` 连接当前端口默认 channel。
- `WS /ws/terminal/{channel_id}` 连接指定 channel。

## 启动
```bash
python main.py --config config.toml
```

示例端口：
- `http://127.0.0.1:9001` -> `codex-web`
- `http://127.0.0.1:9002` -> `bash-web`
