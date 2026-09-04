#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 or newer is required, but python3 was not found." >&2
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating .venv..."
    python3 -m venv .venv
fi

echo "Installing the bot..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env. Add your Telegram settings before starting the bot."
else
    echo "Keeping the existing .env file unchanged."
fi

echo "Installation complete. Run: sh start.sh"

