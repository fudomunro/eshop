#!/bin/sh
set -e

while true; do
  echo "$(date) - Starting review sync..."
  python review_sync.py "$@" || echo "$(date) - Sync failed, will retry next cycle"
  echo "$(date) - Sync complete, sleeping 1 hour..."
  sleep 3600
done
