"""The external data library (Decision 072, 2026-10-29): everything beyond prices that the research could use, from
key-free sources, stored under ``data/param_search/external/<source>/`` with a manifest. Operator: "we have prices but
there is so much more that influences trading … find it, free first." Each source is fetched with a plain GET and a
User-Agent naming the project (the SEC requires one); a failure is recorded in the manifest, never retried blindly.
Re-run to refresh: files are overwritten, the manifest keeps the last status per item.
Run from TitanTrade/: uv run python -I scripts/param_search/fetch_external.py [--only cboe,fred,...] [--skip sec]
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

S = os.environ.get("PARAM_SEARCH_DATA", "data/param_search")
ROOT = f"{S}/external"
UA = "TitanTrade research (jan.hendrych@ampulse-energy.com)"
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
AQR = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"

SOURCES = {
    # Cboe index histories (daily, CSV): volatility, the option-writing benchmarks (the hindsight-free answer to "sell puts at the dip")
    "cboe": {f"{k}_History.csv": f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{k}_History.csv" for k in
             ("VIX", "VIX9D", "VIX3M", "VIX6M", "VVIX", "SKEW", "VXN", "VXD", "RVX", "OVX", "GVZ",
              "PUT", "BXM", "BXMD", "BXY", "CLL", "CNDR", "BFLY", "RXM", "PPUT", "WPUT", "CMBO", "BXMC")},
    # FRED (key-free CSV endpoint): rates, spreads, stress, macro, recession flags, a few indices
    "fred": {f"{k}.csv": f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={k}" for k in
             ("VIXCLS", "VXVCLS", "VXNCLS", "DGS1MO", "DTB3", "DGS2", "DGS10", "DGS30", "T10Y2Y", "T10Y3M", "DFF", "FEDFUNDS",
              "BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A0HYM2EY", "NFCI", "ANFCI", "STLFSI4", "USREC", "USRECD", "UNRATE", "ICSA",
              "BAA", "AAA", "DBAA", "DAAA", "BAA10Y", "AAA10Y", "TEDRATE",   # Moody's corporate yields and spreads (unrevised; monthly 1919 →, daily 1983 →) and the TED spread 1986–2022 — Decision 077
              "CPIAUCSL", "T5YIE", "T10YIE", "UMCSENT", "M2SL", "SP500", "NASDAQCOM", "DJIA", "DCOILWTICO", "DTWEXBGS",
              "GOLDAMGBD228NLBM", "DEXUSEU", "WALCL", "TOTRESNS", "RRPONTSYD")},
    # CFTC Commitments of Traders, legacy futures-only, one zip per year 1986 →
    "cftc": {f"deacot{y}.zip": f"https://www.cftc.gov/files/dea/history/deacot{y}.zip" for y in range(1986, 2027)},
    # Shiller: monthly S&P prices, dividends, earnings, CAPE, rates 1871 →
    "shiller": {"ie_data.xls": "http://www.econ.yale.edu/~shiller/data/ie_data.xls"},
    # AQR data library: factor premia over a century, time-series momentum, quality, betting against beta, value & momentum everywhere
    "aqr": {k: f"{AQR}{k}" for k in ("Century-of-Factor-Premia-Monthly.xlsx", "Time-Series-Momentum-Factors-Monthly.xlsx",
                                     "Quality-Minus-Junk-Factors-Daily.xlsx", "Betting-Against-Beta-Equity-Factors-Daily.xlsx",
                                     "Value-and-Momentum-Everywhere-Factors-Monthly.xlsx", "Momentum-Indices-Monthly.xlsx",
                                     "Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx", "The-Devil-in-HMLs-Details-Factors-Daily.xlsx")},
    # Kenneth French, the daily files we did not have: profitability, investment, size, variance, beta sorts, 5 factors, 10 industries
    "french": {k: f"{FRENCH}{k}" for k in ("F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "Portfolios_Formed_on_OP_Daily_CSV.zip",
                                           "Portfolios_Formed_on_INV_Daily_CSV.zip", "Portfolios_Formed_on_ME_Daily_CSV.zip",
                                           "Portfolios_Formed_on_VAR_Daily_CSV.zip", "Portfolios_Formed_on_RESVAR_Daily_CSV.zip",
                                           "25_Portfolios_ME_OP_5x5_Daily_CSV.zip", "25_Portfolios_ME_BM_5x5_Daily_CSV.zip",
                                           "10_Industry_Portfolios_Daily_CSV.zip", "30_Industry_Portfolios_Daily_CSV.zip",
                                           "Portfolios_Formed_on_BETA_CSV.zip", "Portfolios_Formed_on_ME_Prior_12_2_Daily_CSV.zip")},
    # Kenneth French international library (Track E of the roadmap): regional factors and momentum, daily where published
    "french_intl": {k: f"{FRENCH}{k}" for k in ("Developed_ex_US_3_Factors_Daily_CSV.zip", "Developed_ex_US_Mom_Factor_Daily_CSV.zip",
                                                "Europe_3_Factors_Daily_CSV.zip", "Europe_Mom_Factor_Daily_CSV.zip",
                                                "Japan_3_Factors_Daily_CSV.zip", "Japan_Mom_Factor_Daily_CSV.zip",
                                                "Asia_Pacific_ex_Japan_3_Factors_Daily_CSV.zip", "Asia_Pacific_ex_Japan_Mom_Factor_Daily_CSV.zip",
                                                "Emerging_5_Factors_CSV.zip", "Emerging_MOM_Factor_CSV.zip",
                                                "Developed_3_Factors_Daily_CSV.zip", "Developed_Mom_Factor_Daily_CSV.zip",
                                                "Europe_25_Portfolios_ME_Prior_12_2_Daily_CSV.zip", "Japan_25_Portfolios_ME_Prior_12_2_Daily_CSV.zip",
                                                "Developed_ex_US_25_Portfolios_ME_Prior_12_2_Daily_CSV.zip")},
    # NAAIM exposure index page (the xlsx link is parsed from it), datahub gold monthly 1833 →
    "misc": {"naaim_page.html": "https://naaim.org/programs/naaim-exposure-index/",
             "gold_monthly.csv": "https://datahub.io/core/gold-prices/r/monthly.csv",
             "finra_margin_page.html": "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics",
             "finra_margin_statistics.xlsx": "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"},
    # SEC financial statement data sets (quarterly zips, ~50–130 MB each, 2009q1 →): fetched on demand by the fundamentals project;
    # the two most recent quarters here as a format check. Fair-access policy: ≤ 10 requests/s, a User-Agent with contact.
    "sec": {f"{q}.zip": f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip" for q in ("2026q2", "2026q3")},
}


def get(url, dest, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def span(path):
    """First / last date of a CSV whose first column is a date (CBOE mm/dd/yyyy or FRED yyyy-mm-dd); None otherwise."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        rows = [ln.split(",")[0] for ln in lines[1:] if re.match(r"^\d{2}/\d{2}/\d{4}|^\d{4}-\d{2}-\d{2}", ln)]
        return (rows[0], rows[-1], len(rows)) if rows else None
    except Exception:  # noqa: BLE001
        return None


