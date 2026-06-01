#!/usr/bin/env sh
set -eu

python -m app.db.bootstrap
export APP_BOOTSTRAPPED=1

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
