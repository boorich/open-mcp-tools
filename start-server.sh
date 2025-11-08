#!/usr/bin/env bash
set -e

# Open MCP Tools Server startup script
cd "$(dirname "$0")"

# Load environment if .env exists
if [ -f .env ]; then
    echo "📝 Loading configuration from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Use uv if available, fall back to python -m
if command -v uv &> /dev/null; then
    echo "🚀 Starting Open MCP Tools Server with uv..."
    exec uv run open-mcp-tools serve
elif command -v open-mcp-tools &> /dev/null; then
    echo "🚀 Starting Open MCP Tools Server..."
    exec open-mcp-tools serve
else
    echo "🚀 Starting Open MCP Tools Server with python -m..."
    exec python -m open_mcp_tools.cli serve
fi
