"""Independent cash identities, event settlement and hedge decision policies."""

from math import exp, expm1

import pytest

from options_engine import (Bumps, ConvergenceError, DeltaUnavailableError, DeltaWarningError,
    FDConfig, Market, OptionContract, PathPoint, Portfolio, Position,
    bsm_greeks, bsm_price, simulate_delta_hedge)


MARKET = Market(100, .2, .05, .02)


def book(quantity=1, multiplier=1, maturity=1, kind="call"):
    return Portfolio((Position(OptionContract(100, maturity, kind), quantity, multiplier),))


@pytest.mark.parametrize("strategy", ["unhedged", "static", "dynamic"])
def test_wealth_preserved_at_trades_and_interval_pnl_reconciles(strategy):
    result = simulate_delta_hedge(book(-2, 100), MARKET,
        [(0, 100), (.25, 110), (.5, 90), (.75, 105), (1, 120)],
        strategy=strategy, initial_wealth=1000)
    assert result.history[0].wealth == pytest.approx(1000, abs=1e-10)
    for row in result.history:
        assert row.wealth == pytest.approx(row.wealth_before_trade, abs=1e-10)
        assert row.cash == pytest.approx(row.cash_before_trade-row.trade_cost, abs=1e-10)
        assert row.trade_cost == pytest.approx((row.shares_after-row.shares_before)*row.spot, abs=1e-10)
        assert row.wealth == pytest.approx(row.option_value+row.shares_after*row.spot+row.cash, abs=1e-10)
        assert abs(row.reconciliation_error) < 1e-9
    assert result.pnl == pytest.approx(result.option_pnl+result.stock_pnl+result.dividends+result.financing, abs=1e-9)
    assert result.risk_free_wealth == pytest.approx(1000*exp(.05), abs=1e-10)
    assert result.excess_wealth == pytest.approx(result.final_wealth-1000*exp(.05), abs=1e-10)


@pytest.mark.parametrize("quantity,kind", [(1, "call"), (-1, "call"), (1, "put"), (-1, "put")])
def test_opening_shares_sign_and_cash_financing(quantity, kind):
    result = simulate_delta_hedge(book(quantity, 100, kind=kind), MARKET,
                                  [(0, 100), (1, 100)], strategy="static", initial_wealth=0)
    g = bsm_greeks(100, 100, 1, .05, .2, .02, kind)
    value = quantity*100*bsm_price(100, 100, 1, .05, .2, .02, kind)
    row = result.history[0]
    assert row.delta_used == pytest.approx(quantity*100*g.delta)
    assert row.shares_after == pytest.approx(-quantity*100*g.delta)
    assert row.cash_before_trade == pytest.approx(-value)
    assert row.cash == pytest.approx(-value-row.shares_after*100, abs=1e-9)
    assert row.shares_after*row.trade_cost > 0  # buys cost cash, sales raise cash


@pytest.mark.parametrize("cash", [1000, -1000])
@pytest.mark.parametrize("rate", [.05, -.02])
def test_positive_and_negative_cash_financing(cash, rate):
    market = Market(100, .2, rate)
    result = simulate_delta_hedge(Portfolio(cash=cash), market, [(0, 100), (.5, 110), (1, 90)])
    assert result.final_wealth == pytest.approx(cash*exp(rate), abs=1e-10)
    assert result.history[1].financing == pytest.approx(cash*expm1(rate*.5), abs=1e-10)


@pytest.mark.parametrize("quantity", [1, -1])
def test_dividends_received_or_paid_by_signed_stock_position(quantity):
    result = simulate_delta_hedge(book(quantity), MARKET, [(0, 100), (.5, 110), (1, 120)],
                                  strategy="static", initial_wealth=100)
    h = result.history[0].shares_after
    assert result.history[1].dividends == pytest.approx(.02*h*105*.5, abs=1e-12)
    assert result.history[2].dividends == pytest.approx(.02*h*115*.5, abs=1e-12)
    assert result.dividends*h > 0


