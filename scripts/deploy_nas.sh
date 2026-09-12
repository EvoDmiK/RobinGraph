#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE="$ROOT_DIR/compose.nas.yml"
API_ENV=${ROBINGRAPH_NAS_API_ENV:-"$ROOT_DIR/.env.nas"}
TOOLS_ENV=${ROBINGRAPH_NAS_TOOLS_ENV:-"$ROOT_DIR/.env.nas.ingest"}
ACTION=${1:-deploy}

die() {
  echo "error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

env_value() {
  key=$1
  file=$2
  awk -v wanted="$key" '
    index($0, wanted "=") == 1 { value=substr($0, length(wanted)+2) }
    END { print value }
  ' "$file"
}

require_env_value() {
  key=$1
  file=$2
  value=$(env_value "$key" "$file")
  [ -n "$value" ] || die "$key must be set in $file"
}

require_file() {
  [ -f "$1" ] || die "missing environment file: $1"
}

check_network() {
  file=$1
  network=$(env_value ROBINGRAPH_EDGE_NETWORK "$file")
  network=${network:-robingraph-edge}
  docker network inspect "$network" >/dev/null 2>&1 ||
    die "external Docker network does not exist: $network"
}

compose_api() {
  docker compose --env-file "$API_ENV" -f "$COMPOSE_FILE" "$@"
}

compose_tools() {
  docker compose --env-file "$TOOLS_ENV" -f "$COMPOSE_FILE" --profile tools "$@"
}

build_tools_image() {
  # The workflow artifacts and deployers are copied into the image. Rebuild
  # before every deployment action so a NAS checkout cannot accidentally
  # publish definitions left in an older local image.
  compose_tools build --pull nas-tools
}

check_korean_vernacular_workflow() {
  compose_tools run --rm nas-tools \
    scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --remote
}

preflight_api() {
  require_command docker
  docker compose version >/dev/null
  require_file "$API_ENV"
  check_network "$API_ENV"
  mode=$(env_value ROBINGRAPH_API_MODE "$API_ENV")
  mode=${mode:-serve-fixture}
  case "$mode" in
    serve-fixture) ;;
    serve-neo4j)
      require_env_value NEO4J_URI "$API_ENV"
      require_env_value NEO4J_USERNAME "$API_ENV"
      require_env_value NEO4J_PASSWORD "$API_ENV"
      ;;
    *) die "ROBINGRAPH_API_MODE must be serve-fixture or serve-neo4j" ;;
  esac
  compose_api config --quiet
}

preflight_tools() {
  require_command docker
  docker compose version >/dev/null
  require_file "$TOOLS_ENV"
  check_network "$TOOLS_ENV"
  require_env_value ROBINGRAPH_N8N_API_URL "$TOOLS_ENV"
  require_env_value ROBINGRAPH_N8N_API_KEY "$TOOLS_ENV"
  compose_tools config --quiet
}

wait_for_api() {
  container_id=$(compose_api ps -q api)
  [ -n "$container_id" ] || die "API container was not created"
  attempts=0
  while [ "$attempts" -lt 60 ]; do
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")
    case "$health" in
      healthy)
        echo "RobinGraph API is healthy"
        return 0
        ;;
      unhealthy|exited|dead)
        compose_api logs --tail 100 api >&2
        die "API container entered state: $health"
        ;;
    esac
    attempts=$((attempts + 1))
    sleep 2
  done
  compose_api logs --tail 100 api >&2
  die "API health check timed out"
}

case "$ACTION" in
  preflight)
    preflight_api
    echo "NAS API deployment configuration is valid"
    ;;
  deploy)
    preflight_api
    compose_api build --pull api
    compose_api up -d --remove-orphans api
    wait_for_api
    ;;
  verify)
    preflight_api
    compose_api exec -T api python -c \
      "import json,urllib.request; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)), ensure_ascii=False))"
    ;;
  status)
    preflight_api
    compose_api ps
    ;;
  logs)
    preflight_api
    compose_api logs --tail 100 api
    ;;
  deploy-workflows)
    preflight_tools
    build_tools_image
    compose_tools run --rm nas-tools scripts/deploy_n8n_operational_ingest.py --apply
    compose_tools run --rm nas-tools scripts/deploy_n8n_reference_ingest.py --apply
    compose_tools run --rm nas-tools scripts/deploy_n8n_reference_ingest.py --workflow avonet --apply
    compose_tools run --rm nas-tools scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply
    echo "n8n workflow definitions deployed inactive; record any newly printed workflow IDs"
    ;;
  preflight-korean-vernacular)
    preflight_tools
    build_tools_image
    check_korean_vernacular_workflow
    echo "Korean vernacular workflow is ready for an inactive NAS deployment"
    ;;
  deploy-korean-vernacular)
    preflight_tools
    build_tools_image
    check_korean_vernacular_workflow
    compose_tools run --rm nas-tools \
      scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular --apply
    echo "Korean vernacular workflow deployed inactive; record a newly printed workflow ID before verification"
    ;;
  verify-korean-vernacular)
    preflight_tools
    require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"
    build_tools_image
    check_korean_vernacular_workflow
    ;;
  status-korean-vernacular)
    preflight_tools
    require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"
    build_tools_image
    compose_tools run --rm nas-tools scripts/manage_n8n_korean_vernacular.py status
    ;;
  activate-korean-vernacular)
    preflight_tools
    require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"
    build_tools_image
    compose_tools run --rm nas-tools scripts/manage_n8n_korean_vernacular.py activate --apply
    ;;
  deactivate-korean-vernacular)
    preflight_tools
    require_env_value ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID "$TOOLS_ENV"
    build_tools_image
    compose_tools run --rm nas-tools scripts/manage_n8n_korean_vernacular.py deactivate --apply
    ;;
  validate-avonet)
    preflight_tools
    compose_tools run --rm nas-tools scripts/load_n8n_avonet.py
    ;;
  ingest-avonet)
    preflight_tools
    require_env_value ROBINGRAPH_NEO4J_HTTP_URL "$TOOLS_ENV"
    require_env_value NEO4J_USERNAME "$TOOLS_ENV"
    require_env_value NEO4J_PASSWORD "$TOOLS_ENV"
    compose_tools run --rm nas-tools scripts/load_n8n_avonet.py --apply
    ;;
  *)
    die "usage: $0 {preflight|deploy|verify|status|logs|deploy-workflows|preflight-korean-vernacular|deploy-korean-vernacular|verify-korean-vernacular|status-korean-vernacular|activate-korean-vernacular|deactivate-korean-vernacular|validate-avonet|ingest-avonet}"
    ;;
esac

# Korean vernacular ingest runs natively inside n8n once deploy-workflows or
# deploy-korean-vernacular has created/updated it. Trigger it manually from
# the n8n UI, not from this script. See docs/n8n/korean-vernacular-ingest.md
# for the exact first-run checklist.
#
# status/activate/deactivate-korean-vernacular only flip the Public API
# `active` flag through scripts/manage_n8n_korean_vernacular.py -- they
# never run the workflow themselves. activate-korean-vernacular refuses
# (see that script's module docstring) unless the deployed canonical
# workflow still matches this checkout's reviewed artifact and its own
# execution history already shows a real, meaningful successful run.
