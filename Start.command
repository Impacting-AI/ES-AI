#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Install Docker Desktop, open it, then run Start.command again."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Open Docker Desktop and wait for its engine to start."; exit 1; }
if [[ ! -e .env ]]; then
  umask 077
  (set -C
   printf 'DB_PASSWORD=%s\nENCRYPTION_KEY=%s\nPUBLIC_ORIGIN=http://localhost:8080\n'      "$(openssl rand -hex 32)" "$(openssl rand -base64 32 | tr '/+' '_-')" > .env)
fi
docker compose build
docker compose up -d db
docker compose run --rm -T app python -m server.migrate
admins=$(docker compose exec -T db psql -U pm -d pm -Atc "select count(*) from users where platform_role in ('Super Admin','CEO') and agent_access")
if [[ "$admins" == 0 ]]; then docker compose run --rm app python -m server.admin; fi
docker compose up -d app worker
for attempt in {1..45}; do
  if curl -fsS --max-time 2 http://localhost:8080/api/health 2>/dev/null | grep -q '"database":"ready"'; then
    echo "PM AI ES is ready at http://localhost:8080"
    if [[ "$(uname)" == Darwin ]]; then open http://localhost:8080; fi
    exit 0
  fi
  sleep 2
done
echo 'Readiness check failed. Run docker compose logs --tail 50 app db to diagnose.'
exit 1
