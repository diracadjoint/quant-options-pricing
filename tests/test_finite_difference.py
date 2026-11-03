"""Independent pricing references, obstacle checks and solver failures."""

import pytest

from options_engine import ConvergenceError, FDConfig, bsm_price, crr_price, fd_price
from options_engine.psor import solve_psor


def test_small_lcp_with_known_solution():
    result = solve_psor([-1.0], [2.0, 2.0], [-1.0], [0.0, 3.0], [2.0, 0.0], [2.0, 0.0], scale=1)
    # v=(2,2.5), w=(1.5,0), so exactly complementary.
    assert result.values == pytest.approx((2.0, 2.5), abs=1e-8)
    assert result.residual <= 1e-8
    assert result.dual_violation <= 1e-8


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("spot,rate,yield_,vol,time", [
    (80, .05, 0, .2, 1), (100, .05, .02, .2, 1), (120, 0, .04, .4, 2),
    (100, 0, 0, .1, .1),
])
def test_european_against_bsm(kind, spot, rate, yield_, vol, time):
    result = fd_price(spot, 100, time, rate, vol, yield_, kind,
                      exercise_style="european", config=FDConfig(400, 200, 400))
    reference = bsm_price(spot, 100, time, rate, vol, yield_, kind)
    assert abs(result.price-reference)/100 < 1e-3


def test_spatial_refinement():
    errors = []
    for m in (80, 160, 320, 640):
        result = fd_price(100, 100, 1, .05, .2, exercise_style="european", config=FDConfig(m, 400, 400))
        errors.append(abs(result.price-10.450583572185565))
    assert errors[-1] < errors[0]/20


@pytest.mark.parametrize("kind,spot,rate,yield_", [
    ("put", 100, .05, 0), ("put", 80, .05, 0),
    ("call", 100, .02, .10), ("call", 150, .02, .10), ("call", 100, .05, 0),
])
def test_american_crr_and_complementarity(kind, spot, rate, yield_):
    config = FDConfig(400, 200, 400)
    result = fd_price(spot, 100, 1, rate, .2, yield_, kind, config=config)
    reference = crr_price(spot, 100, 1, rate, .2, yield_, kind, steps=1200)
    european = fd_price(spot, 100, 1, rate, .2, yield_, kind, exercise_style="european", config=config)
    assert abs(result.price-reference.price)/100 < 1e-3
    assert result.price >= european.price-1e-5
    assert result.price >= max(spot-100 if kind == "call" else 100-spot, 0)-1e-10
    assert result.max_residual <= config.tolerance
    assert result.max_update <= config.tolerance
    assert result.obstacle_violation <= config.tolerance
    assert result.dual_violation <= config.tolerance
    assert result.total_iterations > 0
    assert all(v >= max(s-100 if kind == "call" else 100-s, 0)-1e-10
               for s, v in zip(result.spots, result.values))


def test_call_control_and_no_zero_payoff_boundary():
    result = fd_price(100, 100, 1, .05, .2, config=FDConfig(200, 100, 400))
    european = fd_price(100, 100, 1, .05, .2, exercise_style="european", config=result.config)
    assert result.price == pytest.approx(european.price, abs=1e-4)
    assert all(edge is None for _, edge in result.exercise_boundary)


def test_put_boundary_and_rannacher_steps():
    r = fd_price(100, 100, 1, .05, .2, option_type="put", config=FDConfig(200, 100, 400))
    assert len(r.exercise_boundary) == 102  # 4 half steps + 98 CN steps
    assert r.exercise_boundary[0][0] == pytest.approx(.005)
    assert r.exercise_boundary[-1][0] == pytest.approx(1)
    assert 60 < r.exercise_boundary[-1][1] < 100


def test_upwind_fallback():
    result = fd_price(100, 100, 1, .10, .01, exercise_style="european", config=FDConfig(100, 100, 400))
    assert result.upwind_nodes > 0
    assert result.price >= 0


def test_failure_propagates():
    with pytest.raises(ConvergenceError, match="failed after 1"):
        fd_price(100, 100, 1, .05, .2, option_type="put", config=FDConfig(max_iterations=1))


@pytest.mark.parametrize("config", [FDConfig(spatial_steps=2), FDConfig(time_steps=0),
    FDConfig(omega=2), FDConfig(tolerance=0), FDConfig(s_max=100),
    FDConfig(max_iterations=True), FDConfig(s_max=float("inf")), FDConfig(rannacher=1)])
def test_invalid_config(config):
    with pytest.raises(ValueError):
        fd_price(100, 100, 1, .05, .2, config=config)


@pytest.mark.parametrize("rate,yield_", [(-.01, 0), (.05, -.01)])
def test_pde_domain_is_explicit(rate, yield_):
    with pytest.raises(ValueError, match="nonnegative"):
        fd_price(100, 100, 1, rate, .2, yield_)


@pytest.mark.parametrize("time,vol", [(0, .2), (1, 0)])
def test_degenerate_branch(time, vol):
    r = fd_price(80, 100, time, .05, vol, option_type="put")
    assert r.price == crr_price(80, 100, time, .05, vol, option_type="put").price
    assert r.method == "deterministic"


@pytest.mark.parametrize("override", [{"omega": 0}, {"tolerance": -1}, {"max_iterations": 0}])
def test_invalid_psor_controls(override):
    with pytest.raises(ValueError):
        solve_psor([], [1.0], [], [1.0], [0.0], [0.0], scale=1, **override)


def test_temporal_refinement_at_fixed_spatial_resolution():
    errors = [abs(fd_price(100, 100, 1, .05, .2, exercise_style="european",
                          config=FDConfig(400, n, 400)).price-10.450583572185565)
              for n in (25, 50, 100, 200)]
    assert errors[-1] < errors[0]
    assert errors[-1] < .003


def test_domain_expansion_keeps_local_resolution():
    prices = [fd_price(100, 100, 1, .05, .2, option_type="put",
                       config=FDConfig(smax, 100, smax)).price
              for smax in (200, 300, 400, 500)]
    assert max(prices)-min(prices) < 1e-5


def test_psor_rejects_non_m_matrix():
    with pytest.raises(ValueError, match="M-matrix"):
        solve_psor([1.0], [2.0, 2.0], [1.0], [1.0, 1.0], [0.0, 0.0], [0.0, 0.0], scale=1)


def test_final_european_grid_is_monotone_and_nonnegative():
    r = fd_price(100, 100, .05, .05, .2, exercise_style="european", config=FDConfig(300, 100, 300))
    assert min(r.values) >= -1e-12
    assert all(y >= x-1e-12 for x, y in zip(r.values, r.values[1:]))


def test_interpolation_at_off_grid_spot():
    spot = 101.37
    result = fd_price(spot, 100, 1, .05, .2, exercise_style="european", config=FDConfig(400, 200, 400))
    assert result.price == pytest.approx(bsm_price(spot, 100, 1, .05, .2), abs=.01)
