#!/usr/bin/env bash
set -o errexit
export DB_CONN_MAX_AGE="${DB_CONN_MAX_AGE:-0}"

echo "Waiting briefly for old instance DB slots to release…"
sleep 8

migrate_with_retry() {
  local attempt=1
  local max=15
  while [ "$attempt" -le "$max" ]; do
    echo "migrate attempt ${attempt}/${max}…"
    if python manage.py migrate --no-input --skip-checks; then
      return 0
    fi
    echo "migrate failed (DB busy). sleeping 15s…"
    sleep 15
    attempt=$((attempt + 1))
  done
  echo "WARNING: migrate did not succeed; starting anyway" >&2
  return 0
}

migrate_with_retry

# Delete telemetry bulk; keep users/devices. Best-effort.
python manage.py prune_telemetry --wipe || true

python - <<'PY' || true
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from accounts.models import User
u, _ = User.objects.get_or_create(
    username="cueAdmin",
    defaults={"email": "wkabucho4@gmail.com", "role": User.Role.ADMIN},
)
u.email = "wkabucho4@gmail.com"
u.set_password("CueAdmin@2026")
u.is_staff = True
u.is_superuser = True
u.is_active = True
u.role = User.Role.ADMIN
u.save()
print("admin ready", u.username, u.email)
PY

exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
