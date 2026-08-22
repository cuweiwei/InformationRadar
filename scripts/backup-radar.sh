#!/bin/sh
set -eu

APP_DIR="${RADAR_APP_DIR:-/volume1/docker/information-radar}"
DOCKER_BIN="${RADAR_DOCKER_BIN:-/usr/local/bin/docker}"
docker_cmd() { if [ "${RADAR_USE_SUDO:-1}" = "1" ]; then sudo "$DOCKER_BIN" "$@"; else "$DOCKER_BIN" "$@"; fi; }
STAMP="$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$APP_DIR/backups/daily" "$APP_DIR/backups/weekly" "$APP_DIR/backups/monthly"
cd "$APP_DIR"
[ -f image.env ] && . ./image.env
export RADAR_IMAGE
docker_cmd compose run --rm --no-deps radar-web radar backup "/app/backups/daily/radar-$STAMP.db"
if [ "$(date +%u)" = "7" ]; then
  cp "$APP_DIR/backups/daily/radar-$STAMP.db" "$APP_DIR/backups/weekly/radar-$STAMP.db"
fi
if [ "$(date +%d)" = "01" ]; then
  cp "$APP_DIR/backups/daily/radar-$STAMP.db" "$APP_DIR/backups/monthly/radar-$STAMP.db"
fi
find "$APP_DIR/backups/daily" -type f -name 'radar-*.db' -mtime +14 -delete
find "$APP_DIR/backups/weekly" -type f -name 'radar-*.db' -mtime +56 -delete
find "$APP_DIR/backups/monthly" -type f -name 'radar-*.db' -mtime +366 -delete
echo "backup: $APP_DIR/backups/daily/radar-$STAMP.db"
