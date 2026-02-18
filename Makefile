# ============================================================
# NanoGridBot Makefile
# ============================================================
# Hybrid project: Rust (host) + Python (legacy) + Node.js (agent container)
#
# Usage: make help
# ============================================================

include makefiles/variables.mk
include makefiles/conda.mk

.DEFAULT_GOAL := help

# ============================================================
# Help
# ============================================================

.PHONY: help
help: ## Show this help
	@echo "$(BOLD)NanoGridBot - Agent Dev Console & Lightweight Runtime$(NC)"
	@echo ""
	@echo "$(CYAN)Usage:$(NC) make <target>"
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-24s$(NC) %s\n", $$1, $$2}'

# ============================================================
# Rust - Build
# ============================================================

.PHONY: build build-release check
build: ## Build all Rust crates (debug)
	$(CARGO) build --workspace $(CARGO_FLAGS)

build-release: ## Build all Rust crates (release, optimized)
	$(CARGO) build --workspace --release $(CARGO_FLAGS)

check: ## Type-check all Rust crates without building
	$(CARGO) check --workspace

# ============================================================
# Rust - Test
# ============================================================

.PHONY: test test-rust test-rust-verbose test-crate
test-rust: ## Run all Rust tests
	$(CARGO) test --workspace

test-rust-verbose: ## Run all Rust tests with output
	$(CARGO) test --workspace -- --nocapture

test-crate: ## Run tests for a specific crate (CRATE=ngb-core)
	@if [ -z "$(CRATE)" ]; then echo "$(RED)Usage: make test-crate CRATE=ngb-core$(NC)"; exit 1; fi
	$(CARGO) test -p $(CRATE) -- --nocapture

# ============================================================
# Rust - Lint & Format
# ============================================================

.PHONY: fmt fmt-check clippy lint-rust
fmt: ## Format all Rust code
	$(CARGO) fmt --all

fmt-check: ## Check Rust formatting (CI)
	$(CARGO) fmt --all -- --check

clippy: ## Run clippy linter on all crates
	$(CARGO) clippy --workspace -- -D warnings

lint-rust: fmt-check clippy ## Run all Rust lint checks

# ============================================================
# Python - Test
# ============================================================

.PHONY: test-py test-py-verbose test-py-cov
test-py: ## Run all Python tests
	$(PYTEST) -x

test-py-verbose: ## Run Python tests with verbose output
	$(PYTEST) -xvs

test-py-cov: ## Run Python tests with coverage report
	$(PYTEST) --cov=$(PYTHON_SRC) --cov-report=term-missing

# ============================================================
# Python - Lint & Format
# ============================================================

.PHONY: format-py lint-py typecheck-py
format-py: ## Format Python code (black + isort)
	$(BLACK) . && $(ISORT) .

lint-py: ## Lint Python code (ruff)
	$(RUFF) check .

typecheck-py: ## Type-check Python code (mypy)
	$(MYPY) $(PYTHON_SRC)/

# ============================================================
# Container - Agent Runner (Node.js)
# ============================================================

.PHONY: agent-install agent-build agent-clean

$(AGENT_RUNNER_DIR)/node_modules: $(AGENT_RUNNER_DIR)/package.json
	cd $(AGENT_RUNNER_DIR) && $(NPM) install
	@touch $@

agent-install: $(AGENT_RUNNER_DIR)/node_modules ## Install agent-runner npm dependencies

agent-build: $(AGENT_RUNNER_DIR)/node_modules ## Build agent-runner TypeScript
	cd $(AGENT_RUNNER_DIR) && $(NPM) run build

agent-clean: ## Clean agent-runner build artifacts
	rm -rf $(AGENT_RUNNER_DIR)/dist $(AGENT_RUNNER_DIR)/node_modules

# ============================================================
# Docker
# ============================================================

.PHONY: docker-build docker-run docker-shell docker-clean
docker-build: ## Build Docker image (nanogridbot-agent)
	$(DOCKER) build -t $(DOCKER_IMAGE):$(DOCKER_TAG) $(CONTAINER_DIR)

docker-run: ## Run agent container interactively
	$(DOCKER) run -it --rm $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-shell: ## Open shell in agent container
	$(DOCKER) run -it --rm --entrypoint /bin/bash $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-clean: ## Remove agent Docker image
	$(DOCKER) rmi $(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || true

# ============================================================
# Run
# ============================================================

.PHONY: serve serve-release workspace-create workspace-list shell
serve: ## Start NanoGridBot (debug build)
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- serve

serve-release: ## Start NanoGridBot (release build)
	$(CARGO) run -p $(CLI_CRATE) --release -- serve

workspace-create: ## Create a workspace (NAME=my-agent)
	@if [ -z "$(NAME)" ]; then echo "$(RED)Usage: make workspace-create NAME=my-agent$(NC)"; exit 1; fi
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- workspace create $(NAME)

workspace-list: ## List all workspaces and bindings
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- workspace list

shell: ## Start TUI shell (WORKSPACE=my-workspace)
	@if [ -z "$(WORKSPACE)" ]; then echo "$(RED)Usage: make shell WORKSPACE=my-workspace$(NC)"; exit 1; fi
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- shell $(WORKSPACE)

shell-pipe: ## Start TUI shell with pipe transport
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- shell $(WORKSPACE) --transport pipe

shell-ipc: ## Start TUI shell with IPC transport
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- shell $(WORKSPACE) --transport ipc

shell-ws: ## Start TUI shell with WebSocket transport
	$(CARGO) run -p $(CLI_CRATE) $(CARGO_FLAGS) -- shell $(WORKSPACE) --transport ws

# ============================================================
# Combined Targets
# ============================================================

.PHONY: test lint format ci clean
test: test-rust test-py ## Run all tests (Rust + Python)

lint: lint-rust lint-py typecheck-py ## Run all linters (Rust + Python)

format: fmt format-py ## Format all code (Rust + Python)

ci: lint test ## Run full CI pipeline (lint + test)

# ============================================================
# Clean
# ============================================================

clean: ## Clean all build artifacts
	$(CARGO) clean
	rm -rf $(AGENT_RUNNER_DIR)/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ============================================================
# Setup & Dependencies
# ============================================================

.PHONY: setup setup-rust setup-py setup-hooks
setup: setup-rust setup-py setup-hooks ## Full development environment setup

setup-rust: ## Install Rust toolchain components
	rustup component add clippy rustfmt

setup-py: ## Install Python dev dependencies
	pip install -e ".[dev]"

setup-hooks: ## Install pre-commit hooks
	pre-commit install
