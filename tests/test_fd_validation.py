"""Declared benchmark budgets for price, frontier and domain stability.

These are regression limits at K=100, not global accuracy guarantees. Frontier
budgets describe peer-grid stability; no exact free-boundary reference exists.
"""

import pytest

pytestmark = pytest.mark.slow

from options_engine import FDConfig, crr_price, fd_price


PRICE_BUDGET = .003  # absolute price; 3e-5 K, vs the former 1e-3 K
DOMAIN_BUDGET = 1e-5  # expansion at fixed dS=1, Nt=200
TIMES = (.25, .5, 1.0)  # remaining years, away from expiry


def samples(result):
    selected = [min(result.exercise_boundary, key=lambda pair: abs(pair[0]-t)) for t in TIMES]
    for (time, edge), expected in zip(selected, TIMES):
        assert time == pytest.approx(expected, abs=1e-12)
        assert edge is not None
    return [edge for _, edge in selected]


@pytest.fixture(scope="module", params=[("put", .05, 0), ("call", .02, .10)])
def benchmark(request):
    kind, rate, yield_ = request.param
    grids = {m: fd_price(100, 100, 1, rate, .2, yield_, kind,
                         config=FDConfig(m, 200, 400)) for m in (160, 320, 640, 1280)}
    return kind, rate, yield_, grids


def test_fine_price_against_stable_even_odd_crr(benchmark):
    kind, rate, yield_, grids = benchmark
    references = [crr_price(100, 100, 1, rate, .2, yield_, kind, steps=n).price
                  for n in (1200, 1201, 2400, 2401)]
    # Protect the reference's own refinement and parity stability separately.
    assert abs(references[2]-references[0]) < .001
    assert abs(references[3]-references[1]) < .001
    assert abs(references[2]-references[3]) < .001
    # Test against BOTH parities rather than cancellation in their average.
    for reference in references[2:]:
        assert abs(grids[640].price-reference) < PRICE_BUDGET
        assert abs(grids[1280].price-reference) < PRICE_BUDGET


def test_frontier_spatial_stability_is_separate_from_price(benchmark):
    _, _, _, grids = benchmark
    reference = samples(grids[1280])
    for m in (160, 320, 640):
        # Two cells allow contact quantization; do not demand monotonic errors.
        assert max(abs(a-b) for a, b in zip(samples(grids[m]), reference)) <= 2*(400/m)
    # At the two finest levels, require <= one COARSER cell at every date.
    assert max(abs(a-b) for a, b in zip(samples(grids[640]), reference)) <= 400/640


def test_frontier_temporal_stability(benchmark):
    kind, rate, yield_, grids = benchmark
    refined = fd_price(100, 100, 1, rate, .2, yield_, kind, config=FDConfig(640, 400, 400))
    assert max(abs(a-b) for a, b in zip(samples(grids[640]), samples(refined))) <= 400/640


def test_value_matching_and_continuation_slope(benchmark):
    kind, _, _, grids = benchmark
    target = -1 if kind == "put" else 1
    for m in (640, 1280):
        result = grids[m]
        edge = samples(result)[-1]
        i = round(edge/(400/m))
        j = i+1 if kind == "put" else i-1
        payoff = max(100-edge if kind == "put" else edge-100, 0)
        assert abs(result.values[i]-payoff) <= 1e-5
        assert (max(100-result.spots[j], 0) if kind == "put" else max(result.spots[j]-100, 0)) > 0
        # Continuation-side secant, a smooth-pasting diagnostic, not an exact
        # derivative at a mesh-quantized contact or an American Greek API.
        slope = (result.values[j]-result.values[i])/(result.spots[j]-result.spots[i])
        assert abs(slope-target) < .03


@pytest.mark.parametrize("rate,yield_", [(.02, .10), (.05, .01)])
def test_dividend_call_domain_expansion(rate, yield_):
    # High q exercises before the upper boundary; low q tests its approximate
    # continuation condition. Resolution and spot interpolation stay fixed.
    results = [fd_price(100, 100, 1, rate, .2, yield_, "call",
                        config=FDConfig(smax, 200, smax)) for smax in (200, 300, 400, 500)]
    assert max(r.price for r in results)-min(r.price for r in results) < DOMAIN_BUDGET
    if yield_ == .10:
        assert all(r.exercise_boundary[-1][1] == 118 for r in results)
    else:
        # Absence of contact in this finite domain is not proof of no global
        # exercise boundary. At low yield the economic boundary can be higher.
        assert all(r.exercise_boundary[-1][1] is None for r in results)
