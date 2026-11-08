#!/bin/bash
# Uses its own Compose project, unexposed app port and disposable database volume.
set -euo pipefail
cd "$(dirname "$0")/.."
fixture_project="pmescheck$(date +%s)$$"
export DB_PASSWORD="$(openssl rand -hex 32)"
export ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '/+' '_-')"
export PUBLIC_ORIGIN=http://localhost:8080
export OPENAI_API_KEY='' ANTHROPIC_API_KEY='' GEMINI_API_KEY=''
dc(){ docker compose --project-name "$fixture_project" "$@"; }
cleanup(){ dc down -v --remove-orphans >/dev/null; }
trap cleanup EXIT
dc build app
dc up -d db
dc run --rm -T app python -m server.migrate
dc run --rm -T app sh -eu -c '
 uvicorn server.app:app --host 127.0.0.1 --port 8080 --no-access-log &
 python -c "import time,httpx
for i in range(50):
 try:
  if httpx.get(\"http://localhost:8080/api/health\").is_success: break
 except httpx.TransportError: pass
 time.sleep(.25)
else: raise SystemExit(\"Backend readiness failed\")"
 python -m tests.smoke'
dc restart db
dc run --rm -T app python -c "from server.db import database
with database() as db:
 row=db.execute(\"SELECT count(*) AS n FROM sources WHERE title='Scope v2'\").fetchone()
 assert row['n']==1
 print('PASS: source persisted after app replacement and PostgreSQL restart.')"
