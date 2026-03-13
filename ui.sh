#!/bin/bash
set -a
[ -f .env ] && source .env
set +a
PORT=${ADAM_PORT:-64321}
echo "Starting ui on explicit port $PORT"
python -m app.app --port $PORT "$@"
