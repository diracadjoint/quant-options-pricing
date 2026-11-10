"""Independent reference values and financial properties of European prices."""

from itertools import product
from math import exp, isfinite

import pytest

from options_engine import bsm_price


# Combined tolerances remain meaningful for prices/parity differences near zero.
REL_TOL = 1e-12
ABS_TOL = 1e-11
BASE = dict(spot=100.0, strike=100.0, maturity=1.0, rate=0.05, volatility=0.20)


@pytest.mark.parametrize("option_type,dividend_yield,expected", [
    ("call", 0.0, 10.450583572185565),
    ("put", 0.0, 5.573526022256971),
    # Standard continuous-dividend BSM benchmark at q = 2%.
    ("call", 0.02, 9.227005508154036),
    ("put", 0.02, 6.330080627549918),
])
def test_reference_prices(option_type, dividend_yield, expected):
    actual = bsm_price(**BASE, dividend_yield=dividend_yield, option_type=option_type)
    assert isinstance(actual, float)
    assert actual == pytest.approx(expected, rel=REL_TOL, abs=ABS_TOL)


def test_default_arguments():
    assert bsm_price(**BASE) == pytest.approx(
        10.450583572185565, rel=REL_TOL, abs=ABS_TOL
    )


@pytest.mark.parametrize("spot,maturity,rate,dividend_yield,volatility", list(product(
    (60.0, 100.0, 160.0), (0.0, 0.01, 1.0, 5.0), (-0.03, 0.0, 0.05),
    (-0.02, 0.0, 0.04), (0.0, 0.01, 0.20, 0.80),
)))
def test_parity_and_no_arbitrage(spot, maturity, rate, dividend_yield, volatility):
    strike = 100.0
    call = bsm_price(spot, strike, maturity, rate, volatility, dividend_yield, "call")
    put = bsm_price(spot, strike, maturity, rate, volatility, dividend_yield, "put")
    discounted_spot = spot * exp(-dividend_yield * maturity)
    discounted_strike = strike * exp(-rate * maturity)
    parity = discounted_spot - discounted_strike
    assert call - put == pytest.approx(parity, rel=REL_TOL, abs=ABS_TOL)
    tolerance = ABS_TOL + REL_TOL * max(discounted_spot, discounted_strike)
    assert max(parity, 0.0) - tolerance <= call <= discounted_spot + tolerance
    assert max(-parity, 0.0) - tolerance <= put <= discounted_strike + tolerance


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("volatility", [0.0, 0.20])
@pytest.mark.parametrize("spot", [80.0, 100.0, 120.0])
def test_expiry_is_exact_payoff(option_type, volatility, spot):
    expected = max(spot - 100.0, 0.0) if option_type == "call" else max(100.0 - spot, 0.0)
    assert bsm_price(spot, 100, 0, -0.03, volatility, 0.02, option_type) == expected


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("spot", [80.0, 100.0, 120.0])
@pytest.mark.parametrize("rate,dividend_yield", [(0.0, 0.0), (0.05, 0.02), (-0.03, -0.01)])
def test_zero_volatility(option_type, spot, rate, dividend_yield):
    difference = spot * exp(-dividend_yield * 2.0) - 100.0 * exp(-rate * 2.0)
    expected = max(difference if option_type == "call" else -difference, 0.0)
    assert bsm_price(spot, 100, 2, rate, 0, dividend_yield, option_type) == pytest.approx(
        expected, rel=REL_TOL, abs=ABS_TOL
    )


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("rate,dividend_yield", [(0.05, 0.0), (-0.03, 0.02), (0.0, -0.02)])
def test_spot_monotonicity(option_type, rate, dividend_yield):
    prices = [bsm_price(s, 100, 1, rate, 0.20, dividend_yield, option_type)
              for s in (50, 75, 90, 100, 110, 125, 150)]
    differences = [right - left for left, right in zip(prices, prices[1:])]
    if option_type == "call":
        assert all(difference > 0 for difference in differences)
    else:
        assert all(difference < 0 for difference in differences)


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("spot", [60, 100, 160])
@pytest.mark.parametrize("rate,dividend_yield", [(0.05, 0.0), (-0.03, 0.02), (0.0, -0.02)])
def test_volatility_monotonicity(option_type, spot, rate, dividend_yield):
    prices = [bsm_price(spot, 100, 1, rate, v, dividend_yield, option_type)
              for v in (0.0, 0.01, 0.10, 0.20, 0.40, 0.80)]
    assert all(right >= left - ABS_TOL for left, right in zip(prices, prices[1:]))


@pytest.mark.parametrize("name", [*BASE, "dividend_yield"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf"),
                                     None, "0.2", True, 1j, [0.2]])
def test_reject_nonfinite_or_nonscalar_inputs(name, invalid):
    with pytest.raises(ValueError, match=name):
        bsm_price(**{**BASE, name: invalid})


@pytest.mark.parametrize("name,invalid", [
    ("spot", 0), ("spot", -100), ("strike", 0), ("strike", -100),
    ("maturity", -1), ("volatility", -0.2), ("spot", 10**1000),
])
def test_reject_out_of_domain_inputs(name, invalid):
    with pytest.raises(ValueError, match=name):
        bsm_price(**{**BASE, name: invalid})


@pytest.mark.parametrize("option_type", ["CALL", "Put", "unknown", "", None, 1, ["call"]])
def test_reject_unknown_option_type(option_type):
    with pytest.raises(ValueError, match="option_type"):
        bsm_price(**BASE, option_type=option_type)


@pytest.mark.parametrize("maturity,volatility", [(0.0, 0.2), (1.0, 0.0), (0.0, 0.0)])
@pytest.mark.parametrize("override,match", [
    ({"rate": float("nan")}, "rate"), ({"spot": 0}, "spot"),
    ({"option_type": "unknown"}, "option_type"),
])
def test_validate_before_boundary_shortcuts(maturity, volatility, override, match):
    with pytest.raises(ValueError, match=match):
        bsm_price(**{**BASE, "maturity": maturity, "volatility": volatility, **override})


def test_expiry_does_not_evaluate_discount_factors():
    assert bsm_price(120, 100, 0, -1e308, 1e308, -1e308) == 20.0


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_short_maturity_prices_are_finite(option_type):
    price = bsm_price(100, 100, 1e-12, -0.03, 0.20, 0.02, option_type)
    assert isfinite(price) and price > 0


def test_large_spot_strike_ratio_does_not_overflow():
    assert bsm_price(1e200, 1e-200, 1, 0, 0.20) == pytest.approx(1e200, rel=REL_TOL)


@pytest.mark.parametrize("override", [
    {"rate": -1000}, {"dividend_yield": -1000},
    {"spot": 1e308, "dividend_yield": -1},
    {"rate": 1e308, "dividend_yield": -1e308},
])
def test_unrepresentable_intermediates_raise_clear_error(override):
    with pytest.raises(ValueError, match="floating-point range"):
        bsm_price(**{**BASE, **override})
