#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CRON_MARKER="# instagram-cucumber-daily"
CRON_SCHEDULE=${CRON_SCHEDULE:-"00 16 * * *"}
CRON_LINE="$CRON_SCHEDULE $PROJECT_DIR/run_daily.sh >> $PROJECT_DIR/instagram-cron.log 2>&1 $CRON_MARKER"
TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE"' EXIT HUP INT TERM

(crontab -l 2>/dev/null || true) | grep -vF "$CRON_MARKER" > "$TEMP_FILE" || true
printf '%s\n' "$CRON_LINE" >> "$TEMP_FILE"
crontab "$TEMP_FILE"

printf 'Installed daily Instagram post cron: %s\n' "$CRON_LINE"
