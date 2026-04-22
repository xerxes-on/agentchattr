#!/usr/bin/env sh
# agentchattr — connect a remote machine to the shared xerxes.uz hub
# Usage:
#   sh start_remote.sh codex
#   sh start_remote.sh --api qwen

cd "$(dirname "$0")/.."

AGENTCHATTR_WEB_URL="${AGENTCHATTR_WEB_URL:-https://chat.xerxes.uz}"
AGENTCHATTR_MCP_HTTP_URL="${AGENTCHATTR_MCP_HTTP_URL:-https://mcp.xerxes.uz/mcp}"
AGENTCHATTR_MCP_SSE_URL="${AGENTCHATTR_MCP_SSE_URL:-https://sse.xerxes.uz/sse}"
AGENTCHATTR_SHARED_SECRET="${AGENTCHATTR_SHARED_SECRET:-_vrmlQYXaxyrILjsIlpqo4-WDRqsCDbw}"

MODE="cli"
if [ "$1" = "--api" ]; then
    MODE="api"
    shift
fi

AGENT_NAME="$1"
if [ -z "$AGENT_NAME" ]; then
    echo "Usage: sh start_remote.sh [--api] <agent_name>"
    echo "Examples:"
    echo "  sh start_remote.sh codex"
    echo "  sh start_remote.sh --api qwen"
    exit 1
fi

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Python 3 is required but was not found on PATH."
    exit 1
fi

ensure_venv() {
    if [ -d ".venv" ] && [ ! -x ".venv/bin/python" ]; then
        echo "Recreating .venv for this platform..."
        rm -rf .venv
    fi

    if [ ! -x ".venv/bin/python" ]; then
        echo "Creating virtual environment..."
        "$PYTHON_BIN" -m venv .venv || {
            echo "Error: failed to create .venv with $PYTHON_BIN."
            exit 1
        }
        .venv/bin/python -m pip install -q -r requirements.txt || {
            echo "Error: failed to install Python dependencies."
            exit 1
        }
    fi
}

ensure_venv

export AGENTCHATTR_WEB_URL
export AGENTCHATTR_MCP_HTTP_URL
export AGENTCHATTR_MCP_SSE_URL
export AGENTCHATTR_SHARED_SECRET

echo "agentchattr remote hub"
echo "  Web: $AGENTCHATTR_WEB_URL"
echo "  MCP HTTP: $AGENTCHATTR_MCP_HTTP_URL"
echo "  MCP SSE: $AGENTCHATTR_MCP_SSE_URL"

if [ "$MODE" = "api" ]; then
    .venv/bin/python wrapper_api.py "$AGENT_NAME"
else
    .venv/bin/python wrapper.py "$AGENT_NAME"
fi
