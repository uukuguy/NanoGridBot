# NanoGridBot 完整运行指南

本文档提供一步一步的启动指南，帮助你快速运行 NanoGridBot 并完成各种智能体任务。

---

## 目录

1. [环境准备](#1-环境准备)
2. [Docker 镜像构建](#2-docker-镜像构建)
3. [基础配置](#3-基础配置)
4. [CLI 终端模式](#4-cli-终端模式)
5. [Telegram 模式](#5-telegram-模式)
6. [Slack 模式](#6-slack-模式)
7. [智能体任务示例](#7-智能体任务示例)
8. [常见问题](#8-常见问题)

---

## 1. 环境准备

### 1.1 检查环境

```bash
# 检查 Python 版本
python3 --version  # 需要 3.12+

# 检查 Docker
docker --version

# 检查虚拟环境（项目已有 .venv）
ls -la .venv/bin/python
```

### 1.2 激活虚拟环境

```bash
# 激活虚拟环境
source .venv/bin/activate

# 验证
python --version
```

### 1.3 检查 Docker 镜像（稍后构建）

```bash
docker images | grep nanogridbot
# 目前应该为空，我们需要构建
```

---

## 2. Docker 镜像构建

### 2.1 构建 Agent 容器镜像

```bash
cd container

# 使用 build.sh 脚本
./build.sh

# 或者手动构建
docker build -t nanogridbot-agent:latest .
```

**注意**：这个镜像会安装：
- Node.js 22
- Claude Code (`agent-code`)
- Chromium 浏览器（用于浏览器自动化）
- 完整的运行环境

### 2.2 验证构建

```bash
docker images | grep nanogridbot
# 应该看到: nanogridbot-agent   latest   xxx   xxx
```

---

## 3. 基础配置

### 3.1 创建配置文件

在项目根目录创建 `.env` 文件：

```bash
# 基础配置
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# CLI 默认配置
CLI_DEFAULT_GROUP=cli

# 容器配置
CONTAINER_IMAGE=nanogridbot-agent:latest
CONTAINER_TIMEOUT=1800

# 日志级别
LOG_LEVEL=INFO

# Web 面板（可选）
WEB_ENABLED=true
WEB_HOST=0.0.0.0
WEB_PORT=8080
```

### 3.2 获取 Anthropic API Key

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 创建 API Key
3. 复制到 `.env` 文件

### 3.3 创建必要目录

```bash
mkdir -p store/logs
mkdir -p groups
mkdir -p data
```

---

## 4. CLI 终端模式

### 4.1 方式一：交互式 Shell（推荐首次使用）

```bash
python -m nanogridbot shell
```

**命令说明**：
- 直接启动交互式对话
- 会自动创建 Docker 容器
- 输入你的问题，按回车发送
- 输入 `/quit` 退出
- 输入 `/help` 查看更多命令

**首次运行**会：
1. 拉取 Docker 镜像（如未存在）
2. 创建容器
3. 启动 Claude Code 会话

### 4.2 方式二：单次执行

```bash
# 通过命令行参数
python -m nanogridbot run -p "帮我写一个 Python 快速排序函数"

# 通过管道输入
echo "帮我写一个 Hello World 程序" | python -m nanogridbot run
```

### 4.3 方式三：传递自定义环境变量

```bash
# 切换模型
python -m nanogridbot run -p "你的问题" -e ANTHROPIC_MODEL=claude-opus-4-20250514

# 传递其他配置
python -m nanogridbot run -p "你的问题" -e CUSTOM_VAR=value
```

### 4.4 方式四：恢复会话

```bash
# 查看之前会话 ID（见日志）
# 恢复会话继续对话
python -m nanogridbot shell --resume <session-id>
```

---

## 5. Telegram 模式

### 5.1 创建 Telegram Bot

1. 打开 Telegram
2. 搜索 `@BotFather`
3. 发送 `/newbot` 创建新机器人
4. 获取 Bot Token（如：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 5.2 配置 .env

```bash
# 启用 Telegram
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=你的bot_token
```

### 5.3 启动服务

```bash
python -m nanogridbot serve
```

### 5.4 与机器人对话

1. 在 Telegram 中搜索你的机器人
2. 发送 `/start` 开始
3. 直接发送消息进行对话

---

## 6. Slack 模式

### 6.1 创建 Slack App

1. 访问 [Slack App Management](https://api.slack.com/apps)
2. 创建新 App（From scratch）
3. 配置以下权限：
   - `chat:write`
   - `channels:read`
   - `groups:read`
   - `im:read`
   - `mpim:read`
4. 安装到工作区
5. 获取 Bot Token（如：`xoxb-xxx-xxx-xxx`）

### 6.2 配置 .env

```bash
# 启用 Slack
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your-signing-secret
```

### 6.3 启动服务

```bash
python -m nanogridbot serve
```

### 6.4 使用

1. 将 Bot 添加到频道
2. 在频道中 @机器人 或直接发消息

---

## 7. 智能体任务示例

### 7.1 代码开发

```
帮我用 Python 实现一个 LRU Cache，支持 get 和 put 操作，时间复杂度 O(1)
```

### 7.2 代码审查

```
请审查以下代码的性能问题：
[粘贴代码]
```

### 7.3 Deep Research

```
请帮我研究 Claude Agent SDK 的最新功能，并总结其架构设计
```

### 7.4 长时任务

在 Shell 模式下，可以进行多轮对话：

```bash
$ python -m nanogridbot shell
> 我想开发一个完整的 REST API 项目，请先规划一下架构
> (AI 开始规划...)
> 好的，请开始实现用户模块
> (AI 继续实现...)
> 现在添加认证模块
```

### 7.5 定时任务

通过 Web 面板或 API 创建定时任务：

```bash
# 查看 API
curl http://localhost:8080/api/tasks
```

---

## 8. 常见问题

### Q1: Docker 镜像构建失败

**解决方案**：
```bash
# 清理 Docker 缓存
docker builder prune

# 重新构建
cd container && ./build.sh
```

### Q2: 容器启动超时

**解决方案**：
- 检查网络（需要访问 npm 仓库）
- 增加超时配置：`CONTAINER_TIMEOUT=3600`

### Q3: API Key 错误

**解决方案**：
- 确认 `.env` 文件中 `ANTHROPIC_API_KEY` 正确
- 检查格式：`sk-ant-` 开头

### Q4: 端口占用

**解决方案**：
```bash
# 检查端口
lsof -i :8080

# 修改端口
WEB_PORT=8081 python -m nanogridbot serve
```

### Q5: 想用不同的模型

**方案一**：通过环境变量
```bash
python -m nanogridbot run -p "问题" -e ANTHROPIC_MODEL=claude-opus-4-20250514
```

**方案二**：修改 .env 默认模型
```bash
ANTHROPIC_MODEL=claude-opus-4-20250514
```

---

## 下一步

1. **Web 监控面板**：启动后访问 `http://localhost:8080`
2. **查看日志**：`python -m nanogridbot logs -f`
3. **自定义技能**：参考 `docs/` 中的插件开发文档

---

**文档版本**: 1.0
**最后更新**: 2026-02-17
