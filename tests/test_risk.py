"""Numerical risk controls, repricing semantics and interpolation hazards."""

import pytest

from options_engine import Bumps, ConvergenceError, FDConfig, bsm_greeks, numerical_greeks


BUMPS = Bumps(spot=2, volatility=.005, rate=.001, maturity=.01)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_european_control_against_analytic_greeks(kind):
    result = numerical_greeks(100, 100, 1, .05, .2, .02, kind,
                              exercise_style="european", bumps=BUMPS,
                              fd_config=FDConfig(400, 150, 400, tolerance=1e-10))
    reference = bsm_greeks(100, 100, 1, .05, .2, .02, kind)
    budgets = dict(delta=.002, gamma=.0002, vega=.05, theta=.02, rho=.05)
    for name, atol in budgets.items():
        assert getattr(result, name).value == pytest.approx(getattr(reference, name), abs=atol)
    assert len(result.repricings) == 9
    assert all(r.residual is not None for r in result.repricings)


def test_american_no_dividend_call_control():
    result = numerical_greeks(100, 100, 1, .05, .2, bumps=BUMPS,
                              fd_config=FDConfig(320, 100, 400, tolerance=1e-10))
    reference = bsm_greeks(100, 100, 1, .05, .2)
    for name, atol in dict(delta=.002, gamma=.002, vega=.10, theta=.03, rho=.08).items():
        assert getattr(result, name).value == pytest.approx(getattr(reference, name), abs=atol)


@pytest.mark.parametrize("method", ["fd", "crr"])
def test_deep_exercise_put_local_greeks(method):
    result = numerical_greeks(50, 100, 1, .05, .2, option_type="put", method=method,
                              bumps=Bumps(2, .005, .001, .01), tree_steps=200,
                              fd_config=FDConfig(160, 80, 400, tolerance=1e-10) if method == "fd" else None)
    assert result.delta.value == pytest.approx(-1, abs=1e-9)
    for name in ("gamma", "vega", "theta", "rho"):
        assert getattr(result, name).value == pytest.approx(0, abs=1e-7)
    assert all(p.exercise_active for p in result.repricings)


def test_interpolation_can_hide_gamma_and_is_flagged():
    # S=100.25, bumps +/-0.1 stay in the same linear interpolation cell.
    result = numerical_greeks(100.25, 100, 1, .05, .2, option_type="put",
                              bumps=Bumps(.1, .005, .001, .01),
                              fd_config=FDConfig(160, 80, 400, tolerance=1e-10))
    assert result.gamma.value == pytest.approx(0, abs=1e-9)
    assert any("interpolation-limited" in flag for flag in result.gamma.flags)


def test_domain_is_frozen_when_default_smax_would_change(monkeypatch):
    import options_engine.risk as risk
    original = risk.fd_price
    configs = []
    def recorded(*args, **kwargs):
        configs.append(kwargs["config"])
        return original(*args, **kwargs)
    monkeypatch.setattr(risk, "fd_price", recorded)
    result = numerical_greeks(120, 100, 1, .05, .2, bumps=BUMPS,
                              fd_config=FDConfig(120, 50))
    assert result.fd_config.s_max == 480
    assert len(result.repricings) == 9
    assert len(configs) == 9
    assert all(config == result.fd_config for config in configs)


def test_rate_boundary_uses_forward_second_order_stencil():
    result = numerical_greeks(100, 100, 1, 0, .2, option_type="put",
                              exercise_style="european", bumps=BUMPS,
                              fd_config=FDConfig(320, 100, 400))
    assert result.rho.stencil == "forward-2"
    assert all(r.shift >= 0 for r in result.repricings if r.parameter == "rate")
    assert result.rho.value == pytest.approx(bsm_greeks(100, 100, 1, 0, .2, option_type="put").rho, abs=.1)


def test_zero_volatility_one_sided_vega():
    result = numerical_greeks(50, 100, 1, .05, 0, option_type="put", method="crr",
                              bumps=Bumps(1, .05, .001, .01), tree_steps=100)
    assert result.vega.stencil == "forward-2"
    assert any("zero-volatility" in flag for flag in result.vega.flags)


