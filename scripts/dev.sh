#!/usr/bin/env bash
# One-command dev launcher: detects this machine's current LAN IP, wires it
# into .env (it goes stale on a new Wi-Fi — see QOLLANMA.md), then starts
# backend (HTTPS, runserver_plus) and frontend (HTTPS, vite) together so
# both localhost and phone-over-LAN work.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

LAN_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
LAN_IP="${LAN_IP:-127.0.0.1}"
echo "Aniqlangan LAN IP: $LAN_IP"

# adhoc.crt/.key: regenerated every run so the cert's SAN always covers
# *this* run's LAN IP as a real iPAddress entry, not just "localhost".
# A cert that only names "localhost" fails hostname validation the moment
# it's opened via the LAN IP — Chrome still offers an Advanced -> Proceed
# bypass for that, but iOS Safari often shows no bypass at all and just
# fails to load (blank page, no warning). Both servers share this one
# cert (see vite.config.js) so phone and desktop see the same identity.
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout adhoc.key -out adhoc.crt \
  -subj "/CN=$LAN_IP" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:$LAN_IP" \
  >/dev/null 2>&1

# .env: DEV_LAN_HOST + CORS_ALLOWED_ORIGINS
if grep -q "^DEV_LAN_HOST=" .env; then
  sed -i "s|^DEV_LAN_HOST=.*|DEV_LAN_HOST=$LAN_IP|" .env
else
  echo "DEV_LAN_HOST=$LAN_IP" >> .env
fi
sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://localhost:5173,http://$LAN_IP:5173,https://localhost:5173,https://$LAN_IP:5173|" .env

# No frontend/.env.local write here on purpose: the frontend now targets
# whatever hostname the page itself was opened with (see api/client.js),
# so https://localhost:5173 and https://$LAN_IP:5173 both work without a
# hardcoded VITE_API_URL — which would only ever match one of them and
# silently break the (SameSite=Strict) session cookie on the other, since
# browsers treat "localhost" and a LAN IP as different sites.
rm -f frontend/.env.local

# Free the ports if a previous run is still holding them.
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 5173/tcp 2>/dev/null || true
sleep 1

cleanup() {
  echo ""
  echo "To'xtatilmoqda..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

.venv/bin/python manage.py runserver_plus 0.0.0.0:8000 --cert-file adhoc.crt --key-file adhoc.key &
BACKEND_PID=$!

(cd frontend && npm run dev -- --host 0.0.0.0) &
FRONTEND_PID=$!

sleep 3
echo ""
echo "=================================================="
echo " Kompyuterdan:  https://localhost:5173"
echo " Telefondan:    https://$LAN_IP:5173"
echo " (Telefonda avval https://$LAN_IP:8000 ni ochib sertifikatni qabul qiling)"
echo "=================================================="
echo ""
echo "To'xtatish uchun: Ctrl+C"

wait
