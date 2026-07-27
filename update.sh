#!/bin/zsh
# Daily IPO data refresh for IPO Ledger
set -euo pipefail

ROOT="/Users/williamon9/Library/CloudStorage/GoogleDrive-truckdriver@gmail.com/My Drive/PROJECTS/appDev/ipo"
LOG_DIR="$ROOT/logs"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
LOG_FILE="$LOG_DIR/update-$(date '+%Y-%m-%d').log"

mkdir -p "$LOG_DIR"
cd "$ROOT"

{
  echo "===== IPO update start: $STAMP ====="
  echo "Running scrape_queue.py..."
  if "$PYTHON" scrape_queue.py; then
    echo "scrape_queue.py OK"
  else
    echo "scrape_queue.py FAILED (exit $?)"
  fi

  echo "Running scrape_calendar.py..."
  if "$PYTHON" scrape_calendar.py; then
    echo "scrape_calendar.py OK"
  else
    echo "scrape_calendar.py FAILED (exit $?)"
  fi

  echo "Running scrape.py..."
  if "$PYTHON" scrape.py; then
    echo "scrape.py OK"
  else
    echo "scrape.py FAILED (exit $?)"
  fi

  # Keep only last 14 daily logs
  ls -1t "$LOG_DIR"/update-*.log 2>/dev/null | tail -n +15 | while read -r old; do
    rm -f "$old"
  done

  echo "===== IPO update end: $(date '+%Y-%m-%d %H:%M:%S') ====="
  echo
} >>"$LOG_FILE" 2>&1
