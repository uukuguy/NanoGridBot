# NanoGridBot 快速启动和E2E测试指引

## 前提条件

- Python 3.12+
- Docker Desktop (用于容器运行)
- 至少一个消息平台的API凭证（推荐从Telegram开始）

## 快速启动步骤

### 1. 安装依赖

```bash
# 克隆项目（如果还没有）
cd /path/to/NanoGridBot

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -e .
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# .env
# 基础配置
LOG_LEVEL=INFO
DATA_DIR=./data

# Telegram配置（最简单的测试通道）
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# 可选：其他通道配置
# SLACK_BOT_TOKEN=xoxb-...
# DISCORD_BOT_TOKEN=...
# WHATSAPP_PHONE_NUMBER_ID=...
# WHATSAPP_ACCESS_TOKEN=...
```

**获取Telegram Bot Token**:
1. 在Telegram中搜索 @BotFather
2. 发送 `/newbot` 创建新机器人
3. 按提示设置名称，获取token
4. 发送 `/start` 给你的机器人
5. 访问 `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` 获取chat_id

### 3. 启动NanoGridBot

```bash
# 方式1: 使用Python模块
python -m nanogridbot

# 方式2: 使用CLI（如果已安装）
nanogridbot

# 方式3: 指定端口
python -m nanogridbot --port 8080

# 方式4: 调试模式
python -m nanogridbot --debug
```

启动成功后，你会看到：

```
INFO: Started server process
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:3000
```

### 4. 访问Web监控面板

打开浏览器访问：http://localhost:3000

你应该能看到：
- 系统状态
- 已注册的群组
- 计划任务
- 最近消息

## E2E测试场景

### 场景1: 基础消息收发测试

**目标**: 验证机器人能接收和响应消息

**步骤**:
1. 在Telegram中向你的机器人发送消息: "Hello"
2. 检查Web面板的"最近消息"部分，应该能看到这条消息
3. 检查日志输出，应该有消息接收的记录

**预期结果**:
- ✅ Web面板显示收到的消息
- ✅ 日志显示消息处理记录
- ✅ 无错误信息

### 场景2: 群组注册测试

**目标**: 注册一个测试群组

**步骤**:
1. 准备一个测试容器配置（或使用默认配置）
2. 通过API注册群组：

```bash
curl -X POST http://localhost:3000/api/groups \
  -H "Content-Type: application/json" \
  -d '{
    "jid": "telegram:123456789",
    "folder": "test-group",
    "trigger_pattern": "^/test",
    "container_config": {
      "image": "python:3.12-slim",
      "command": ["python", "-c", "print(\"Hello from container\")"],
      "timeout": 30
    }
  }'
```

3. 刷新Web面板，检查"已注册群组"部分

**预期结果**:
- ✅ API返回成功响应
- ✅ Web面板显示新注册的群组
- ✅ 群组状态为"active"

### 场景3: 容器执行测试

**目标**: 触发容器执行并获取响应

**步骤**:
1. 确保Docker Desktop正在运行
2. 在Telegram中发送触发消息: "/test hello"
3. 等待容器执行（可能需要几秒钟）
4. 检查机器人的响应

**预期结果**:
- ✅ 机器人回复容器的输出
- ✅ Web面板显示容器执行记录
- ✅ 日志显示容器启动和完成

### 场景4: 任务调度测试

**目标**: 创建并执行定时任务

**步骤**:
1. 创建一个简单的定时任务：

```bash
curl -X POST http://localhost:3000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "group_jid": "telegram:123456789",
    "schedule_type": "INTERVAL",
    "schedule_value": "60",
    "prompt": "定时任务测试"
  }'
```

2. 等待60秒
3. 检查Telegram是否收到定时消息
4. 在Web面板查看任务执行历史

**预期结果**:
- ✅ 任务创建成功
- ✅ 60秒后收到消息
- ✅ Web面板显示任务执行记录

### 场景5: 多通道测试（可选）

**目标**: 验证多个消息通道同时工作

**前提**: 已配置多个通道的凭证

**步骤**:
1. 在 `.env` 中添加第二个通道配置（如Slack）
2. 重启NanoGridBot
3. 分别在Telegram和Slack中发送消息
4. 检查Web面板是否显示来自两个通道的消息

**预期结果**:
- ✅ 两个通道都能接收消息
- ✅ Web面板正确区分不同通道
- ✅ 消息JID格式正确（telegram:xxx, slack:xxx）

## 常见问题排查

### 问题1: 启动失败 - 端口被占用

**错误信息**: `Address already in use`

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :3000

# 杀死进程或使用其他端口
python -m nanogridbot --port 8080
```

### 问题2: Telegram连接失败

**错误信息**: `Unauthorized` 或 `Invalid token`

**解决方案**:
1. 检查 `.env` 中的 `TELEGRAM_BOT_TOKEN` 是否正确
2. 确认token没有多余的空格
3. 重新从BotFather获取token

### 问题3: Docker容器无法启动

**错误信息**: `Cannot connect to Docker daemon`

**解决方案**:
```bash
# 检查Docker是否运行
docker ps

# 如果没有运行，启动Docker Desktop
# macOS: 打开Docker Desktop应用
# Linux: sudo systemctl start docker
```

### 问题4: 消息收不到

**可能原因**:
1. Bot没有权限读取消息
2. Chat ID配置错误
3. 网络连接问题

**解决方案**:
```bash
# 检查日志
tail -f logs/nanogridbot.log

# 测试API连接
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### 问题5: Web面板无法访问

**解决方案**:
```bash
# 检查服务是否运行
ps aux | grep nanogridbot

# 检查端口是否监听
netstat -an | grep 3000

# 尝试使用127.0.0.1而不是localhost
# http://127.0.0.1:3000
```

## 快速验证清单

启动后，按以下清单验证系统是否正常：

- [ ] Web面板可以访问 (http://localhost:3000)
- [ ] 健康检查通过 (http://localhost:3000/api/health)
- [ ] 至少一个通道连接成功
- [ ] 可以接收消息
- [ ] 可以注册群组
- [ ] 可以执行容器
- [ ] 日志正常输出

## 停止服务

```bash
# 如果在前台运行，按 Ctrl+C

# 如果在后台运行
pkill -f nanogridbot

# 或查找进程ID后杀死
ps aux | grep nanogridbot
kill <PID>
```

## 清理测试数据

```bash
# 删除数据库
rm -rf data/

# 删除日志
rm -rf logs/

# 重新创建目录
mkdir -p data logs
```

## 下一步

完成基础测试后，可以：

1. 阅读 [完整测试文档](./README.md)
2. 配置更多消息通道
3. 创建自定义容器镜像
4. 开发插件扩展功能
5. 部署到生产环境

## 获取帮助

- 查看日志: `tail -f logs/nanogridbot.log`
- 查看完整文档: `docs/testing/`
- 提交Issue: GitHub Issues
- 技术支持: support@nanogridbot.com

---

**提示**: 这是最简化的测试指引。对于生产环境部署，请参考完整的测试文档和部署指南。