def test_expiry_greeks_unavailable():
    result = numerical_greeks(100, 100, 0, .05, .2)
    assert result.price == 0
    assert all(getattr(result, name).value is None for name in ("delta", "gamma", "vega", "theta", "rho"))
    assert len(result.repricings) == 1


def test_failures_are_not_silenced():
    with pytest.raises(ConvergenceError):
        numerical_greeks(100, 100, 1, .05, .2, fd_config=FDConfig(max_iterations=1))


@pytest.mark.parametrize("override", [dict(method="other"), dict(bumps=Bumps(spot=0)),
    dict(bumps=Bumps(rate=float("nan"))), dict(bumps="auto"), dict(spot=0),
    dict(rate=-.01), dict(fd_config="fine")])
def test_invalid_inputs(override):
    with pytest.raises(ValueError):
        numerical_greeks(**{**dict(spot=100, strike=100, maturity=1, rate=.05, volatility=.2), **override})


def test_bump_that_rounds_away_is_rejected():
    with pytest.raises(ValueError, match="not representable"):
        numerical_greeks(100, 100, 1, .05, .2, method="crr", bumps=Bumps(spot=1e-30), tree_steps=20)


def test_bumped_spot_cannot_move_fixed_domain():
    with pytest.raises(ValueError, match="s_max"):
        numerical_greeks(100, 100, 1, .05, .2, bumps=Bumps(spot=20), fd_config=FDConfig(40, 10, 110))


def test_near_frontier_regime_change_is_reported():
    result = numerical_greeks(81, 100, 1, .05, .2, option_type="put",
                              bumps=Bumps(2.5, .005, .001, .01),
                              fd_config=FDConfig(320, 100, 400, tolerance=1e-10))
    assert any("exercise regime changes" in flag for flag in result.gamma.flags)


@pytest.fixture(scope="module", params=[("put", .05, 0), ("call", .02, .10)])
def stability(request):
    kind, rate, yield_ = request.param
    cache = {}
    def evaluate(m=320, nt=100, scale=1, spot_bump=2.5):
        key = (m, nt, scale, spot_bump)
        if key not in cache:
            cache[key] = numerical_greeks(100, 100, 1, rate, .2, yield_, kind,
                bumps=Bumps(spot_bump*scale, .005*scale, .001*scale, .01*scale),
                fd_config=FDConfig(m, nt, 400, tolerance=1e-10))
        return cache[key]
    return evaluate


# Declared regression budgets for the two continuation benchmarks at K=100.
# Different scales/units require separate absolute budgets for each Greek.
STABILITY_BUDGETS = dict(delta=.003, gamma=.001, vega=.20, theta=.05, rho=.20)


def test_bump_stability_at_fixed_mesh(stability):
    results = [stability(m=640, scale=factor, spot_bump=1.25) for factor in (.5, 1, 2)]
    for name, budget in STABILITY_BUDGETS.items():
        values = [getattr(result, name).value for result in results]
        assert max(values)-min(values) < budget
    assert all(result.fd_config == results[0].fd_config for result in results)


def test_refined_setup_reduces_observed_delta_spread(stability):
    # Retain the original wider-range experiment instead of hiding its
    # truncation bias after selecting a finer-grid plateau. This comparison
    # changes BOTH setup choices and is not used to attribute error to either;
    # the per-axis tests above/below keep the other choices fixed.
    wide = [stability(scale=s).delta.value for s in (.5, 1, 2)]
    fine = [stability(m=640, scale=s, spot_bump=1.25).delta.value for s in (.5, 1, 2)]
    assert max(fine)-min(fine) < .5*(max(wide)-min(wide))


def test_spatial_stability_at_fixed_bumps_and_time_steps(stability):
    coarse, medium, fine = (stability(m=m) for m in (160, 320, 640))
    assert coarse.bumps == medium.bumps == fine.bumps
    for name, budget in STABILITY_BUDGETS.items():
        assert abs(getattr(medium, name).value-getattr(fine, name).value) < budget
    # Coarse results are observed, not assumed to have the same accuracy.


def test_temporal_stability_at_fixed_space_and_bumps(stability):
    results = [stability(nt=nt) for nt in (50, 100, 200)]
    for name, budget in STABILITY_BUDGETS.items():
        values = [getattr(result, name).value for result in results]
        assert max(values)-min(values) < budget
