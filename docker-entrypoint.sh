#!/bin/sh
set -e

python manage.py migrate --noinput

# Demo data only when explicitly asked for (SEED_DEMO=true in .env). A real
# server must not ship a shop with a publicly known password.
case "$(echo "${SEED_DEMO:-false}" | tr '[:upper:]' '[:lower:]')" in
  true|1|yes) python manage.py seed_demo ;;
esac

exec "$@"
