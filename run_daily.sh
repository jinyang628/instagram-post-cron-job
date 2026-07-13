#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m app.instagram_publisher
fi

exec python3 -m app.instagram_publisher
