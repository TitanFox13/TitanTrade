#!/usr/bin/env bash
# Off-server copy of the latest state archive (Decision 071): pulls it from titanserver over ssh with the
# base64 pipe (scp fails there) into a local, git-ignored folder. Run at every checkup from any machine with
# the `titanserver` ssh alias:  scripts/pull_backup.sh [dest]   (default ../backups next to the checkout)
set -euo pipefail
DEST="${1:-$(cd "$(dirname "$0")/../.." && pwd)/backups}"
mkdir -p "$DEST"
LATEST="$(ssh titanserver 'ls -1t /home/TitanTrade/backups/titantrade-state-*.tar.gz | head -1' 2>/dev/null | tail -1)"
[ -n "$LATEST" ] || { echo "no archive on titanserver"; exit 1; }
OUT="$DEST/$(basename "$LATEST")"
ssh titanserver "base64 -w0 '$LATEST'" 2>/dev/null | tail -1 | base64 -d > "$OUT"
tar tzf "$OUT" > /dev/null
echo "$(date -u +%FT%TZ) pulled $OUT ($(du -h "$OUT" | cut -f1)); $(ls -1 "$DEST"/titantrade-state-*.tar.gz | wc -l) local copies"
