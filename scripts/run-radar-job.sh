#!/bin/sh
set -eu

APP_DIR="${RADAR_APP_DIR:-/volume1/docker/information-radar}"
DOCKER_BIN="${RADAR_DOCKER_BIN:-/usr/local/bin/docker}"
docker_cmd() { if [ "${RADAR_USE_SUDO:-1}" = "1" ]; then sudo env RADAR_IMAGE="${RADAR_IMAGE:-}" "$DOCKER_BIN" "$@"; else "$DOCKER_BIN" "$@"; fi; }
LOCK_DIR="$APP_DIR/run/job.lock"
mkdir -p "$APP_DIR/run"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "radar job already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

cd "$APP_DIR"
[ -f image.env ] && . ./image.env
export RADAR_IMAGE
docker_cmd compose --profile job run --rm radar-job
