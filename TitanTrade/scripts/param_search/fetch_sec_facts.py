"""Fetch each universe name's XBRL facts from the SEC (free, point-in-time by filing date) for qualpick.py.

One GET per company on ``data.sec.gov/api/xbrl/companyfacts/CIK##########.json`` (the SEC's fair-access policy: a
User-Agent with a contact and no more than ten requests a second — this script sends about six), after the ticker →
CIK map from ``www.sec.gov/files/company_tickers.json`` (current tickers only: a delisted or renamed ticker that does
not map is reported and skipped). Keeps only the tags qualpick needs, every row with its period end, value, fiscal
year / period, form and filing date, into ``data/param_search/external/sec_facts/<TICKER>.json``; a manifest lists the
mapped and unmapped tickers. Re-running skips files that exist.
Run from TitanTrade/: uv run python -I scripts/param_search/fetch_sec_facts.py [--universe <json list>]
"""
import json
import os
import sys
import time
import urllib.request

S = os.environ.get("PARAM_SEARCH_DATA", "data/param_search")
OUT = f"{S}/external/sec_facts"
UA = {"User-Agent": "TitanTrade research jan.hendrych@ampulse-energy.com", "Accept-Encoding": "gzip, deflate"}
TAGS = {"us-gaap": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenuesNetOfInterestExpense",
                    "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices", "CostOfGoodsAndServicesSoldExcludingDepreciationDepletionAndAmortization",
                    "SellingGeneralAndAdministrativeExpense", "InterestExpense", "InterestExpenseNonoperating", "OperatingIncomeLoss", "GrossProfit",
                    "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "Assets", "NetIncomeLoss"],
        "dei": ["EntityCommonStockSharesOutstanding"]}
KEEP = ("end", "val", "fy", "fp", "form", "filed", "start")


def get(url):
    import gzip
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw)


def main():
    uni = json.load(open(sys.argv[sys.argv.index("--universe") + 1] if "--universe" in sys.argv else f"{S}/universes/sp500_union_2016_2026.json"))
    os.makedirs(OUT, exist_ok=True)
    tick = get("https://www.sec.gov/files/company_tickers.json")
    cik = {v["ticker"].upper(): int(v["cik_str"]) for v in tick.values()}
    alt = {t.replace(".", "-"): c for t, c in cik.items()}
    mapped, unmapped, failed = {}, [], []
    for s in uni:
        c = cik.get(s) or alt.get(s) or cik.get(s.replace("-", "."))
        if c is None:
            unmapped.append(s); continue
        mapped[s] = c
        path = f"{OUT}/{s}.json"
        if os.path.exists(path):
            continue
        try:
            d = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json")
        except Exception as e:  # noqa: BLE001 — a missing filer (404) is data, not a crash
            failed.append((s, str(e)[:80])); time.sleep(0.2); continue
        facts = {}
        for ns, tags in TAGS.items():
            for tag in tags:
                node = d.get("facts", {}).get(ns, {}).get(tag)
                if not node:
                    continue
                unit = "USD" if "USD" in node["units"] else next(iter(node["units"]))
                facts[tag] = [{k: r.get(k) for k in KEEP} for r in node["units"][unit] if r.get("form") in ("10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "40-F")]
        json.dump({"ticker": s, "cik": c, "name": d.get("entityName"), "facts": facts}, open(path, "w"))
        print(f"{s}: {d.get('entityName')} — {len(facts)} tags", file=sys.stderr)
        time.sleep(0.17)
    json.dump({"mapped": mapped, "unmapped": unmapped, "failed": failed, "fetched_at": time.strftime("%Y-%m-%d")}, open(f"{OUT}/manifest.json", "w"), indent=1)
    print(f"mapped {len(mapped)} / {len(uni)}; unmapped {len(unmapped)}: {unmapped}; failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