def main():
    only = next((a.split("=")[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    skip = next((a.split("=")[1].split(",") for a in sys.argv if a.startswith("--skip=")), [])
    os.makedirs(ROOT, exist_ok=True)
    mpath = f"{ROOT}/manifest.json"
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for source, items in SOURCES.items():
        if (only and source not in only) or source in skip:
            continue
        os.makedirs(f"{ROOT}/{source}", exist_ok=True)
        for name, url in items.items():
            dest = f"{ROOT}/{source}/{name}"; key = f"{source}/{name}"
            t0 = time.time()
            try:
                n = get(url, dest)
                head = open(dest, "rb").read(200)
                ok = n > 0 and not head.lstrip().lower().startswith(b"<!doctype html") and not head.lstrip().startswith(b"<?xml")
                if name.endswith((".html",)):
                    ok = n > 0
                entry = {"url": url, "ok": ok, "bytes": n, "fetched_at": datetime.now(timezone.utc).isoformat(), "span": span(dest) if ok and name.endswith(".csv") else None}
                if not ok:
                    entry["note"] = "HTML or XML returned instead of data (walled or moved)"
            except Exception as exc:  # noqa: BLE001
                entry = {"url": url, "ok": False, "error": str(exc)[:160], "fetched_at": datetime.now(timezone.utc).isoformat()}
                if os.path.exists(dest) and os.path.getsize(dest) == 0:
                    os.remove(dest)
            manifest[key] = entry
            print(f"{'ok ' if entry['ok'] else 'FAIL'} {key:60} {entry.get('bytes', 0):>11,} B {entry.get('span') or entry.get('error') or entry.get('note') or ''}  [{time.time() - t0:.1f}s]", flush=True)
            time.sleep(0.3 if source != "sec" else 1.0)
    # NAAIM: find the xlsx link on the page and fetch it
    page = f"{ROOT}/misc/naaim_page.html"
    if os.path.exists(page):
        m = re.search(r'href="([^"]+\.xlsx?)"', open(page, encoding="utf-8", errors="replace").read())
        if m:
            url = m.group(1); dest = f"{ROOT}/misc/naaim_exposure.xlsx"
            try:
                n = get(url, dest); manifest["misc/naaim_exposure.xlsx"] = {"url": url, "ok": n > 0, "bytes": n, "fetched_at": datetime.now(timezone.utc).isoformat()}
                print(f"ok  misc/naaim_exposure.xlsx {n:>11,} B  {url}")
            except Exception as exc:  # noqa: BLE001
                manifest["misc/naaim_exposure.xlsx"] = {"url": url, "ok": False, "error": str(exc)[:160]}; print(f"FAIL misc/naaim_exposure.xlsx {exc}")
    json.dump(manifest, open(mpath, "w"), indent=1)
    ok = sum(1 for v in manifest.values() if v.get("ok")); print(f"\nmanifest: {ok} ok / {len(manifest)} items → {mpath}")


if __name__ == "__main__":
    main()
