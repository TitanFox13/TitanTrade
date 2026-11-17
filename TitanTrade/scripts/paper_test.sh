#!/usr/bin/env bash
# The paper account beside the live system (Decision 111): a drill step or a CLI command in a throw-away container
# with its own state/, data/ and logs/ under /home/TitanTrade/paper_test. Nothing of the live deployment is mounted,
# Discord is off, and the drill refuses to trade unless the mounted settings file says paper. Run on the server:
#   scripts/paper_test.sh init ['{"fractional_core": true}']   the live settings as a paper copy (+ overrides); the
#                                                              archived paper state the first time
#   scripts/paper_test.sh cli fetch                            a CLI command on the paper account
#   scripts/paper_test.sh drill STEP=status [NAME=… DIP=… SHOCK=…]   a scripts/paper_drill.py step
# PAPER_IMAGE=<tag> runs an image built from code that is not deployed (docker build -t titantrade-papertest <dir>).
set -euo pipefail
cd "$(dirname "$0")/.."
T=/home/TitanTrade/paper_test
IMG=${PAPER_IMAGE:-titantrade-titantrade}
RUN=(docker run --rm -i --env-file .env -e TRADING_MODE=paper -e DISCORD_WEBHOOK_URL= -v "$T/state:/app/state" -v "$T/data:/app/data" -v "$T/logs:/app/logs")
case "${1:-}" in
  init)
    mkdir -p "$T/state" "$T/logs"; rm -rf "$T/data"; cp -r data "$T/data"
    [ -e "$T/state/strategy.json" ] || cp state/archive/paper_2026-11-12/*.json state/sector_cache.json "$T/state/"
    python3 -c 'import json, sys
p = sys.argv[1]; w = json.load(open(p)); w["settings"]["trading_mode"] = "paper"; w["settings"]["mechanical"].update(json.loads(sys.argv[2]))
json.dump(w, open(p, "w"), indent=2); print("paper settings:", {k: w["settings"]["mechanical"].get(k) for k in json.loads(sys.argv[2])} or "as live")' "$T/data/watchlist.json" "${2:-{\}}"
    ;;
  cli) shift; "${RUN[@]}" "$IMG" "$@" ;;
  drill) shift; envs=(); for kv in "$@"; do envs+=(-e "$kv"); done
    "${RUN[@]}" "${envs[@]}" --entrypoint uv "$IMG" run python - < scripts/paper_drill.py ;;
  *) echo "usage: $0 init [json] | cli <command> | drill STEP=… [NAME=… DIP=… SHOCK=…]"; exit 2 ;;
esac
