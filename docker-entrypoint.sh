#!/bin/sh
set -e

python manage.py migrate --noinput

# Demo data only when explicitly asked for (SEED_DEMO=true in .env). A real
# server must not ship a shop with a publicly known password.
case "$(echo "${SEED_DEMO:-false}" | tr '[:upper:]' '[:lower:]')" in
  true|1|yes) python manage.py seed_demo ;;
esac

# The operator login, created once from MARKET_ADMIN_PHONE/PASSWORD (see
# ensure_admin); skipped when they are unset. A bad value is reported but must
# not keep the shop itself from starting.
python manage.py ensure_admin --if-configured || echo "ensure_admin: admin yaratilmadi (yuqoridagi xabarga qarang)" >&2

exec "$@"
