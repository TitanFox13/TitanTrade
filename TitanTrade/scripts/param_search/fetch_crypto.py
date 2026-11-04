"""Daily crypto closes from two exchanges' public candle APIs (key-free; Decisions 095 / 096 research, 2026-11-04).

Default: BTC-USD, ETH-USD, LTC-USD from Coinbase Exchange (the Decision 095 probe). ``--all``: **every USD pair Coinbase
has ever listed** (online and delisted — the delisted ones still serve their candles, so the universe is point-in-time
on that venue; the coins that never listed there are still missing) into ``external/coinbase/``, and **every USDT pair
on Binance** (trading and halted, daily klines from 2017-08) into ``external/binance/`` — the second universe for the
consensus check. UTC days; Coinbase 300 candles per request, Binance 1,000. CSV: date,open,high,low,close,volume,
usd_volume (Coinbase's usd_volume = base volume × close; Binance's is the quote volume). Manifest entries per file like
the rest of the library (Decision 072); a pair that returns nothing is recorded as not ok. Three workers by default (`--workers=N`; Coinbase throttles six), a
back-off on 429; a re-run skips what was fetched today.
Run from TitanTrade/: uv run python -I scripts/param_search/fetch_crypto.py [--all] [--venue=coinbase|binance] [--workers=N]
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_external import ROOT, UA  # noqa: E402

PRODUCTS = ("BTC-USD", "ETH-USD", "LTC-USD")
CB = "https://api.exchange.coinbase.com"
BN = "https://api.binance.com/api/v3"


def get(url, tries=6):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == tries - 1:
                raise
            time.sleep(2.0 * (attempt + 1))   # Coinbase's public limit is ~10 requests/s per IP; back off and retry


def coinbase(product):
    rows = {}; day = dt.date(2015, 1, 1); today = dt.datetime.now(dt.timezone.utc).date()
    while day < today:
        end = min(day + dt.timedelta(days=290), today + dt.timedelta(days=1))
        for t, lo, hi, op, cl, vol in get(f"{CB}/products/{product}/candles?granularity=86400&start={day}T00:00:00Z&end={end}T00:00:00Z"):
            rows[dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()] = (op, hi, lo, cl, vol, vol * cl)
        day = end; time.sleep(0.12)
    return rows


def binance(symbol):
    rows = {}; start = int(dt.datetime(2017, 8, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    while True:
        k = get(f"{BN}/klines?symbol={symbol}&interval=1d&startTime={start}&limit=1000")
        for t, op, hi, lo, cl, vol, _, qvol, *_ in k:
            rows[dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).date().isoformat()] = (float(op), float(hi), float(lo), float(cl), float(vol), float(qvol))
        if len(k) < 1000:
            return rows
        start = k[-1][0] + 86_400_000; time.sleep(0.12)


def write(venue, name, rows, url):
    os.makedirs(f"{ROOT}/{venue}", exist_ok=True); dest = f"{ROOT}/{venue}/{name}.csv"; days = sorted(rows)
    with open(dest, "w") as f:
        f.write("date,open,high,low,close,volume,usd_volume\n")
        for d in days:
            f.write(d + "," + ",".join(f"{x:.10g}" for x in rows[d]) + "\n")
    n = os.path.getsize(dest); span = (days[0], days[-1], len(days)) if days else None
    return f"{venue}/{name}.csv", {"url": url, "ok": bool(days), "bytes": n, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(), "span": span}


def fetch_one(venue, name):
    if venue == "coinbase":
        return write("coinbase", name, coinbase(name), f"{CB}/products/{name}/candles?granularity=86400")
    return write("binance", name, binance(name), f"{BN}/klines?symbol={name}&interval=1d")


def main():
    mpath = f"{ROOT}/manifest.json"; manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    all_ = "--all" in sys.argv; venue = next((a.split("=")[1] for a in sys.argv if a.startswith("--venue=")), None); today = dt.date.today().isoformat()
    tasks = []
    if venue in (None, "coinbase"):
        tasks += [("coinbase", p) for p in (sorted(p["id"] for p in get(f"{CB}/products") if p["quote_currency"] == "USD") if all_ else PRODUCTS)]
    if all_ and venue in (None, "binance"):
        tasks += [("binance", s["symbol"]) for s in get(f"{BN}/exchangeInfo")["symbols"] if s["quoteAsset"] == "USDT"]
    tasks = [(v, n) for v, n in tasks if not (manifest.get(f"{v}/{n}.csv", {}).get("fetched_at", "")[:10] == today and manifest[f"{v}/{n}.csv"].get("ok"))]
    print(f"{len(tasks)} pairs to fetch (the rest fetched today)", flush=True)
    workers = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--workers=")), 3))
    with ThreadPoolExecutor(max_workers=workers) as pool:   # 3 stays under Coinbase's ~10 requests/s; Binance tolerates 6
        futures = {pool.submit(fetch_one, v, n): (v, n) for v, n in tasks}
        for i, f in enumerate(as_completed(futures)):
            v, n = futures[f]
            try:
                key, entry = f.result(); manifest[key] = entry; print(f"ok  {key} {entry['span']}  [{i + 1}/{len(tasks)}]", flush=True)
            except Exception as exc:  # noqa: BLE001
                manifest[f"{v}/{n}.csv"] = {"url": f"{v}:{n}", "ok": False, "error": str(exc)[:160]}; print(f"FAIL {v}/{n} {exc}", flush=True)
            if i % 50 == 49:
                json.dump(manifest, open(mpath, "w"), indent=1)
    json.dump(manifest, open(mpath, "w"), indent=1)


if __name__ == "__main__":
    main()
