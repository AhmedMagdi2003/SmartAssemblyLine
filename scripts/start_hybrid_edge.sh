#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/deployment/cloud/env/edge-hybrid.env"
CONDA_ENV_NAME="${SMART_ASSEMBLY_CONDA_ENV:-torch}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/start_hybrid_edge.sh [--env-file path] [--conda-env name]

This starts only the local vision pipeline and exports cloud MQTT settings first.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --conda-env)
      CONDA_ENV_NAME="$2"
      shift 2
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

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Hybrid edge env file not found: $ENV_FILE" >&2
  echo "Create it from deployment/cloud/env/edge-hybrid.env.example first." >&2
  exit 1
fi

activate_conda() {
  if [[ -n "${CONDA_EXE:-}" ]]; then
    # shellcheck disable=SC1091
    source "$(dirname "$(dirname "$CONDA_EXE")")/etc/profile.d/conda.sh"
  elif command -v conda >/dev/null 2>&1; then
    local conda_base
    conda_base="$(conda info --base)"
    # shellcheck disable=SC1090
    source "$conda_base/etc/profile.d/conda.sh"
  else
    echo "Conda was not found in this shell." >&2
    exit 1
  fi
  conda activate "$CONDA_ENV_NAME"
}

set -a
source "$ENV_FILE"
set +a

cd "$PROJECT_ROOT"
activate_conda

echo "Running Smart Assembly Line hybrid edge mode"
echo "Project root: $PROJECT_ROOT"
echo "Using conda environment: $CONDA_ENV_NAME"
echo "Publishing to MQTT broker: ${MQTT_HOST:-localhost}:${MQTT_PORT:-1883}"
echo "Topic: ${MQTT_TOPIC:-factory/assembly/boxes}"

python scripts/run_pipeline.py
