#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/deployment/cloud/env/dashboard-tunnel.env"
DASHBOARD_HOST="127.0.0.1"
DASHBOARD_PORT="8000"
TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/start_dashboard_tunnel.sh [options]

Options:
  --env-file <path>         Env file to load. Default: deployment/cloud/env/dashboard-tunnel.env
  --dashboard-host <host>   Local dashboard host. Default: 127.0.0.1
  --dashboard-port <port>   Local dashboard port. Default: 8000
  --token <token>           Cloudflare named tunnel token. If omitted, quick tunnel mode is used.
  --help                    Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --dashboard-host)
      DASHBOARD_HOST="$2"
      shift 2
      ;;
    --dashboard-port)
      DASHBOARD_PORT="$2"
      shift 2
      ;;
    --token)
      TUNNEL_TOKEN="$2"
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

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
  DASHBOARD_PORT="${DASHBOARD_PORT:-8000}"
  TUNNEL_TOKEN="${CLOUDFLARE_TUNNEL_TOKEN:-$TUNNEL_TOKEN}"
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared was not found in PATH." >&2
  echo "Install it first, then rerun this command." >&2
  exit 1
fi

LOCAL_URL="http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"

echo "Starting dashboard tunnel for ${LOCAL_URL}"

if [[ -n "$TUNNEL_TOKEN" ]]; then
  echo "Mode: named tunnel"
  exec cloudflared tunnel run --token "$TUNNEL_TOKEN"
fi

echo "Mode: quick tunnel"
echo "Cloudflare will print a temporary trycloudflare.com URL below."
exec cloudflared tunnel --url "$LOCAL_URL"
