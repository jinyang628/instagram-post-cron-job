#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if [ -x .venv/bin/python ]; then
  exec .venv/bin/python instagram_publisher.py
fi

exec python3 instagram_publisher.py
