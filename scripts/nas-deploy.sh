#!/bin/sh
set -eu

APP_DIR="${RADAR_APP_DIR:-/volume1/docker/information-radar}"
HOST_PORT="${RADAR_HOST_PORT:-8789}"
DOCKER_BIN="${RADAR_DOCKER_BIN:-/usr/local/bin/docker}"
docker_cmd() { if [ "${RADAR_USE_SUDO:-1}" = "1" ]; then sudo env RADAR_IMAGE="${RADAR_IMAGE:-}" "$DOCKER_BIN" "$@"; else "$DOCKER_BIN" "$@"; fi; }
NEW_IMAGE="${1:?usage: nas-deploy.sh ghcr.io/owner/information-radar@sha256:digest}"
cd "$APP_DIR"
mkdir -p data config logs backups run releases
sudo chown -R 10001:100 data logs backups
sudo chmod 770 data logs backups

if [ -f image.env ]; then
  cp image.env "releases/previous-image.env"
fi
printf 'RADAR_IMAGE=%s\n' "$NEW_IMAGE" > image.env.new
mv image.env.new image.env
. ./image.env
export RADAR_IMAGE

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
docker_cmd compose pull radar-web radar-job
docker_cmd compose run --rm --no-deps radar-web radar backup "/app/backups/pre-deploy-$STAMP.db"
docker_cmd compose up -d radar-web

READY=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:$HOST_PORT/health/ready" >"/tmp/information-radar-health.json"; then
    READY=1
    break
  fi
  sleep 3
done

if [ "$READY" -ne 1 ]; then
  echo "deployment failed: health check did not become ready" >&2
  if [ -f releases/previous-image.env ]; then
    cp releases/previous-image.env image.env
    . ./image.env
    export RADAR_IMAGE
    docker_cmd compose up -d radar-web
  fi
  exit 1
fi

docker_cmd compose ps
cat /tmp/information-radar-health.json
echo "DEPLOYMENT VERIFIED"
