#!/usr/bin/env bash
# One-command project launcher for handing the project in: builds and
# starts db + backend + frontend with Docker Compose. If .env is missing
# (a fresh clone), generates one from .env.example with random secrets so
# nothing needs manual editing first.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ ! -f .env ]; then
  echo ".env topilmadi — .env.example asosida avtomatik yaratilmoqda..."
  cp .env.example .env

  rand() { python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(${1:-24})))"; }

  SECRET_KEY="$(rand 50)"
  POSTGRES_PASSWORD="$(rand 20)"

  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://my_market_user:${POSTGRES_PASSWORD}@localhost:5433/my_market_db|" .env

  # No TLS-terminating proxy sits in front of gunicorn in this compose
  # setup, so the prod-default HTTPS redirect would break every request.
  if grep -q "^SECURE_SSL_REDIRECT=" .env; then
    sed -i "s|^SECURE_SSL_REDIRECT=.*|SECURE_SSL_REDIRECT=False|" .env
  else
    echo "SECURE_SSL_REDIRECT=False" >> .env
  fi

  # Demo launcher: create the demo shop (phone +998900000001, password
  # demo12345) with 10 products so there is something to log into.
  echo "SEED_DEMO=True" >> .env
fi

echo "Quyidagilar ishga tushirilmoqda: PostgreSQL, backend (Django) va frontend (Vue)..."
echo "Tayyor bo'lgach oching: http://localhost:${WEB_PORT:-8080}  (demo: +998900000001 / demo12345)"
docker compose up --build
