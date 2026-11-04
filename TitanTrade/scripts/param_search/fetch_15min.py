"""Alpaca 15-minute bars (SIP, split- and dividend-adjusted) 2016 → for SPY, SPMO, the 11 sector ETFs and the 15 shadow
names — **run on titanserver** with the project's keys (the research machine has no broker .env), then carried to the
research machine with the base64 trick (`ssh titanserver 'tar czf - -C … alpaca_15min | base64 -w0' | tail -1 |
base64 -d | tar xzf -`; the server's login shell prints, which breaks scp). Decision 100 (execution timing). Output:
one JSON per symbol under the given directory, all bars the feed returns (extended hours included — the readers keep
09:30–16:00 ET), fields t, o, h, l, c, v; ~65,000 regular-session bars per symbol, 10,000 per page, sequential with
a pause (about twenty minutes for all 28 — give it a worker pool next time). The library's manifest entries are
written by hand after the copy (see Decision 100).
Run on the server: set -a; . /home/TitanTrade/TitanTrade/.env; set +a; python3 fetch_15min.py <out_dir> [SYM …]
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

KEY = os.environ.get("ALPACA_PAPER_KEY") or os.environ.get("ALPACA_KEY"); SEC = os.environ.get("ALPACA_PAPER_SECRET") or os.environ.get("ALPACA_SECRET")
ETFS = ["SPY", "SPMO", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
NAMES = ["CRWD", "ANET", "LLY", "DXCM", "HCA", "JPM", "GS", "DVN", "WMT", "URI", "GE", "DASH", "DECK", "FCX", "EQIX"]


def fetch(sym, end):
    bars = []; token = None; pages = 0
    while True:
        q = {"timeframe": "15Min", "start": "2016-01-04T00:00:00Z", "end": end, "limit": 10000, "feed": "sip", "adjustment": "all"}
        if token:
            q["page_token"] = token
        req = urllib.request.Request(f"https://data.alpaca.markets/v2/stocks/{sym}/bars?{urllib.parse.urlencode(q)}", headers={"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SEC})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    d = json.load(r)
                break
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == 4:
                    raise
                time.sleep(3 * (attempt + 1))
        bars += d.get("bars") or []; pages += 1; token = d.get("next_page_token")
        if not token:
            return bars, pages
        time.sleep(0.35)


def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True); syms = sys.argv[2:] or ETFS + NAMES
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")   # SIP: end ≥ 15 minutes ago
    for sym in syms:
        bars, pages = fetch(sym, end); json.dump(bars, open(f"{out}/{sym}.json", "w"))
        print(f"ok {sym} {len(bars)} bars, {pages} pages, {bars[0]['t'] if bars else None} → {bars[-1]['t'] if bars else None}", flush=True)


if __name__ == "__main__":
    main()
