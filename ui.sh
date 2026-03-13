#!/bin/bash
set -a
[ -f .env ] && source .env
set +a
PORT=${ADAM_PORT:-64321}
echo "Starting ui on explicit port $PORT"
uv run uvicorn app.app:app --port $PORT --reload "$@"
