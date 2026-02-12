# NanoGridBot 多平台消息通道可行性评估报告

## 背景

评估为 NanoGridBot 添加 7 个消息平台的支持可行性，实现双向消息通信。

## 评估维度

针对每个平台从以下维度评估：
1. **Python 库成熟度** - 是否有官方/稳定 SDK
2. **协议复杂度** - 认证、消息格式、回调机制
3. **实现难度** - 基于通道接口的工作量
4. **维护风险** - 协议变更频率、社区支持

## 各平台详细评估

### 1. Telegram (⭐⭐ 简单)

| 维度 | 评估 |
|------|------|
| Python 库 | `python-telegram-bot` (官方，Benchmark 92.4) |
| 协议 | Bot API，HTTP polling/webhook |
| 认证 | Bot Token |
| 消息格式 | 标准 JSON |
| 实现难度 | **简单** - 成熟的官方异步 SDK |

**推荐方案**: 使用 `python-telegram-bot` 库，实现 `Application` 类处理 polling 或 webhook

**代码示例**:
```python
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

async def start(update: Update, context):
    await update.message.reply_text("Hello!")

app = Application.builder().token("BOT_TOKEN").build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
```

---

### 2. Slack (⭐⭐ 简单)

| 维度 | 评估 |
|------|------|
| Python 库 | `python-slack-sdk` (官方，Benchmark 83) |
| 协议 | WebSocket + HTTP API |
| 认证 | Bot User OAuth Token |
| 消息格式 | Block Kit JSON |
| 实现难度 | **简单** - 成熟的官方 SDK，支持 WebSocket 实时消息 |

**推荐方案**: 使用 `slack-sdk` 的 `SocketModeClient` 实现实时消息处理

**代码示例**:
```python
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient

web_client = WebClient(token="xoxb-...")
socket_client = SocketModeClient(
    app_token="xapp-...",
    web_client=web_client,
    message_handler=...
)
socket_client.connect()
```

---

### 3. Discord (⭐⭐ 简单)

| 维度 | 评估 |
|------|------|
| Python 库 | `discord.py` (主流，Benchmark 79.1) |
| 协议 | Gateway (WebSocket) + HTTP API |
| 认证 | Bot Token |
| 消息格式 | Embed + JSON |
| 实现难度 | **简单** - 成熟的异步库，社区活跃 |

**推荐方案**: 使用 `discord.py` 的 `Client` 类实现消息处理

**代码示例**:
```python
import discord

class MyClient(discord.Client):
    async def on_message(self, message):
        if message.author == self.user:
            return
        await message.reply(message.content)

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
client.run("BOT_TOKEN")
```

---

### 4. QQ (⭐⭐⭐ 中等)

| 维度 | 评估 |
|------|------|
| Python 库 | `NoneBot2` + OneBot 协议 |
| 协议 | OneBot v11 / v12 (WebSocket/HTTP) |
| 认证 | 无需认证 (通过中间件) |
| 消息格式 | CQ 码 JSON |
| 实现难度 | **中等** - 需要额外中间件 (NapCat/onebot-v11) |

**推荐方案**:
- 方案 A: NoneBot2 作为独立服务，NanoGridBot 通过 HTTP 调用
- 方案 B: 直接对接 NapCatQQ (OneBot 协议)

**注意**: QQ 机器人需要本地运行中间件 (NapCatQQ)，增加了部署复杂度

**NapCatQQ 部署**:
1. 下载 NapCatQQ 安装包
2. 配置 OneBot 协议
3. 获取 WebSocket 连接信息
4. NanoGridBot 通过 WebSocket 接收消息

---

### 5. 飞书 (⭐⭐⭐ 中等)

| 维度 | 评估 |
|------|------|
| Python 库 | `lark-oapi` (官方) |
| 协议 | HTTP API + 事件回调 (WebSocket) |
| 认证 | App ID + App Secret |
| 消息格式 | JSON |
| 实现难度 | **中等** - 官方 SDK 较新，需要处理加密签名验证 |

**推荐方案**: 使用 `lark-oapi` SDK，通过事件回调接收消息，OpenAPI 发送消息

**代码示例**:
```python
from lark_oapi import Lark

client = Lark(
    app_id="APP_ID",
    app_secret="APP_SECRET",
    log_level="DEBUG"
)

# 发送消息
response = client.im.message.create({
    "receive_id": "RECEIVE_ID",
    "msg_type": "text",
    "content": json.dumps({"text": "Hello"})
})
```

**注意**: 飞书支持自定义机器人和应用两种模式，应用模式功能更全但配置更复杂

---

### 6. 企业微信 (⭐⭐ 简单)

| 维度 | 评估 |
|------|------|
| Python 库 | 原生 HTTP (Webhook 方式，无需 SDK) |
| 协议 | Webhook |
| 认证 | Webhook URL (自带密钥) |
| 消息格式 | JSON |
| 实现难度 | **简单** - 纯 HTTP 请求即可 |

**推荐方案**: 直接使用 `httpx` 发送 POST 请求到 Webhook URL

**限制**: 仅支持群机器人，接收消息需要企业微信应用

**代码示例**:
```python
import httpx

async def send_wecom_message(webhook_url: str, content: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": content}}
        )
```

---

### 7. 钉钉 (⭐⭐ 简单-中等)

