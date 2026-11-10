"""CRR controls, convergence, early exercise and deterministic optimization."""

from math import exp, log

import pytest

from options_engine import bsm_price, crr_price


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("rate,yield_", [(0.05, 0), (-0.02, 0.03)])
def test_european_convergence(kind, rate, yield_):
    reference = bsm_price(100, 100, 1, rate, 0.2, yield_, kind)
    # Separate even and odd sequences: CRR errors need not decrease monotonically.
    for parity in (0, 1):
        errors = []
        for steps in (100, 200, 400, 800):
            result = crr_price(100, 100, 1, rate, 0.2, yield_, kind,
                               exercise_style="european", steps=steps+parity)
            errors.append(abs(result.price-reference))
            assert result.early_exercise_premium == 0
        assert errors[-1] < errors[0]
        assert errors[-1] / 100 < 1e-3


def test_one_step_independent_recursion():
    up, down = exp(0.2), exp(-0.2)
    p = (exp(0.05)-down) / (up-down)
    expected = exp(-0.05) * (1-p) * (100-100*down)
    result = crr_price(100, 100, 1, 0.05, 0.2, option_type="put", steps=1)
    assert result.price == pytest.approx(expected, abs=1e-12)
    assert result.probability == pytest.approx(p, abs=1e-12)


def test_call_without_dividends_has_no_early_exercise():
    result = crr_price(100, 100, 1, 0.05, 0.2, steps=800)
    assert result.price == pytest.approx(result.european_price, abs=1e-11)
    assert result.price == pytest.approx(10.450583572185565, abs=0.003)


def test_american_put_refinement_and_reference():
    prices = [crr_price(100, 100, 1, 0.05, 0.2, option_type="put", steps=n).price
              for n in (200, 400, 800, 1600)]
    # Classic American put benchmark; absolute price tolerance declared upfront.
    assert prices[-1] == pytest.approx(6.0896, abs=0.003)
    assert abs(prices[-1]-prices[-2]) < 0.003
    assert max(prices[-2:])-min(prices[-2:]) < max(prices[:2])-min(prices[:2])


@pytest.mark.parametrize("kind,spot,rate,yield_", [
    ("put", 80, 0.05, 0), ("put", 100, 0.05, 0),
    ("call", 150, 0.02, 0.10), ("call", 80, 0.02, 0.01),
    ("put", 100, -0.02, 0.03),
])
def test_obstacle_and_same_tree_control(kind, spot, rate, yield_):
    result = crr_price(spot, 100, 1, rate, 0.2, yield_, kind, steps=400)
    payoff = max(spot-100 if kind == "call" else 100-spot, 0)
    assert result.price >= payoff-1e-11
    assert result.price >= result.european_price-1e-11
    if rate >= 0 and yield_ >= 0:
        assert result.price <= (spot if kind == "call" else 100) + 1e-10


def test_dividend_call_exercises_immediately():
    r = crr_price(150, 100, 1, 0.02, 0.2, 0.10, steps=800)
    assert r.price == pytest.approx(50, abs=1e-10)
    assert r.early_exercise_premium > 5


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("spot", [80, 100, 120])
def test_expiry_and_deterministic_european(kind, spot):
    for maturity, volatility in [(0, 0.2), (1, 0)]:
        result = crr_price(spot, 100, maturity, -0.02, volatility, 0.03, kind,
                           exercise_style="european")
        assert result.price == bsm_price(spot, 100, maturity, -0.02, volatility, 0.03, kind)
        assert result.probability is None


def test_deterministic_interior_optimum():
    # For r=.10, q=.05, S=K=100 the maximum occurs at log(2)/.05.
    optimum = log(2)/0.05
    expected = 100*exp(-0.05*optimum)-100*exp(-0.10*optimum)
    result = crr_price(100, 100, 20, 0.10, 0, 0.05)
    assert result.price == pytest.approx(expected, abs=1e-12)
    assert result.price > result.european_price


def test_deterministic_american_put_exercises_now():
    assert crr_price(80, 100, 1, 0.05, 0, option_type="put").price == 20


@pytest.mark.parametrize("override", [
    {"steps": 0}, {"steps": -1}, {"steps": True}, {"steps": 1.5},
    {"exercise_style": "bermudan"}, {"spot": 0}, {"volatility": -1},
    {"rate": float("inf")}, {"option_type": "other"},
])
def test_invalid_inputs(override):
    with pytest.raises(ValueError):
        crr_price(**{**dict(spot=100, strike=100, maturity=1, rate=0.05, volatility=0.2), **override})


def test_invalid_probability_is_not_clipped():
    with pytest.raises(ValueError, match="probability.*increase steps"):
        crr_price(100, 100, 1, 0.5, 0.01, steps=1)


def test_negative_rate_deterministic_put_interior_optimum():
    # With x=exp(.05 u), discounted put payoff is 100x-25x²,
    # maximized at x=2 with value 100, strictly inside [0, 30].
    result = crr_price(25, 100, 30, -0.05, 0, -0.10, "put")
    schedule = [max(100*exp(0.05*u)-25*exp(0.10*u), 0)
                for u in (j*0.01 for j in range(3001))]
    assert result.price >= max(schedule)-1e-10
    assert result.price == pytest.approx(100, abs=1e-10)
