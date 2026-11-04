"""Signed exposures, repricing, payoff settlement and explicit cash accounting."""

from dataclasses import replace
from math import exp

import pytest

from options_engine import (Bumps, FDConfig, Market, OptionContract, Portfolio, Position,
                            Scenario, bsm_greeks, bsm_price, scenario_pnl, value_portfolio)


MARKET = Market(100, .2, .05, .02)


def test_signed_value_and_all_greeks_with_multipliers():
    call = OptionContract(100, 1)
    put = OptionContract(110, .5, "put")
    book = Portfolio((Position(call, 2, 100), Position(put, -3, 50)), cash=1000)
    result = value_portfolio(book, MARKET)
    expected_value = 1000+200*bsm_price(100, 100, 1, .05, .2, .02)-150*bsm_price(100, 110, .5, .05, .2, .02, "put")
    assert result.total_value == pytest.approx(expected_value, abs=1e-10)
    c, p = bsm_greeks(100, 100, 1, .05, .2, .02), bsm_greeks(100, 110, .5, .05, .2, .02, "put")
    for name in ("delta", "gamma", "vega", "theta", "rho"):
        assert getattr(result.greeks, name) == pytest.approx(200*getattr(c, name)-150*getattr(p, name), abs=1e-9)


def test_offsetting_long_short_cancel_value_and_risk():
    contract = OptionContract(100, 1)
    book = Portfolio((Position(contract, 2, 50), Position(contract, -1, 100)))
    initial = value_portfolio(book, MARKET)
    assert initial.total_value == 0
    assert all(getattr(initial.greeks, n) == 0 for n in ("delta", "gamma", "vega", "theta", "rho"))
    scenario = scenario_pnl(book, MARKET, Scenario(10, .05, .01, .1), initial=initial)
    assert scenario.total_value == 0 and scenario.exact_pnl == 0


def test_unavailable_unit_greeks_cancel_only_for_exact_offsets():
    market = Market(100, 0, .05)
    contract = OptionContract(100, 1)
    hedged = Portfolio((Position(contract, 1, 100), Position(contract, -2, 50)))
    assert value_portfolio(hedged, market).greeks.gamma == 0
    unhedged = value_portfolio(Portfolio((Position(contract),)), market)
    assert unhedged.greeks.gamma is None
    assert unhedged.flags


@pytest.mark.parametrize("shock", [Scenario(), Scenario(2), Scenario(volatility_change=.01),
    Scenario(rate_change=.002), Scenario(elapsed=.02), Scenario(-3, .02, -.005, .1)])
def test_isolated_and_combined_scenarios_match_independent_bsm(shock):
    contract = OptionContract(100, 1, "put")
    book = Portfolio((Position(contract, -2, 100),), cash=500)
    result = scenario_pnl(book, MARKET, shock)
    expected = -200*bsm_price(100+shock.spot_change, 100, 1-shock.elapsed,
                               .05+shock.rate_change, .2+shock.volatility_change, .02, "put")
    expected += 500*exp((.05+shock.rate_change)*shock.elapsed)
    assert result.total_value == pytest.approx(expected, abs=1e-10)
    assert result.exact_pnl == pytest.approx(expected-result.initial.total_value, abs=1e-10)
    assert result.shocked_market.dividend_yield == MARKET.dividend_yield
    assert result.first_order_pnl is not None
    assert result.second_order_residual == pytest.approx(result.exact_pnl-result.second_order_pnl, abs=1e-10)


def test_gamma_term_improves_small_spot_shock():
    book = Portfolio((Position(OptionContract(100, 1), 1, 100),))
    result = scenario_pnl(book, MARKET, Scenario(spot_change=.1))
    assert abs(result.second_order_residual) < abs(result.first_order_residual)/100


def test_taylor_units_and_cash_carry_are_separate():
    book = Portfolio((Position(OptionContract(100, 1), 2, 100),), cash=-1000)
    shock = Scenario(1, .005, .001, .01)
    result = scenario_pnl(book, MARKET, shock)
    g = bsm_greeks(100, 100, 1, .05, .2, .02)
    first = 200*(g.delta+g.vega*.005+g.rho*.001+g.theta*.01)-1000*(exp(.051*.01)-1)
    assert result.first_order_pnl == pytest.approx(first, abs=1e-10)
    assert result.second_order_pnl == pytest.approx(first+100*g.gamma, abs=1e-10)


def test_empty_portfolio_and_unchanged_scenario():
    result = scenario_pnl(Portfolio(), MARKET, Scenario())
    assert result.total_value == result.exact_pnl == result.second_order_pnl == 0


@pytest.mark.parametrize("quantity", [2, -2])
@pytest.mark.parametrize("horizon", [.5, .75])
def test_expiry_cash_settlement_and_post_expiry_accrual(quantity, horizon):
    book = Portfolio((Position(OptionContract(100, .5), quantity, 100),), cash=-500)
    shock = Scenario(spot_change=20, rate_change=.01, elapsed=horizon)
    result = scenario_pnl(book, MARKET, shock)
    principal = quantity*100*20
    settled = principal*exp(.06*(horizon-.5))
    initial_cash = -500*exp(.06*horizon)
    assert result.option_value == 0
    assert result.settlement_cash_at_horizon == pytest.approx(settled, abs=1e-10)
    assert result.total_value == pytest.approx(settled+initial_cash, abs=1e-10)
    assert result.positions[0].settlement_time == .5
    assert result.positions[0].settlement_principal == principal
    assert result.first_order_pnl is None and result.second_order_pnl is None