| 维度 | 评估 |
|------|------|
| Python 库 | `dingtalk-stream-sdk-python` (官方) |
| 协议 | Stream 模式 (WebSocket) + Webhook |
| 认证 | App Key + App Secret |
| 消息格式 | JSON (卡片消息) |
| 实现难度 | **简单-中等** - 官方 Stream SDK 简化了复杂度 |

**推荐方案**: 使用 Stream 模式 SDK 处理事件回调，Webhook 发送消息

**代码示例**:
```python
from dingtalk_stream import AckMessage
from dingtalk_stream import CallbackClient

async def on_callback_event(event):
    # 处理消息
    return AckMessage(status=200)

client = CallbackClient(
    client_id="DINGTALK_CLIENT_ID",
    client_secret="DINGTALK_CLIENT_SECRET"
)
client.register_callback_handler(event, on_callback_event)
client.start_forever()
```

---

## 综合对比

| 平台 | 实现难度 | 依赖库 | 认证复杂度 | 维护风险 | 推荐优先级 |
|------|----------|--------|------------|----------|------------|
| Telegram | ⭐⭐ 简单 | python-telegram-bot | Token | 低 | 1 |
| Slack | ⭐⭐ 简单 | python-slack-sdk | OAuth Token | 低 | 2 |
| Discord | ⭐⭐ 简单 | discord.py | Token | 低 | 3 |
| 企业微信 | ⭐⭐ 简单 | httpx (原生) | Webhook URL | 低 | 4 |
| 钉钉 | ⭐⭐ 中等 | dingtalk-stream-sdk | App 凭证 | 低 | 5 |
| 飞书 | ⭐⭐⭐ 中等 | lark-oapi | App 凭证 | 中 | 6 |
| QQ | ⭐⭐⭐ 中等 | NoneBot2/OneBot | 协议认证 | 高 | 7 |

## JID 格式设计

| 平台 | JID 格式示例 | 说明 |
|------|-------------|------|
| Telegram | `telegram:chat_id` | chat_id 为数字 |
| Slack | `slack:channel_id:team_id` | 支持多团队 |
| Discord | `discord:channel_id:guild_id` | 支持服务器/频道 |
| QQ | `qq:group_id` | 通过 OneBot |
| 飞书 | `feishu:open_id` 或 `feishu:chat_id` | 支持会话ID |
| 企业微信 | `wecom:webhook_key` | Webhook 标识 |
| 钉钉 | `dingtalk:open_conversation_id` | 会话标识 |

## 架构设计要点

### 1. 通道工厂模式

```python
class ChannelFactory:
    _channels: Dict[ChannelType, Type[Channel]] = {}

    @classmethod
    def register(cls, channel_type: ChannelType, channel_class: Type[Channel]):
        cls._channels[channel_type] = channel_class

    @classmethod
    def create(cls, config: ChannelConfig) -> Channel:
        channel_class = cls._channels.get(config.type)
        if not channel_class:
            raise ValueError(f"Unknown channel type: {config.type}")
        return channel_class(config)
```

### 2. 统一消息适配器

```python
class MessageAdapter(ABC):
    """平台消息适配器"""

    @abstractmethod
    def to_internal(self, raw_message: Any) -> Message:
        """将平台消息转换为内部格式"""

    @abstractmethod
    def from_internal(self, message: Message) -> Any:
        """将内部消息转换为平台格式"""
```

### 3. 事件回调处理

```python
class ChannelEventHandler:
    async def handle_inbound(self, channel: Channel, raw_event: Any):
        message = channel.adapter.to_internal(raw_event)
        await self.message_queue.put(message)

    async def handle_outbound(self, jid: str, text: str):
        channel = self.router.find_channel(jid)
        await channel.send_message(jid, text)
```

## 实施计划

### 阶段 1: 基础设施 (优先级最高)
- [ ] 完善通道抽象接口
- [ ] 定义统一的 JID 格式规范
- [ ] 实现 JID 解析和路由工具函数

### 阶段 2: 简单平台 (1-2周)
1. **Telegram** - 2-3 天
2. **Slack** - 2-3 天
3. **Discord** - 2-3 天
4. **企业微信** - 1-2 天

### 阶段 3: 中等平台 (3-4周)
5. **钉钉** - 3-4 天
6. **飞书** - 4-5 天
7. **QQ** - 4-5 天 (需要 NapCat 中间件)

### 阶段 4: 集成测试
- 端到端消息收发测试
- 并发处理测试
- 错误处理和重连测试

**总工作量预估**: 约 20-25 个开发日

## 风险评估

| 风险 | 影响平台 | 缓解措施 |
|------|----------|----------|
| 协议变更 | 所有平台 | 使用官方 SDK，定期更新 |
| 账号风险 | QQ | 遵守协议，使用中间件 |
| API 限流 | 飞书/钉钉 | 实现指数退避 |
| 认证失效 | 所有 | 定期刷新 token |

## 结论

NanoGridBot 添加多平台支持在技术上是**完全可行**的：

1. **6/7 平台有成熟 Python SDK**，实现难度低
2. **通道抽象设计优秀**，新通道接入成本低
3. **建议分三阶段实现**，从简单平台开始
4. **QQ 平台需要额外中间件**，复杂度最高

---

**创建日期**: 2026-02-13
**更新日期**: 2026-02-13
