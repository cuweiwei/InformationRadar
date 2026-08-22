#!/bin/sh
set -eu

APP_DIR="${RADAR_APP_DIR:-/volume1/docker/information-radar}"
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
docker compose --profile job run --rm radar-job
