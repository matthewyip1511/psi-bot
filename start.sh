#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if [ ! -x ".venv/bin/python" ]; then
    echo "The local Python environment is missing. Run: sh install.sh" >&2
    exit 1
fi

if [ ! -f ".env" ]; then
    echo ".env is missing. Copy .env.example to .env and fill in the required values." >&2
    exit 1
fi

exec .venv/bin/python -m psi_bot

