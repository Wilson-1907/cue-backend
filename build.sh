#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input

# Free-tier Aiven: never pool during build; retry migrate if slots are briefly full
export DB_CONN_MAX_AGE=0

migrate_with_retry() {
  local attempt=1
  local max=12
  while [ "$attempt" -le "$max" ]; do
    echo "migrate attempt ${attempt}/${max}…"
    if python manage.py migrate --no-input --skip-checks; then
      return 0
    fi
    echo "migrate failed (likely DB slots). sleeping 20s…"
    sleep 20
    attempt=$((attempt + 1))
  done
  echo "migrate failed after ${max} attempts" >&2
  return 1
}

migrate_with_retry

# Best-effort: wipe/prune telemetry + ensure admin (never fail the build)
python manage.py prune_telemetry --wipe || true
python - <<'PY' || true
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from accounts.models import User
u, created = User.objects.get_or_create(
    username="cueAdmin",
    defaults={"email": "wkabucho4@gmail.com", "role": "ADMIN"},
)
u.email = "wkabucho4@gmail.com"
u.set_password("CueAdmin@2026")
u.is_staff = True
u.is_superuser = True
u.is_active = True
if hasattr(u, "role"):
    u.role = "ADMIN"
u.save()
print("admin ready", u.username, u.email, "created" if created else "updated")
PY
