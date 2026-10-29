#!/usr/bin/env bash
# Daily snapshot of state/ (trade log, plan, strategy, ledger, cooldowns, peak) and data/watchlist.json.
# Runs from the host on titanserver (cron, 21:30 UTC — after the 20:30 UTC daily summary):
#   30 21 * * * /home/TitanTrade/TitanTrade/scripts/backup_state.sh >> /home/TitanTrade/backups/backup.log 2>&1
# Keeps the last 30 archives. Restore: tar xzf <archive> -C <checkout>/TitanTrade (Decision 071).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/home/TitanTrade/backups}"
mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%d-%H%M)"
OUT="$DEST/titantrade-state-$STAMP.tar.gz"
tar czf "$OUT" -C "$ROOT" state data/watchlist.json
ls -1t "$DEST"/titantrade-state-*.tar.gz | tail -n +31 | xargs -r rm --
echo "$(date -u +%FT%TZ) backup $OUT ($(du -h "$OUT" | cut -f1)), $(ls -1 "$DEST"/titantrade-state-*.tar.gz | wc -l) kept"
