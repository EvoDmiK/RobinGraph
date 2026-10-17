#!/bin/sh
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE="$BASE/current"
TEST_ENV="$RELEASE/.env.nas.test"
value() { awk -v key="$1" 'index($0,key "=")==1 {v=substr($0,length(key)+2)} END {print v}' "$TEST_ENV"; }
export ROBINGRAPH_DEPLOY_TARGET=test ROBINGRAPH_COMPOSE_PROJECT=robingraph-test ROBINGRAPH_API_CONTAINER=robingraph-api-test
export ROBINGRAPH_ENV_FILE="$TEST_ENV"
ROBINGRAPH_API_MODE=$(value ROBINGRAPH_API_MODE)
ROBINGRAPH_IMAGE=$(value ROBINGRAPH_IMAGE)
ROBINGRAPH_EDGE_NETWORK=$(value ROBINGRAPH_EDGE_NETWORK)
ROBINGRAPH_VCS_REF=$(value ROBINGRAPH_VCS_REF)
export ROBINGRAPH_API_MODE ROBINGRAPH_IMAGE ROBINGRAPH_EDGE_NETWORK ROBINGRAPH_VCS_REF
case "${1:-}" in
 start) set -- up -d --no-build api ;;
 status) set -- ps api ;;
 stop) set -- stop api ;;
 verify) exec docker --context orbstack exec robingraph-api-test python scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json ;;
 *) echo "usage: $0 {start|status|stop|verify}" >&2;exit 1 ;;
esac
exec docker --context orbstack compose --env-file "$TEST_ENV" -f "$RELEASE/compose.nas.yml" -f "$RELEASE/compose.mac-test.yml" "$@"
