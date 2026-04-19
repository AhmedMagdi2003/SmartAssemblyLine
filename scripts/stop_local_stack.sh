#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$PROJECT_ROOT/data/runtime/pids"
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.local.yml"

stop_service() {
  local name="$1"
  local pid_file="$PID_DIR/${name}.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not tracked."
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "Stopping $name (PID $pid)..."
    kill "$pid"
  else
    echo "$name PID $pid is not running."
  fi
  rm -f "$pid_file"
}

stop_service "logger"
stop_service "dashboard"

echo "Stopping Docker infrastructure..."
docker compose -f "$COMPOSE_FILE" down

echo "Local stack stopped."
