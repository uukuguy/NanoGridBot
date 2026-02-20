# ============================================================
# NanoGridBot Makefile - Variables
# ============================================================

# Rust toolchain
CARGO := cargo
CARGO_FLAGS :=

# Python toolchain
PYTHON := python
UV := uv
PYTEST := pytest
RUFF := ruff
BLACK := black
ISORT := isort
MYPY := mypy

# Node.js toolchain
NPM := npm

# Docker
DOCKER := docker
DOCKER_IMAGE := nanogridbot-agent
DOCKER_TAG := latest

# Directories
RUST_SRC := crates
PYTHON_SRC := src/nanogridbot
CONTAINER_DIR := container
AGENT_RUNNER_DIR := $(CONTAINER_DIR)/agent-runner
TESTS_DIR := tests
DOCS_DIR := docs

# CLI binary
CLI_CRATE := ngb-cli

# Default port
PORT ?= 10042

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
CYAN := \033[0;36m
BOLD := \033[1m
NC := \033[0m
