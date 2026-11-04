"""Daily crypto closes from Coinbase Exchange's public candles API (key-free; Decision 095 research, 2026-11-04).

BTC-USD (candles from 2015-07-20), ETH-USD (2016-05-18) and LTC-USD (2016-08) — the three coins Coinbase listed by
the decade window's start, the only hindsight-free basket. UTC days, 300 candles per request → fetched in chunks,
written as CSV (date,open,high,low,close,volume) under ``external/coinbase/`` with manifest entries like the rest of
the library (Decision 072). Re-run to refresh; files are overwritten.
Run from TitanTrade/: uv run python -I scripts/param_search/fetch_crypto.py
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_external import ROOT, UA  # noqa: E402

PRODUCTS = ("BTC-USD", "ETH-USD", "LTC-USD")
API = "https://api.exchange.coinbase.com/products/{}/candles?granularity=86400&start={}T00:00:00Z&end={}T00:00:00Z"


def candles(product):
    rows = {}; day = dt.date(2015, 1, 1); today = dt.datetime.now(dt.timezone.utc).date()
    while day < today:
        end = min(day + dt.timedelta(days=290), today + dt.timedelta(days=1))
        req = urllib.request.Request(API.format(product, day, end), headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            for t, lo, hi, op, cl, vol in json.load(r):   # newest first: [time, low, high, open, close, volume]
                rows[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()] = (op, hi, lo, cl, vol)
        day = end; time.sleep(0.3)
    return rows


def main():
    os.makedirs(f"{ROOT}/coinbase", exist_ok=True); mpath = f"{ROOT}/manifest.json"
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for p in PRODUCTS:
        rows = candles(p); dest = f"{ROOT}/coinbase/{p}.csv"; days = sorted(rows)
        with open(dest, "w") as f:
            f.write("date,open,high,low,close,volume\n")
            for d in days:
                f.write(d + "," + ",".join(str(x) for x in rows[d]) + "\n")
        n = os.path.getsize(dest); span = (days[0], days[-1], len(days)) if days else None
        manifest[f"coinbase/{p}.csv"] = {"url": API.format(p, "2015-01-01", "today"), "ok": n > 0, "bytes": n, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "span": span}
        print(f"ok  coinbase/{p}.csv {n:>9,} B  {span}")
    json.dump(manifest, open(mpath, "w"), indent=1)


if __name__ == "__main__":
    main()
