#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
docker build -t nanogridbot-agent:latest "$SCRIPT_DIR"
echo "Built nanogridbot-agent:latest"
