#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_ENV="$ROOT_DIR/.env.nas.test"
ACTION=${1:-}
case "$ACTION" in
  deploy|start|verify|status|stop) ;;
  *) echo "usage: $0 {deploy|start|verify|status|stop}" >&2; exit 1 ;;
esac

# This entry point always targets the local TEST stack.
export ROBINGRAPH_DEPLOY_TARGET=test
sh "$ROOT_DIR/scripts/deploy_nas.sh" preflight
env_value() {
  awk -v key="$1" 'index($0, key "=") == 1 { value=substr($0, length(key)+2) } END { print value }' "$TEST_ENV"
}
export ROBINGRAPH_COMPOSE_PROJECT=robingraph-test
export ROBINGRAPH_API_CONTAINER=robingraph-api-test
export ROBINGRAPH_ENV_FILE="$TEST_ENV"
ROBINGRAPH_API_MODE=$(env_value ROBINGRAPH_API_MODE)
ROBINGRAPH_API_MODE=${ROBINGRAPH_API_MODE:-serve-fixture}
ROBINGRAPH_IMAGE=$(env_value ROBINGRAPH_IMAGE)
ROBINGRAPH_EDGE_NETWORK=$(env_value ROBINGRAPH_EDGE_NETWORK)
ROBINGRAPH_EDGE_NETWORK=${ROBINGRAPH_EDGE_NETWORK:-robingraph-edge}
export ROBINGRAPH_API_MODE ROBINGRAPH_IMAGE ROBINGRAPH_EDGE_NETWORK
compose() {
  docker compose --env-file "$TEST_ENV" -f "$ROOT_DIR/compose.nas.yml" -f "$ROOT_DIR/compose.local-test.yml" "$@"
}
case "$ACTION" in
  deploy)
    sh "$ROOT_DIR/scripts/deploy_nas.sh" build
    compose up -d --no-build api
    ;;
  start) compose up -d --no-build api ;;
  verify) sh "$ROOT_DIR/scripts/deploy_nas.sh" verify ;;
  status) compose ps api ;;
  stop) compose stop api ;;
esac
