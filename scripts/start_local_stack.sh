#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.local.yml"
RUNTIME_DIR="$PROJECT_ROOT/data/runtime"
PID_DIR="$RUNTIME_DIR/pids"
LOG_DIR="$RUNTIME_DIR/logs"
CONDA_ENV_NAME="${SMART_ASSEMBLY_CONDA_ENV:-torch}"
CONDA_SH_PATH=""

NO_INFRA=0
NO_LOGGER=0
NO_DASHBOARD=0
NO_PIPELINE=0

usage() {
  cat <<'EOF'
Usage:
  bash scripts/start_local_stack.sh [options]

Options:
  --conda-env <name>   Conda environment name to activate. Default: torch
  --no-infra           Skip docker compose + migrations
  --no-logger          Do not start the logger service
  --no-dashboard       Do not start the dashboard service
  --no-pipeline        Do not run the vision pipeline
  --help               Show this help

Environment:
  SMART_ASSEMBLY_CONDA_ENV   Default conda env if --conda-env is not passed
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --conda-env)
      CONDA_ENV_NAME="$2"
      shift 2
      ;;
    --no-infra)
      NO_INFRA=1
      shift
      ;;
    --no-logger)
      NO_LOGGER=1
      shift
      ;;
    --no-dashboard)
      NO_DASHBOARD=1
      shift
      ;;
    --no-pipeline)
      NO_PIPELINE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "$PID_DIR" "$LOG_DIR"

activate_conda() {
  if [[ -n "${CONDA_EXE:-}" ]]; then
    CONDA_SH_PATH="$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh"
    # shellcheck disable=SC1091
    source "$CONDA_SH_PATH"
  elif command -v conda >/dev/null 2>&1; then
    local conda_base
    conda_base="$(conda info --base)"
    CONDA_SH_PATH="$conda_base/etc/profile.d/conda.sh"
    # shellcheck disable=SC1090
    source "$CONDA_SH_PATH"
  else
    echo "Conda was not found. Open WSL in an environment where conda is available." >&2
    exit 1
  fi

  conda activate "$CONDA_ENV_NAME"
}

wait_for_container() {
  local container_name="$1"
  local timeout_seconds="${2:-90}"
  local deadline=$((SECONDS + timeout_seconds))

  while (( SECONDS < deadline )); do
    local status=""
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_name" 2>/dev/null || true)"
    if [[ "$status" == "healthy" || "$status" == "running" ]]; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for container '$container_name'." >&2
  exit 1
}

start_background_service() {
  local name="$1"
  local command="$2"
  local log_file="$LOG_DIR/${name}.log"
  local pid_file="$PID_DIR/${name}.pid"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" >/dev/null 2>&1; then
      echo "$name is already running with PID $existing_pid"
      return 0
    fi
    rm -f "$pid_file"
  fi

  echo "Starting $name..."
  nohup bash -lc "cd \"$PROJECT_ROOT\" && source \"$CONDA_SH_PATH\" && conda activate \"$CONDA_ENV_NAME\" && $command" >"$log_file" 2>&1 &
  local service_pid=$!
  echo "$service_pid" >"$pid_file"
  sleep 1
  if ! kill -0 "$service_pid" >/dev/null 2>&1; then
    echo "$name failed to stay running. Last log lines:" >&2
    tail -n 40 "$log_file" >&2 || true
    exit 1
  fi
  echo "$name started with PID $service_pid"
  echo "Log: $log_file"
}

cd "$PROJECT_ROOT"
activate_conda

echo "Project root: $PROJECT_ROOT"
echo "Using conda environment: $CONDA_ENV_NAME"

if [[ "$NO_INFRA" -eq 0 ]]; then
  echo "Starting PostgreSQL and Mosquitto with Docker Compose..."
  docker compose -f "$COMPOSE_FILE" up -d

  echo "Waiting for PostgreSQL..."
  wait_for_container "smart-assembly-db" 90

  echo "Waiting for MQTT broker..."
  wait_for_container "smart-assembly-mqtt" 30

  echo "Applying Alembic migrations..."
  python -m alembic upgrade head
fi

if [[ "$NO_LOGGER" -eq 0 ]]; then
  start_background_service "logger" "python -u src/utils/logger.py"
fi

if [[ "$NO_DASHBOARD" -eq 0 ]]; then
  start_background_service "dashboard" "python -u -m uvicorn src.dashboard.main:app --host 0.0.0.0 --port 8000 --reload"
fi

echo
echo "Local stack is starting."
echo "Dashboard: http://127.0.0.1:8000"
echo "PostgreSQL: localhost:5433"
echo "MQTT Broker: localhost:1883"
echo "Logs directory: $LOG_DIR"

if [[ "$NO_PIPELINE" -eq 0 ]]; then
  echo
  echo "Starting vision pipeline in the current terminal..."
  python scripts/run_pipeline.py
else
  echo
  echo "Pipeline not started because --no-pipeline was used."
fi