def test_dividend_credit_is_at_endpoint_and_not_accrued_inside_interval():
    result = simulate_delta_hedge(book(-1), MARKET, [(0, 100), (.5, 110), (1, 120)],
                                  strategy="static", initial_wealth=100)
    a, b, c = result.history
    expected_dividend = .02*a.shares_after*105*.5
    assert b.cash_before_trade == pytest.approx(a.cash*exp(.05*.5)+expected_dividend, abs=1e-12)
    assert c.financing == pytest.approx(b.cash*expm1(.05*.5), abs=1e-12)


def test_quantity_multiplier_and_fractional_stock_holdings():
    first = simulate_delta_hedge(book(2, 50), MARKET, [(0, 100), (1, 110)], initial_wealth=1000)
    second = simulate_delta_hedge(book(1, 100), MARKET, [(0, 100), (1, 110)], initial_wealth=1000)
    assert first.final_wealth == pytest.approx(second.final_wealth)
    assert first.history[0].shares_after == pytest.approx(second.history[0].shares_after)
    assert not first.history[0].shares_after.is_integer()


def test_unhedged_payoff_cash_and_initial_premium_funding():
    result = simulate_delta_hedge(book(-1, 100), MARKET, [(0, 100), (1, 120)],
                                  strategy="unhedged", initial_wealth=1000)
    premium = 100*bsm_price(100, 100, 1, .05, .2, .02)
    expected = (1000+premium)*exp(.05)-2000
    assert result.final_wealth == pytest.approx(expected, abs=1e-10)
    assert all(row.shares_after == 0 for row in result.history)
    assert result.history[-1].settlement_cash == -2000
    assert result.history[-1].option_value == 0


def test_expiry_inserted_with_linear_spot_and_stock_closed_once():
    market = Market(100, .2, 0, 0)
    result = simulate_delta_hedge(book(1, maturity=.5), market, [(0, 100), (1, 120)],
                                  strategy="static", initial_wealth=0)
    a, expiry, final = result.history
    assert expiry.time == .5 and expiry.spot == 110
    assert expiry.settlement_cash == 10
    assert expiry.shares_after == 0
    assert expiry.trade_cost == pytest.approx(-a.shares_after*110)
    assert expiry.cash == pytest.approx(a.cash+10+a.shares_after*110, abs=1e-12)
    assert final.settlement_cash == 0 and final.trade_cost == 0
    assert final.cash == expiry.cash


def test_already_due_option_converts_to_cash_once():
    market = Market(120, .2, .05)
    result = simulate_delta_hedge(book(2, 100, maturity=0), market, [(0, 120), (1, 80)])
    assert result.initial_wealth == 4000
    assert result.history[0].settlement_cash == 4000
    assert result.history[-1].settlement_cash == 0
    assert result.final_wealth == pytest.approx(4000*exp(.05), abs=1e-10)


def test_default_nav_preserves_existing_cash_explicit_wealth_records_adjustment():
    portfolio = Portfolio(book().positions, cash=500)
    result = simulate_delta_hedge(portfolio, MARKET, [(0, 100), (1, 100)])
    expected_nav = 500+bsm_price(100, 100, 1, .05, .2, .02)
    assert result.initial_wealth == pytest.approx(expected_nav)
    assert result.opening_cash_adjustment == 0
    funded = simulate_delta_hedge(portfolio, MARKET, [(0, 100), (1, 100)], initial_wealth=10)
    assert funded.opening_cash_adjustment == pytest.approx(10-expected_nav)


def test_horizon_closes_stock_but_live_options_remain_marked():
    result = simulate_delta_hedge(book(), MARKET, [(0, 100), (.5, 110)])
    final = result.history[-1]
    assert final.shares_after == 0 and final.option_value > 0
    assert not final.settlements
    assert final.warnings


