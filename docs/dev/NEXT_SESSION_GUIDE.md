# 下一阶段开发指南

## 当前状态

**阶段**: 架构设计完成 ✅
**日期**: 2026-02-13
**状态**: 准备开始实施

---

## 已完成工作

### 1. 项目分析
- ✅ NanoClaw 项目深度分析（20+ 文件，5,077 行代码）
- ✅ 核心模块功能分析（7 个核心模块）
- ✅ 设计模式识别
- ✅ 技术栈评估
- ✅ 数据流分析
- ✅ 安全模型分析

### 2. 架构设计
- ✅ 完整项目结构设计
- ✅ 技术栈映射（TypeScript → Python）
- ✅ 核心模块详细设计（含代码示例）
- ✅ 扩展功能设计
- ✅ 14 周实施方案

### 3. 文档体系
- ✅ README.md - 项目概览
- ✅ docs/README.md - 文档索引
- ✅ docs/design/NANOGRIDBOT_DESIGN.md - 架构设计（53KB）
- ✅ docs/design/IMPLEMENTATION_PLAN.md - 实施方案
- ✅ docs/main/ANALYSIS_SUMMARY.md - 分析总结（13KB）
- ✅ docs/main/QUICK_START.md - 快速开始（8.4KB）
- ✅ docs/main/WORK_LOG.md - 工作日志

---

## 下一阶段：基础架构搭建（第 1-2 周）

### 目标
建立项目骨架和核心基础设施

### 任务清单

#### 1. 创建项目结构 ⏳
```bash
# 创建目录结构
mkdir -p src/nanogridbot/{core,database,channels,plugins,web,utils}
mkdir -p container/agent_runner
mkdir -p bridge
mkdir -p tests/{unit,integration,e2e}
mkdir -p groups/{main,global}
mkdir -p data/{ipc,sessions,env}
mkdir -p store/auth
```

#### 2. 配置项目 ⏳
- [ ] 创建 `pyproject.toml`
  - 定义项目元数据
  - 配置依赖（asyncio、aiosqlite、pydantic、fastapi 等）
  - 配置开发工具（black、ruff、mypy、pytest）
- [ ] 创建 `.gitignore`
- [ ] 创建 `.pre-commit-config.yaml`
- [ ] 设置虚拟环境

#### 3. 实现基础模块 ⏳
- [ ] `src/nanogridbot/__init__.py`
- [ ] `src/nanogridbot/config.py` - 配置管理
  - 环境变量加载
  - 路径配置
  - 常量定义
- [ ] `src/nanogridbot/logger.py` - 日志配置
  - Loguru 配置
  - 日志级别
  - 日志格式
- [ ] `src/nanogridbot/types.py` - Pydantic 数据模型
  - Message
  - RegisteredGroup
  - ContainerConfig
  - ScheduledTask
  - ContainerOutput

#### 4. 设置 CI/CD ⏳
- [ ] 创建 `.github/workflows/test.yml`
  - 运行测试
  - 代码质量检查
  - 类型检查
- [ ] 创建 `.github/workflows/release.yml`
  - 构建 Docker 镜像
  - 发布到 PyPI

#### 5. 编写基础测试 ⏳
- [ ] `tests/conftest.py` - pytest 配置
- [ ] `tests/unit/test_config.py` - 配置测试
- [ ] `tests/unit/test_types.py` - 数据模型测试

---

## 技术要点

### 1. 项目配置 (pyproject.toml)

```toml
[project]
name = "nanogridbot"
version = "0.1.0"
description = "Personal Claude AI assistant accessible via WhatsApp"
requires-python = ">=3.12"
dependencies = [
    "aiosqlite>=0.19.0",
    "loguru>=0.7.0",
    "pydantic>=2.5.0",
    "croniter>=2.0.0",
    "aiofiles>=23.2.0",
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.12.0",
    "ruff>=0.1.9",
    "mypy>=1.8.0",
]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

### 2. 配置管理 (config.py)

```python
from pathlib import Path
import os

class Config:
    # 基础路径
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    STORE_DIR = PROJECT_ROOT / "store"
    GROUPS_DIR = PROJECT_ROOT / "groups"
    DATA_DIR = PROJECT_ROOT / "data"

    # 助手配置
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Andy")
    TRIGGER_PATTERN = rf"^@{ASSISTANT_NAME}\b"

    # 轮询间隔
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2000"))
    SCHEDULER_POLL_INTERVAL = int(os.getenv("SCHEDULER_POLL_INTERVAL", "60000"))

    # 容器配置
    CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "nanogridbot-agent:latest")
    CONTAINER_TIMEOUT = int(os.getenv("CONTAINER_TIMEOUT", "1800000"))
    MAX_CONCURRENT_CONTAINERS = int(os.getenv("MAX_CONCURRENT_CONTAINERS", "5"))

    # 日志级别
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

### 3. 日志配置 (logger.py)

```python
from loguru import logger
import sys

def setup_logger(level: str = "INFO"):
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/nanogridbot.log",
        rotation="500 MB",
        retention="10 days",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
```

---

## 注意事项

### 1. Python 版本
- 必须使用 Python 3.12+
- 使用最新的类型注解语法（`list[str]` 而非 `List[str]`）

### 2. 异步编程
- 所有 I/O 操作使用 async/await
- 使用 aiosqlite 而非 sqlite3
- 使用 aiofiles 处理文件操作

### 3. 类型安全
- 所有函数必须有类型注解
- 使用 Pydantic 进行数据验证
- 运行 mypy 进行类型检查

### 4. 代码质量
- 使用 Black 格式化代码（行长 100）
- 使用 Ruff 进行 Linting
- 遵循 PEP 8 规范

### 5. 测试
- 使用 pytest 和 pytest-asyncio
- 目标覆盖率 > 80%
- 每个模块都要有对应的测试文件

---

## 参考文档

- [架构设计文档](../design/NANOGRIDBOT_DESIGN.md) - 详细的模块设计
- [实施方案](../design/IMPLEMENTATION_PLAN.md) - 开发阶段规划
- [快速开始](../main/QUICK_START.md) - 安装和使用指南

---

## 常见问题

### Q: 为什么选择 Baileys 桥接而不是纯 Python WhatsApp 库？
A: Baileys 是最成熟的 WhatsApp Web 协议实现，通过 Node.js 子进程桥接可以复用其稳定性，同时保持 Python 主应用的优势。

### Q: 为什么使用 asyncio 而不是多线程？
A: asyncio 更适合 I/O 密集型任务，性能更好，且避免了 GIL 的限制。

### Q: 数据库为什么选择 SQLite？
A: 与原版保持一致，SQLite 足够轻量且可靠，适合单机部署。未来可以扩展支持 PostgreSQL。

---

## 第一周目标

- [ ] 完成项目骨架搭建
- [ ] 实现配置和日志模块
- [ ] 定义所有 Pydantic 模型
- [ ] 编写基础单元测试
- [ ] 设置 CI/CD 流程
- [ ] 通过所有代码质量检查

---

## 联系方式

如有问题，请参考文档或提交 Issue。

---

**创建日期**: 2026-02-13
**更新日期**: 2026-02-13
**下次更新**: 第一周结束后
