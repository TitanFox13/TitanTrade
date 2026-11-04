"""The keyed free sources (roadmap Track H → B10 / B11, 2026-11-04): Tiingo's adjusted daily history 1990 → for the
book's symbols, and Alpha Vantage's historical earnings dates for the 15 names. Keys come from the environment or
TitanTrade/.env (git-ignored): TIINGO_API_KEY, ALPHAVANTAGE_API_KEY. Writes external/tiingo/<SYM>.json (the raw rows:
date, close, adjClose, divCash, splitFactor …) and external/alphavantage/<SYM>_earnings.json, and records each in
external/manifest.json like fetch_external.py. Free limits: Tiingo 50 symbols / hour, 1,000 requests / day; Alpha
Vantage 25 requests / day — so the earnings set takes two days; the script skips what is already on disk.
Run from TitanTrade/: uv run python -I scripts/param_search/fetch_keyed.py [--tiingo] [--earnings] [--force]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = "data/param_search/external"
SECT = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLB", "XLRE", "XLP", "XLU", "XLC"]
NAMES = ["CRWD", "ANET", "LLY", "DXCM", "HCA", "JPM", "GS", "DVN", "WMT", "URI", "GE", "DASH", "DECK", "FCX", "EQIX"]
TIINGO_SYMBOLS = ["SPY", "SPMO", "MTUM", "QQQ", "IWM", "SHY", "IEF", "TLT", "GLD", "BIL", "SVXY", "XIV", "VXX"] + SECT + NAMES   # SVXY / XIV / VXX: the short- and long-VIX products, Decision 098
UA = "TitanTrade research (contact via the repository)"


def keys():
    env = dict(os.environ)
    if os.path.exists(".env"):
        for line in open(".env"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1); env.setdefault(k, v)
    return env.get("TIINGO_API_KEY"), env.get("ALPHAVANTAGE_API_KEY")


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def record(manifest, key, url, data, span):
    manifest[key] = {"url": url, "ok": True, "bytes": len(data), "fetched_at": datetime.now(timezone.utc).isoformat(), "span": span}


def tiingo(token, manifest, force):
    os.makedirs(f"{ROOT}/tiingo", exist_ok=True)
    for sym in TIINGO_SYMBOLS:
        dest = f"{ROOT}/tiingo/{sym}.json"
        if os.path.exists(dest) and not force:
            continue
        url = f"https://api.tiingo.com/tiingo/daily/{sym}/prices?startDate=1990-01-01&format=json"
        try:
            data = get(url, {"Authorization": f"Token {token}"})
            rows = json.loads(data)
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"unexpected payload: {data[:120]!r}")
            open(dest, "wb").write(data)
            span = [rows[0]["date"][:10], rows[-1]["date"][:10], len(rows)]
            record(manifest, f"tiingo/{sym}.json", url, data, span)
            print(f"ok   tiingo {sym:5} {span}", flush=True)
        except Exception as exc:  # noqa: BLE001
            manifest[f"tiingo/{sym}.json"] = {"url": url, "ok": False, "error": str(exc)[:160], "fetched_at": datetime.now(timezone.utc).isoformat()}
            print(f"FAIL tiingo {sym:5} {str(exc)[:120]}", flush=True)
        time.sleep(1.5)


def earnings(key, manifest, force, budget=24):
    os.makedirs(f"{ROOT}/alphavantage", exist_ok=True)
    done = 0
    for sym in NAMES:
        dest = f"{ROOT}/alphavantage/{sym}_earnings.json"
        if os.path.exists(dest) and not force:
            continue
        if done >= budget:
            print(f"stop: the day's budget of {budget} requests is used; run again tomorrow", flush=True)
            return
        url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode({"function": "EARNINGS", "symbol": sym, "apikey": key})
        try:
            data = get(url); doc = json.loads(data); q = doc.get("quarterlyEarnings")
            if not q:
                raise ValueError(f"no quarterlyEarnings: {data[:160]!r}")
            open(dest, "wb").write(data)
            dates = sorted(x.get("reportedDate") or "" for x in q)
            record(manifest, f"alphavantage/{sym}_earnings.json", url.split("&apikey")[0], data, [dates[0], dates[-1], len(q)])
            print(f"ok   earnings {sym:5} {[dates[0], dates[-1], len(q)]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            manifest[f"alphavantage/{sym}_earnings.json"] = {"url": url.split("&apikey")[0], "ok": False, "error": str(exc)[:160], "fetched_at": datetime.now(timezone.utc).isoformat()}
            print(f"FAIL earnings {sym:5} {str(exc)[:120]}", flush=True)
        done += 1
        time.sleep(15)   # the free tier's per-minute limit


def main():
    t_key, a_key = keys()
    want_t = "--tiingo" in sys.argv or "--earnings" not in sys.argv
    want_e = "--earnings" in sys.argv or "--tiingo" not in sys.argv
    force = "--force" in sys.argv
    mpath = f"{ROOT}/manifest.json"
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    try:
        if want_t:
            if not t_key: print("no TIINGO_API_KEY"); return
            tiingo(t_key, manifest, force)
        if want_e:
            if not a_key: print("no ALPHAVANTAGE_API_KEY"); return
            earnings(a_key, manifest, force)
    finally:
        json.dump(manifest, open(mpath, "w"), indent=1)


if __name__ == "__main__":
    main()