@pytest.mark.parametrize("policy", ["raise", "allow"])
def test_unavailable_delta_always_errors(policy):
    with pytest.raises(DeltaUnavailableError) as caught:
        simulate_delta_hedge(book(), Market(100, 0, .05), [(0, 100), (1, 110)], warning_policy=policy)
    assert caught.value.time == 0
    assert caught.value.valuation.greeks.delta is None
    unhedged = simulate_delta_hedge(book(), Market(100, 0, .05), [(0, 100), (1, 110)], strategy="unhedged")
    assert unhedged.history[0].delta_used is None


def american_fd():
    return Portfolio((Position(OptionContract(100, .5, "put", "american"), method="fd",
                               fd_config=FDConfig(40, 20), bumps=Bumps(1, .01, .001, .01)),))


def test_numeric_warnings_preserved_and_policy_enforced():
    portfolio = american_fd()
    path = [(0, 100), (.25, 105), (.5, 110)]
    with pytest.raises(DeltaWarningError) as caught:
        simulate_delta_hedge(portfolio, MARKET, path)
    assert caught.value.valuation.positions[0].numerical_risk is not None
    result = simulate_delta_hedge(portfolio, MARKET, path, warning_policy="allow")
    for row in result.history[:-1]:
        assert row.used_warned_delta
        assert any("interpolation-limited" in flag for flag in row.warnings)
        assert row.valuation.positions[0].numerical_risk.repricings
        assert row.valuation.positions[0].fixed_fd_config.s_max == 400
    assert result.american_policy == "hold_to_expiry_no_early_assignment"


def test_solver_failure_propagates():
    portfolio = Portfolio((Position(OptionContract(100, 1, "put", "american"), method="fd",
                                   fd_config=FDConfig(max_iterations=1)),))
    with pytest.raises(ConvergenceError):
        simulate_delta_hedge(portfolio, MARKET, [(0, 100), (1, 110)], warning_policy="allow")


def test_american_risk_refreshed_even_when_static_inventory_is_held():
    result = simulate_delta_hedge(american_fd(), MARKET,
        [(0, 100), (.1, 101), (.2, 102), (.3, 103)], strategy="static", warning_policy="allow")
    for row in result.history:
        assert row.valuation.positions[0].numerical_risk.repricings
        assert row.valuation.positions[0].fixed_fd_config.s_max == 400
        assert row.valuation.greeks.delta is not None
        assert any("interpolation-limited" in flag for flag in row.warnings)
    assert all(row.delta_used is None for row in result.history[1:])
    assert not result.history[-1].used_warned_delta
    assert result.history[-1].shares_after == 0


def test_schedule_and_forced_partial_expiry_rebalance():
    portfolio = Portfolio((Position(OptionContract(100, .3)), Position(OptionContract(100, 1))))
    result = simulate_delta_hedge(portfolio, MARKET,
        [(0, 100), (.2, 102), (.4, 104), (.6, 106), (.8, 108), (1, 110)], rebalance_every=2)
    decisions = [round(row.time, 6) for row in result.history if row.action in ("open_hedge", "rebalance")]
    assert decisions == [0, .3, .4, .8]
    assert result.history[2].settlement_cash == 3


@pytest.mark.parametrize("path", [[], [(0, 100)], [(1, 100), (2, 110)],
    [(0, 99), (1, 100)], [(0, 100), (0, 110)], [(0, 100), (.5, 100), (.4, 100)],
    [(0, 100), (1, 0)], [(0, 100), (1, -1)], [(0, 100), (float("inf"), 100)],
    [(0, 100), (1, float("nan"))], [(0, 100), (True, 100)], [(0, 100), (1, 2, 3)]])
def test_invalid_paths(path):
    with pytest.raises(ValueError):
        simulate_delta_hedge(book(), MARKET, path)


@pytest.mark.parametrize("override", [dict(strategy="unknown"), dict(warning_policy="ignore"),
    dict(rebalance_every=0), dict(rebalance_every=True), dict(rebalance_every=1.5),
    dict(initial_wealth=float("nan"))])
def test_invalid_controls(override):
    with pytest.raises(ValueError):
        simulate_delta_hedge(book(), MARKET, [PathPoint(0, 100), PathPoint(1, 110)], **override)
