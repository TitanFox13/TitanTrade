"""The two-sleeve book in the package backtester (Decision 081): the momentum
leg holds its target and moves only outside the band, a slot is 10 % of equity
under design 070 and 25 % at momentum_weight 0, the shock trigger scales both
legs and pauses entries, exposure = min(insurance, shock) not the product, and
momentum_weight 0 is the old dip-only book. Synthetic bars, zero network."""
from datetime import date, timedelta

import pytest

from titantrade.backtest.mechanical import run_mechanical_backtest

LIVE = {"dip_pct": 0.08, "dip_lookback_days": 90, "trend_sma_days": 150, "slot_pct": 0.25, "max_slots": 3,
        "tp_pct": 0.20, "stop_pct": 0.12, "max_hold_days": 60, "momentum_weight": 0.6,
        "shock_drop_pct": 0.07, "shock_lookback_days": 10, "shock_hold_days": 20, "shock_scale": 0.5}


def _bars(closes, start=date(2016, 1, 4)):
    out, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"date": d.isoformat(), "open": c, "high": c, "low": c, "close": c, "volume": 1000})
        d += timedelta(days=1)
    return out


def _rise(n, step=0.002, base=100.0):
    return [base * (1 + step) ** i for i in range(n)]


def _dip_fixture():
    """A name that dips 12 % inside an uptrend and then recovers (the Decision 061 fixture)."""
    aaa = _rise(300, 0.003)
    aaa += [aaa[299] * (1 - 0.03 * k) for k in range(1, 5)]
    aaa += [aaa[-1] * (1 + 0.025 * k) for k in range(1, 9)]
    return aaa + [aaa[-1]] * (400 - len(aaa))


def test_momentum_leg_holds_its_target_and_moves_only_outside_the_band():
    flat = _bars([100.0] * 400)
    mom = _bars(_rise(400, 0.001))
    res = run_mechanical_backtest({"AAA": flat}, flat, None, LIVE, momentum_bars=mom)
    daily = run_mechanical_backtest({"AAA": flat}, flat, None, {**LIVE, "core_band_pct": 0.0}, momentum_bars=mom)
    assert 0.55 <= res["avg_momentum_share"] <= 0.63          # target 0.95 × 0.6 = 57 %, drifting inside the band
    assert 2 <= res["core_trades"]["momentum"] <= 4 < 100 < daily["core_trades"]["momentum"]
    assert res["metrics"]["trades"] == 0 and res["shock_days"] == 0


def test_slot_is_a_quarter_of_the_dip_sleeve():
    aaa, spy = _bars(_dip_fixture()), _bars(_rise(400, 0.0005))
    two = run_mechanical_backtest({"AAA": aaa}, spy, None, {**LIVE, "max_slots": 1}, momentum_bars=_bars([100.0] * 400))
    dip_only = run_mechanical_backtest({"AAA": aaa}, spy, None, {**LIVE, "max_slots": 1, "momentum_weight": 0.0})
    assert two["trades"][0]["size_pct"] == pytest.approx(0.10, abs=0.005)      # 25 % of the 40 % sleeve (design 070)
    assert dip_only["trades"][0]["size_pct"] == pytest.approx(0.25, abs=0.005)  # the Decision 061 slot


def _shock_fixture():
    """SPY falls 9.6 % in ten sessions after a long rise (stays above its 200-day SMA);
    AAA's dip signal exists only inside the shock hold and vanishes as it recovers."""
    spy = _rise(300)
    spy += [spy[-1] * 0.99 ** k for k in range(1, 11)]
    spy += [spy[-1]] * 90
    aaa = _rise(300)
    aaa += [aaa[-1] * 0.99 ** k for k in range(1, 11)]
    aaa += [aaa[-1] * 1.01 ** k for k in range(1, 91)]
    return _bars(aaa), _bars(spy)


def test_shock_trigger_scales_both_legs_and_pauses_entries():
    aaa, spy = _shock_fixture()
    mom = _bars([100.0] * 400)
    on = run_mechanical_backtest({"AAA": aaa}, spy, None, LIVE, momentum_bars=mom)
    off = run_mechanical_backtest({"AAA": aaa}, spy, None, {**LIVE, "shock_drop_pct": 0.0}, momentum_bars=mom)
    assert on["shock_days"] >= 20 and on["risk_off_days"] == 0
    assert 0.40 < on["min_exposure"] < 0.55       # 0.5 × 95 %: SPY 19 % + momentum 28.5 % — both legs halved
    assert on["metrics"]["trades"] == 0 and off["metrics"]["trades"] == 1   # the dip was only buyable while the shock was on


def test_exposure_is_the_min_of_the_two_rules_not_the_product():
    spy = _rise(300, 0.001)
    spy += [spy[-1] * 0.985 ** k for k in range(1, 11)]        # the shock: −14 % in ten sessions …
    spy += [spy[-1] * 0.997 ** k for k in range(1, 91)]        # … then a grind below the 200-day SMA (insurance)
    bars = _bars(spy)
    res = run_mechanical_backtest({"AAA": bars}, bars, {f"X{i}": bars for i in range(4)}, LIVE, momentum_bars=_bars([100.0] * 400))
    assert res["risk_off_days"] > 0 and res["shock_days"] > 0
    assert 0.40 < res["min_exposure"] < 0.55      # min(0.5, 0.5) × 95 % = 47.5 %, never 0.25 × 95 %


def test_momentum_weight_zero_is_the_dip_only_book():
    aaa, spy = _bars(_dip_fixture()), _bars(_rise(400, 0.0005))
    old = run_mechanical_backtest({"AAA": aaa}, spy, None, {"max_slots": 1})
    no_bars = run_mechanical_backtest({"AAA": aaa}, spy, None, {"max_slots": 1, "momentum_weight": 0.6})   # no momentum bars → dip-only
    assert old["metrics"]["trades"] == 1 and old["trades"][0]["exit"] == "tp" and old["trades"][0]["return"] >= 0.10
    assert old["trades"] == no_bars["trades"] and old["equity_curve"] == no_bars["equity_curve"]
    assert old["avg_momentum_share"] is None and old["shock_days"] == 0 and old["core_trades"] == no_bars["core_trades"]
