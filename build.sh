#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
# NOTE: migrate/wipe run at *start* (see start.sh), not here.
# Build-time migrate fails when the live Render process already holds
# all free-tier Aiven connection slots.
