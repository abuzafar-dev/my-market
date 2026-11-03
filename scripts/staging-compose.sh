#!/bin/sh
# Every docker compose command for STAGING goes through this script, e.g.
#     scripts/staging-compose.sh config --quiet
#     scripts/staging-compose.sh up -d --build
#     scripts/staging-compose.sh logs --since 5m celery-beat
#
# Why: docker-compose.yml pins `name: my-market` for production. A plain
# `docker compose up` for staging that forgets the project name targets the
# PRODUCTION project — it would recreate production's containers and attach
# them to production's volumes. This script always passes
# `-p my-market-staging --env-file .env.staging`, and refuses to run unless the
# env file isolates everything that the project name alone does not
# (env_file of the app containers, the host port, the shared-proxy alias).
# It never prints a value from the env file. See docs/STAGING.md §0a.
set -eu

cd "$(dirname "$0")/.."

PROJECT=my-market-staging
ENV_FILE=${STAGING_ENV_FILE:-.env.staging}

die() {
    echo "staging-compose: $*" >&2
    exit 1
}

[ "$ENV_FILE" != ".env" ] || die "refusing to use .env (that is production's env file)"
[ -f "$ENV_FILE" ] || die "$ENV_FILE not found — create it from deploy/env.staging.example"

# Last assignment of KEY in the env file (no output to the terminal).
get() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | tr -d '"'"'"; }

[ "$(get COMPOSE_PROJECT_NAME)" = "$PROJECT" ] \
    || die "COMPOSE_PROJECT_NAME in $ENV_FILE must be $PROJECT"
[ "$(get APP_ENV_FILE)" = "$ENV_FILE" ] \
    || die "APP_ENV_FILE in $ENV_FILE must be $ENV_FILE (else the app containers load production's .env)"

port=$(get WEB_PORT)
[ -n "$port" ] || die "set WEB_PORT in $ENV_FILE (production uses 8080)"
[ "$port" != "8080" ] || die "WEB_PORT=8080 is production's port; use e.g. 8081"

case ":$(get COMPOSE_FILE):" in
    *shared-proxy*)
        alias=$(get PROXY_ALIAS)
        [ -n "$alias" ] && [ "$alias" != "my-market" ] \
            || die "with the shared proxy, PROXY_ALIAS must be set and differ from my-market"
        ;;
esac

! grep -qE '^[A-Z_]+=CHANGE-ME$' "$ENV_FILE" || die "$ENV_FILE still has CHANGE-ME placeholders"
[ -n "$(get SECRET_KEY)" ] || die "SECRET_KEY is empty in $ENV_FILE"
[ -n "$(get POSTGRES_PASSWORD)" ] || die "POSTGRES_PASSWORD is empty in $ENV_FILE"

exec docker compose -p "$PROJECT" --env-file "$ENV_FILE" "$@"