def test_multiple_expiries_settle_at_their_own_time_without_double_counting():
    book = Portfolio((Position(OptionContract(100, .25), 1, 100),
                      Position(OptionContract(120, .75, "put"), -2, 50),
                      Position(OptionContract(100, 2), 1, 10)), cash=100)
    result = scenario_pnl(book, MARKET, Scenario(10, elapsed=1))
    # Spot jumps to 110 immediately and stays flat throughout the year.
    settlements = 1000*exp(.05*.75)-1000*exp(.05*.25)
    live = 10*bsm_price(110, 100, 1, .05, .2, .02)
    assert result.settlement_cash_at_horizon == pytest.approx(settlements, abs=1e-10)
    assert result.option_value == pytest.approx(live, abs=1e-10)
    assert result.cash == pytest.approx(100*exp(.05)+settlements, abs=1e-10)
    assert [leg.status for leg in result.positions] == ["settled", "settled", "active"]


def test_already_due_option_settles_before_spot_shock():
    market = Market(120, .2, .05)
    book = Portfolio((Position(OptionContract(100, 0), 1, 100),), cash=50)
    initial = value_portfolio(book, market)
    assert initial.option_value == 0 and initial.cash == 2050
    assert initial.greeks.delta == 0
    result = scenario_pnl(book, market, Scenario(spot_change=-40, elapsed=.5), initial=initial)
    assert result.total_value == pytest.approx(2050*exp(.05*.5), abs=1e-10)
    assert result.positions[0].status == "already_settled"
    assert result.positions[0].settlement_principal == 2000
    assert result.second_order_pnl == pytest.approx(result.exact_pnl, abs=1e-10)


def test_cash_only_with_negative_rates():
    book = Portfolio(cash=-2000)
    result = scenario_pnl(book, Market(100, .2, -.02), Scenario(elapsed=1))
    assert result.total_value == pytest.approx(-2000*exp(-.02))
    assert result.second_order_pnl == pytest.approx(result.exact_pnl)


def test_zero_quantity_does_not_poison_unavailable_risk():
    book = Portfolio((Position(OptionContract(100, 1), quantity=0),))
    result = value_portfolio(book, Market(100, 0, .05))
    assert result.total_value == 0 and result.greeks.gamma == 0 and not result.flags


def test_price_only_valuation_can_still_run_exact_scenarios():
    book = Portfolio((Position(OptionContract(100, 1)),))
    initial = value_portfolio(book, MARKET, compute_greeks=False)
    result = scenario_pnl(book, MARKET, Scenario(1), initial=initial)
    assert result.first_order_pnl is None
    assert result.exact_pnl > 0


def test_foreign_initial_valuation_is_rejected():
    book = Portfolio((Position(OptionContract(100, 1)),))
    initial = value_portfolio(book, MARKET)
    with pytest.raises(ValueError, match="must match"):
        scenario_pnl(book, replace(MARKET, spot=101), Scenario(), initial=initial)


def test_american_numerical_risk_is_cached_and_signed(monkeypatch):
    import options_engine.portfolio as module
    original, calls = module.numerical_greeks, []
    def recorded(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "numerical_greeks", recorded)
    contract = OptionContract(100, 1, "put", "american")
    book = Portfolio((Position(contract, 2, 100, "crr", tree_steps=100),
                      Position(contract, -1, 50, "crr", tree_steps=100)))
    result = value_portfolio(book, MARKET)
    assert len(calls) == 1
    assert result.positions[0].numerical_risk is not None
    unit = result.positions[0].unit_greeks
    assert result.greeks.delta == pytest.approx(150*unit.delta)
    assert result.total_value == pytest.approx(150*result.positions[0].unit_price)


def test_fd_grid_is_frozen_across_scenario_spot_shocks(monkeypatch):
    import options_engine.portfolio as module
    original, configs = module.fd_price, []
    def recorded(*args, **kwargs):
        configs.append(kwargs["config"])
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "fd_price", recorded)
    book = Portfolio((Position(OptionContract(100, 1, "put", "american"), method="fd",
                               fd_config=FDConfig(80, 40)),))
    market = Market(120, .2, .05)
    initial = value_portfolio(book, market, compute_greeks=False)
    result = scenario_pnl(book, market, Scenario(5, .01, .001, .02), initial=initial)
    assert all(cfg.s_max == 480 for cfg in configs)
    assert len(configs) == 2
    assert result.positions[0].status == "active"


def test_american_expiry_is_cash_settled_even_for_fd_method():
    book = Portfolio((Position(OptionContract(100, .5, "put", "american"), -1, 100, "fd",
                               fd_config=FDConfig(80, 40)),))
    initial = value_portfolio(book, MARKET, compute_greeks=False)
    result = scenario_pnl(book, MARKET, Scenario(-20, elapsed=.75), initial=initial)
    assert result.settlement_cash_at_horizon == pytest.approx(-2000*exp(.05*.25), abs=1e-10)
    assert result.first_order_pnl is None


@pytest.mark.parametrize("factory", [
    lambda: OptionContract(0, 1), lambda: OptionContract(100, -1),
    lambda: Market(0, .2, .05), lambda: Market(100, -.2, .05),
    lambda: Position(OptionContract(100, 1), multiplier=0),
    lambda: Position(OptionContract(100, 1), quantity=float("nan")),
    lambda: Position(OptionContract(100, 1), bumps=Bumps(spot=-1)),
    lambda: Position(OptionContract(100, 1, exercise_style="american")),
    lambda: Position(OptionContract(100, 1), method="unknown"),
    lambda: Portfolio(cash=float("inf")), lambda: Portfolio(("invalid",)),
    lambda: Scenario(elapsed=-1), lambda: Scenario(rate_change=float("nan")),
])
def test_invalid_inputs(factory):
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize("shock", [Scenario(-100), Scenario(volatility_change=-.3)])
def test_invalid_shocked_market_is_rejected(shock):
    with pytest.raises(ValueError):
        scenario_pnl(Portfolio(), MARKET, shock)
