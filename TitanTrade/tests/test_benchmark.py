"""Tests for the benchmark (strategy vs SPY) metrics module.

All external calls (Alpaca portfolio history, SPY OHLCV) are mocked — zero
network, zero token spend. The statistical core is tested against
hand-computable fixtures.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from titantrade import benchmark as bm


def _levels(start: float, rets: list[float]) -> list[float]:
    """Build a level series from a start value and a list of daily returns."""
    out = [start]
    for r in rets:
        out.append(out[-1] * (1 + r))
    return out


# ---------------------------------------------------------------------------
# Pure statistics
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_identical_to_spy_is_beta_one_zero_alpha(self):
        rm = [0.10, -0.10, 0.10]
        spy = _levels(100, rm)
        strat = _levels(100, rm)  # identical returns
        m = bm.compute_metrics(strat, spy)

        assert m["insufficient_data"] is False
        assert m["n_days"] == 3
        assert m["beta"] == pytest.approx(1.0, abs=1e-9)
        assert m["alpha_annual_pct"] == pytest.approx(0.0, abs=1e-9)
        assert m["correlation"] == pytest.approx(1.0, abs=1e-9)
        assert m["excess_return_pct"] == pytest.approx(0.0, abs=1e-6)
        assert m["up_capture"] == pytest.approx(1.0, abs=1e-9)
        assert m["down_capture"] == pytest.approx(1.0, abs=1e-9)
        # Active return is identically zero → tracking error 0 → IR undefined.
        assert m["info_ratio"] is None

    def test_leveraged_2x_is_beta_two(self):
        rm = [0.10, -0.10, 0.10]
        rp = [2 * r for r in rm]
        m = bm.compute_metrics(_levels(100, rp), _levels(100, rm))
        assert m["beta"] == pytest.approx(2.0, abs=1e-9)
        assert m["alpha_annual_pct"] == pytest.approx(0.0, abs=1e-9)
        assert m["correlation"] == pytest.approx(1.0, abs=1e-9)

    def test_defensive_with_alpha(self):
        # rp = 0.5*rm + 0.001 → beta exactly 0.5, daily alpha exactly 0.001,
        # correlation +1 (affine), and both capture ratios < 1 (defensive).
        rm = [0.02, -0.01, 0.015, -0.02]
        c = 0.001
        rp = [0.5 * r + c for r in rm]
        m = bm.compute_metrics(_levels(100, rp), _levels(100, rm))

        assert m["beta"] == pytest.approx(0.5, abs=1e-9)
        assert m["alpha_annual_pct"] == pytest.approx(0.001 * 252 * 100, abs=1e-6)
        assert m["correlation"] == pytest.approx(1.0, abs=1e-9)
        assert m["up_capture"] < 1.0
        assert m["down_capture"] < 1.0
        assert m["up_days"] == 2
        assert m["down_days"] == 2
        # Positive alpha + higher Sharpe than SPY → "adding value".
        assert "Adding value" in bm.classify(m)

    def test_flat_benchmark_beta_undefined(self):
        spy = [100, 100, 100, 100]  # zero variance
        strat = _levels(100, [0.01, -0.01, 0.02])
        m = bm.compute_metrics(strat, spy)
        assert m["beta"] is None
        assert m["alpha_annual_pct"] is None
        assert "Beta undefined" in bm.classify(m)

    def test_insufficient_data(self):
        assert bm.compute_metrics([100.0], [100.0])["insufficient_data"] is True
        assert bm.compute_metrics([], [])["insufficient_data"] is True

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError):
            bm.compute_metrics([100, 101], [100, 101, 102])

    def test_max_drawdown(self):
        # Peak 110 → trough 88 = -20%.
        m = bm.compute_metrics([100, 110, 88, 95], [100, 101, 102, 103])
        assert m["max_drawdown_strategy_pct"] == pytest.approx(-20.0, abs=1e-6)
        assert m["max_drawdown_spy_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_total_and_excess_return(self):
        strat = _levels(100, [0.05, 0.05])   # +10.25%
        spy = _levels(100, [0.01, 0.01])     # +2.01%
        m = bm.compute_metrics(strat, spy)
        assert m["total_return_strategy_pct"] == pytest.approx(10.25, abs=1e-6)
        assert m["total_return_spy_pct"] == pytest.approx(2.01, abs=1e-6)
        assert m["excess_return_pct"] == pytest.approx(8.24, abs=1e-6)


class TestClassify:
    def test_dominated_by_spy(self):
        # Negative alpha + worse Sharpe.
        m = {
            "insufficient_data": False, "alpha_annual_pct": -5.0,
            "info_ratio": -0.3, "sharpe_strategy": 0.4, "sharpe_spy": 1.2,
        }
        assert "dominated" in bm.classify(m)

    def test_protection_not_selection(self):
        # Negative alpha but better Sharpe → smoother, protection working.
        m = {
            "insufficient_data": False, "alpha_annual_pct": -2.0,
            "sharpe_strategy": 1.5, "sharpe_spy": 1.0,
        }
        assert "protection" in bm.classify(m).lower()

    def test_insufficient(self):
        assert "Insufficient" in bm.classify({"insufficient_data": True})


# ---------------------------------------------------------------------------
# Discord summary formatting
# ---------------------------------------------------------------------------

class TestFormatSummaryLine:
    def test_renders_key_metrics(self):
        line = bm.format_summary_line({
            "insufficient_data": False, "beta": 0.78, "alpha_annual_pct": 12.3,
            "sharpe_strategy": 1.4, "sharpe_spy": 0.9, "n_days": 30,
            "total_return_strategy_pct": 1.8, "total_return_spy_pct": -1.5,
        })
        assert "β 0.78" in line
        assert "α +12.3%/yr" in line
        assert "Sharpe 1.40 vs SPY 0.90" in line
        assert "vs SPY -1.5%" in line

    def test_none_on_insufficient(self):
        assert bm.format_summary_line({"insufficient_data": True}) is None
        assert bm.format_summary_line(None) is None


# ---------------------------------------------------------------------------
# Live-data wiring (mocked broker + SPY)
# ---------------------------------------------------------------------------

class TestBrokerPortfolioHistory:
    def test_hits_correct_endpoint(self, fake_config):
        from titantrade import broker

        captured = {}

        class _Resp:
            def json(self):
                return {"timestamp": [1], "equity": [100.0]}

        def _fake(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["params"] = kwargs.get("params")
            return _Resp()

        with patch("titantrade.broker.fetch_with_retry", side_effect=_fake):
            out = broker.get_portfolio_history(fake_config, period="6M")

        assert captured["method"] == "GET"
        assert captured["url"].endswith("/v2/account/portfolio/history")
        assert captured["params"]["period"] == "6M"
        assert captured["params"]["timeframe"] == "1D"
        assert out["equity"] == [100.0]


class TestSessionDate:
    """Alpaca stamps 1D equity at 20:00 ET (= 00:00 UTC next day). The session
    date must come from market time, not UTC, or every day pairs with the wrong
    SPY close (the off-by-one that produced spurious negative betas)."""

    def test_midnight_utc_maps_to_prior_eastern_session(self):
        import datetime as _dt
        ts = int(_dt.datetime(2026, 6, 19, 0, 0, tzinfo=_dt.timezone.utc).timestamp())
        assert bm._session_date(ts) == "2026-06-18"

    def test_intraday_utc_same_eastern_day(self):
        import datetime as _dt
        ts = int(_dt.datetime(2026, 6, 18, 14, 0, tzinfo=_dt.timezone.utc).timestamp())  # 10:00 ET
        assert bm._session_date(ts) == "2026-06-18"


class TestAlign:
    def test_inner_join_on_date(self):
        equity = [("2026-06-01", 100.0), ("2026-06-02", 101.0), ("2026-06-03", 102.0)]
        spy = [("2026-06-02", 500.0), ("2026-06-03", 505.0), ("2026-06-04", 510.0)]
        dates, p, m = bm._align(equity, spy)
        assert dates == ["2026-06-02", "2026-06-03"]
        assert p == [101.0, 102.0]
        assert m == [500.0, 505.0]


class TestComputeBenchmarkEndToEnd:
    def test_computes_and_persists(self, fake_config, tmp_state_dir):
        ph = {
            "timestamp": [],
            "equity": [],
        }
        # 4 aligned trading days, strategy defensive vs SPY.
        dates = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"]
        spy_closes = [500.0, 510.0, 504.9, 512.5]
        equity_vals = [100000.0, 101000.0, 100600.0, 101400.0]
        import datetime as _dt
        for d, e in zip(dates, equity_vals):
            ts = int(_dt.datetime(
                int(d[:4]), int(d[5:7]), int(d[8:10]), 12, 0, tzinfo=_dt.timezone.utc
            ).timestamp())
            ph["timestamp"].append(ts)
            ph["equity"].append(e)

        spy_bars = [{"date": d, "close": c} for d, c in zip(dates, spy_closes)]

        with patch("titantrade.broker.get_portfolio_history", return_value=ph), \
             patch("titantrade.market_data.get_ohlcv", return_value=spy_bars):
            m = bm.compute_benchmark(fake_config, lookback_days=90)

        assert m["insufficient_data"] is False
        assert m["n_days"] == 3
        assert m["window_start"] == "2026-06-01"
        assert m["window_end"] == "2026-06-04"
        assert m["beta"] is not None
        # Persisted to state.
        saved = bm.load_metrics()
        assert saved is not None
        assert saved["window_end"] == "2026-06-04"

    def test_since_filter_excludes_early_days(self, fake_config, tmp_state_dir):
        dates = ["2026-05-20", "2026-05-21", "2026-06-01", "2026-06-02", "2026-06-03"]
        equity_vals = [90000.0, 80000.0, 100000.0, 101000.0, 100500.0]
        spy_closes = [480.0, 470.0, 500.0, 505.0, 503.0]
        import datetime as _dt
        ph = {"timestamp": [], "equity": []}
        for d, e in zip(dates, equity_vals):
            ts = int(_dt.datetime(
                int(d[:4]), int(d[5:7]), int(d[8:10]), 12, 0, tzinfo=_dt.timezone.utc
            ).timestamp())
            ph["timestamp"].append(ts)
            ph["equity"].append(e)
        spy_bars = [{"date": d, "close": c} for d, c in zip(dates, spy_closes)]

        with patch("titantrade.broker.get_portfolio_history", return_value=ph), \
             patch("titantrade.market_data.get_ohlcv", return_value=spy_bars):
            m = bm.compute_benchmark(fake_config, since="2026-06-01")

        # The volatile pre-June days are excluded.
        assert m["window_start"] == "2026-06-01"
        assert m["n_days"] == 2
        assert m["since"] == "2026-06-01"


class TestNotifierIntegration:
    def test_daily_summary_includes_benchmark_field(self, tmp_state_dir, monkeypatch):
        from unittest.mock import MagicMock

        from titantrade import notifier

        # Both modules must read the same temp state dir.
        monkeypatch.setattr("titantrade.notifier.STATE_DIR", tmp_state_dir, raising=False)
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/x")

        bm.save_metrics({
            "insufficient_data": False, "beta": 0.8, "alpha_annual_pct": 10.0,
            "sharpe_strategy": 1.2, "sharpe_spy": 0.8, "n_days": 20,
            "total_return_strategy_pct": 1.5, "total_return_spy_pct": -1.0,
        })

        with patch("titantrade.notifier.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notifier.send_daily_summary()

        payload = mock_post.call_args.kwargs["json"]
        names = [f["name"] for f in payload["embeds"][0]["fields"]]
        assert "Benchmark (vs SPY)" in names
