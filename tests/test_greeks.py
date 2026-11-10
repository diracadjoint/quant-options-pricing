"""Analytic sensitivities checked by identities and independent differentiation."""

from math import exp

import pytest

from options_engine import GreeksUnavailableError, bsm_greeks, bsm_price


def test_call_reference():
    g = bsm_greeks(100, 100, 1, 0.05, 0.20)
    for name, expected in dict(delta=0.6368306511756191, gamma=0.0187620173458469,
                               vega=37.52403469169379, theta=-6.414027546438197,
                               rho=53.232481545376345).items():
        assert getattr(g, name) == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("spot", [70, 100, 140])
@pytest.mark.parametrize("rate,yield_", [(0.05, 0), (-0.02, 0.03), (0.01, -0.01)])
@pytest.mark.parametrize("maturity", [0.1, 2.0])
def test_greek_identities_and_pde(spot, rate, yield_, maturity):
    c = bsm_greeks(spot, 100, maturity, rate, 0.3, yield_, "call")
    p = bsm_greeks(spot, 100, maturity, rate, 0.3, yield_, "put")
    assert c.delta - p.delta == pytest.approx(exp(-yield_ * maturity), abs=1e-12)
    assert c.rho - p.rho == pytest.approx(100 * maturity * exp(-rate * maturity), abs=1e-12)
    assert c.theta - p.theta == pytest.approx(
        yield_ * spot * exp(-yield_ * maturity) - rate * 100 * exp(-rate * maturity), abs=1e-12)
    assert c.gamma == p.gamma and c.vega == p.vega
    assert c.gamma >= 0 and c.vega >= 0
    for kind, greek in [("call", c), ("put", p)]:
        price = bsm_price(spot, 100, maturity, rate, 0.3, yield_, kind)
        residual = greek.theta + 0.5 * 0.3**2 * spot**2 * greek.gamma + (rate-yield_) * spot * greek.delta - rate * price
        assert residual == pytest.approx(0, abs=1e-11)


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("spot", [80, 100, 120])
@pytest.mark.parametrize("rate,yield_", [(0.05, 0), (-0.02, 0.03)])
def test_finite_differences(kind, spot, rate, yield_):
    parameters = dict(spot=spot, strike=100, maturity=0.7, rate=rate,
                      volatility=0.25, dividend_yield=yield_, option_type=kind)
    greek = bsm_greeks(**parameters)
    base = bsm_price(**parameters)
    for field, name, bump, sign in [("spot", "delta", 0.001, 1),
                                    ("volatility", "vega", 1e-5, 1),
                                    ("rate", "rho", 1e-5, 1),
                                    ("maturity", "theta", 1e-5, -1)]:
        up = bsm_price(**{**parameters, field: parameters[field] + bump})
        down = bsm_price(**{**parameters, field: parameters[field] - bump})
        assert getattr(greek, name) == pytest.approx(sign * (up-down)/(2*bump), rel=2e-6, abs=1e-7)
    bump = 0.01
    gamma = (bsm_price(**{**parameters, "spot": spot+bump}) - 2*base
             + bsm_price(**{**parameters, "spot": spot-bump})) / bump**2
    assert greek.gamma == pytest.approx(gamma, rel=2e-6, abs=1e-8)


@pytest.mark.parametrize("time,vol", [(0, 0.2), (1, 0), (0, 0)])
def test_unavailable_at_boundaries(time, vol):
    with pytest.raises(GreeksUnavailableError, match="positive maturity and volatility"):
        bsm_greeks(100, 100, time, 0.05, vol)


@pytest.mark.parametrize("override", [{"spot": 0}, {"rate": float("nan")},
                                      {"option_type": "CALL"}, {"volatility": -1}])
def test_invalid_inputs(override):
    args = dict(spot=100, strike=100, maturity=1, rate=0.05, volatility=0.2)
    with pytest.raises(ValueError):
        bsm_greeks(**{**args, **override})
