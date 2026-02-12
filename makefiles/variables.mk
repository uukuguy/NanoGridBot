# ============================================================
# GridCode Makefile 变量定义
# ============================================================

# 工具链
PYTHON := python
UV := uv
PYTEST := pytest
RUFF := ruff

# 命令前缀（消除 70+ 处重复）
UV_RUN := $(UV) run
GRIDCODE_CMD := $(UV_RUN) $(GRIDCODE)
PY_CMD := $(UV_RUN) $(PYTHON)

# 命令行缺省全局参数
PORT ?= 10042

# 颜色输出
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m
