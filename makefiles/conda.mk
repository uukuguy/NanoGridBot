# ============================================================
# GridCode Makefile - Conda 模块
# ============================================================
# Conda 环境专用命令（仅 Linux 服务器使用）
# 依赖: mk/variables.mk
# ============================================================

include makefiles/variables.mk

# Conda 依赖包列表（消除 5 处重复）
CONDA_BASE_DEPS := pydantic pydantic-settings lancedb mcp typer rich loguru \
                   anthropic claude-agent-sdk "pydantic-ai>=1.0.0" \
                   langgraph langchain-anthropic langchain-openai sentence-transformers

CONDA_DEV_DEPS := $(CONDA_BASE_DEPS) pytest pytest-asyncio ruff

CONDA_ALL_DEPS := $(CONDA_DEV_DEPS) tantivy whoosh jieba qdrant-client

CONDA_OCR_DEPS := docling $(CONDA_BASE_DEPS) rapidocr-onnxruntime

CONDA_FULL_DEPS := docling $(CONDA_BASE_DEPS)

CONDA_INSTALL_FLAGS := -c constraints-conda.txt --upgrade-strategy only-if-needed

#----------------------------------------------------------------------
# Conda 安装目标
#----------------------------------------------------------------------

install-conda: ## Install in conda environment (uses system torch)
	@echo "$(BLUE)Installing GridCode in conda environment...$(NC)"
	@echo "$(YELLOW)Prerequisite: conda environment with torch, tiktoken already installed$(NC)"
	@echo "$(YELLOW)Note: docling excluded (ingest on Mac, serve on Linux)$(NC)"
	@echo "$(YELLOW)Step 1: Installing dependencies...$(NC)"
	pip install $(CONDA_INSTALL_FLAGS) $(CONDA_BASE_DEPS)
	@echo "$(YELLOW)Step 2: Installing grid-code in editable mode...$(NC)"
	pip install -e . --no-deps
	@echo "$(GREEN)Installation complete!$(NC)"

install-conda-dev: ## Install with dev dependencies in conda environment
	@echo "$(BLUE)Installing GridCode with dev dependencies...$(NC)"
	@echo "$(YELLOW)Prerequisite: conda environment with torch, tiktoken already installed$(NC)"
	@echo "$(YELLOW)Step 1: Installing dependencies...$(NC)"
	pip install $(CONDA_INSTALL_FLAGS) $(CONDA_DEV_DEPS)
	@echo "$(YELLOW)Step 2: Installing grid-code in editable mode...$(NC)"
	pip install -e . --no-deps
	@echo "$(GREEN)Installation complete!$(NC)"

install-conda-all: ## Install with all optional backends in conda environment
	@echo "$(BLUE)Installing GridCode with all optional index backends...$(NC)"
	@echo "$(YELLOW)Prerequisite: conda environment with torch, tiktoken already installed$(NC)"
	@echo "$(YELLOW)Step 1: Installing dependencies...$(NC)"
	pip install $(CONDA_INSTALL_FLAGS) $(CONDA_ALL_DEPS)
	@echo "$(YELLOW)Step 2: Installing grid-code in editable mode...$(NC)"
	pip install -e . --no-deps
	@echo "$(GREEN)Installation complete!$(NC)"

install-conda-ocr: ## Install with OCR support in conda environment (requires docling)
	@echo "$(BLUE)Installing GridCode with OCR support...$(NC)"
	@echo "$(YELLOW)Prerequisite: conda environment with torch, tiktoken already installed$(NC)"
	@echo "$(YELLOW)Step 1: Installing dependencies (including docling for OCR)...$(NC)"
	pip install $(CONDA_INSTALL_FLAGS) $(CONDA_OCR_DEPS)
	@echo "$(YELLOW)Step 2: Installing grid-code in editable mode...$(NC)"
	pip install -e . --no-deps
	@echo "$(GREEN)Installation complete!$(NC)"

install-conda-full: ## Install with docling for ingest support in conda environment
	@echo "$(BLUE)Installing GridCode with full ingest support...$(NC)"
	pip install $(CONDA_INSTALL_FLAGS) $(CONDA_FULL_DEPS)
	pip install -e . --no-deps
	@echo "$(GREEN)Installation complete!$(NC)"
