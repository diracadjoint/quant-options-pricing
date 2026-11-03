"""Uniform-spot Crank–Nicolson, Rannacher startup and American PSOR."""

from dataclasses import dataclass
from math import exp, isfinite
from typing import Literal

from .analytic import _finite_real, _validate_inputs
from .binomial import crr_price
from .psor import solve_psor


@dataclass(frozen=True)
class FDConfig:
    """Spatial/time interval counts and solver controls; Smax defaults to 4 max(S,K)."""

    spatial_steps: int = 200
    time_steps: int = 200
    s_max: float | None = None
    rannacher: bool = True
    omega: float = 1.2
    tolerance: float = 1e-8
    max_iterations: int = 10000


@dataclass(frozen=True)
class FDResult:
    """Price, final grid and diagnostics. Convergence here is algebraic only.

    Residual/violations/update are maxima over ALL solved LCP steps, scaled
    by strike. Boundary pairs are (remaining time, contact node or None),
    excluding expiry; contact requires strictly positive intrinsic payoff.
    """

    price: float
    config: FDConfig
    s_max: float
    spots: tuple[float, ...]
    values: tuple[float, ...]
    exercise_boundary: tuple[tuple[float, float | None], ...]
    max_residual: float
    max_update: float
    obstacle_violation: float
    dual_violation: float
    total_iterations: int
    max_iterations_used: int
    upwind_nodes: int
    cn_positive_rhs: bool
    method: str


def _tridiagonal(lower: list[float], diagonal: list[float], upper: list[float], rhs: list[float]) -> list[float]:
    """Thomas elimination; no dense matrix or inverse is formed."""
    d, b = diagonal.copy(), rhs.copy()
    for i in range(1, len(d)):
        ratio = lower[i-1]/d[i-1]
        d[i] -= ratio*upper[i-1]
        b[i] -= ratio*b[i-1]
    v = [0.0]*len(d)
    v[-1] = b[-1]/d[-1]
    for i in range(len(d)-2, -1, -1):
        v[i] = (b[i]-upper[i]*v[i+1])/d[i]
    return v


def fd_price(
    spot: float, strike: float, maturity: float, rate: float,
    volatility: float, dividend_yield: float = 0.0,
    option_type: Literal["call", "put"] = "call", *,
    exercise_style: Literal["european", "american"] = "american",
    config: FDConfig | None = None,
) -> FDResult:
    """Solve the BSM PDE/obstacle on [0,Smax], interpolating linearly at spot.

    Financial units match bsm_price. This PDE implementation validates only
    nonnegative rates and yields; BSM/CRR retain their broader domains.
    Central drift changes locally to a monotone first-order stencil where
    needed. Rannacher replaces the first TWO full steps with FOUR implicit
    half steps, solving the obstacle at each half step for Americans.
    No price accuracy is inferred from a small PSOR residual: refine spatial,
    temporal and truncation parameters separately. A single contact node is
    a grid approximation to an exercise boundary, not a smooth-pasting proof.
    """
    spot, strike, maturity, rate, volatility, dividend_yield = _validate_inputs(
        spot, strike, maturity, rate, volatility, dividend_yield, option_type
    )
    if rate < 0 or dividend_yield < 0:
        raise ValueError("finite differences currently require nonnegative rate and dividend_yield")
    if not isinstance(exercise_style, str) or exercise_style not in ("american", "european"):
        raise ValueError("exercise_style must be american or european")
    cfg = config if config is not None else FDConfig()
    if not isinstance(cfg, FDConfig):
        raise ValueError("config must be FDConfig")
    for name, minimum in (("spatial_steps", 3), ("time_steps", 2), ("max_iterations", 1)):
        value = getattr(cfg, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    if not isinstance(cfg.rannacher, bool):
        raise ValueError("rannacher must be bool")
    omega = _finite_real("omega", cfg.omega)
    tolerance = _finite_real("tolerance", cfg.tolerance)
    if not 0 < omega < 2 or tolerance <= 0:
        raise ValueError("omega must be in (0,2) and tolerance must be positive")
    smax = _finite_real("s_max", cfg.s_max if cfg.s_max is not None else 4*max(spot, strike))
    if smax <= max(spot, strike):
        raise ValueError("s_max must exceed spot and strike")
    if maturity == 0 or volatility == 0:
        deterministic = crr_price(spot, strike, maturity, rate, volatility, dividend_yield,
                                   option_type, exercise_style=exercise_style)
        return FDResult(deterministic.price, cfg, smax, (), (), (), 0, 0, 0, 0, 0, 0, 0, True, "deterministic")
    m = cfg.spatial_steps
    ds, dt = smax/m, maturity/cfg.time_steps
    if ds == 0 or dt == 0:
        raise ValueError("grid spacing underflows floating-point range")
    spots = [i*ds for i in range(m+1)]
    sign = 1 if option_type == "call" else -1
    payoff = [max(sign*(s-strike), 0.0) for s in spots]
    v = payoff.copy()
    a, b, c = [], [], []
    upwind = 0
    for i in range(1, m):
        try:
            diffusion = 0.5*(volatility*i)**2
        except OverflowError as exc:
            raise ValueError("operator exceeds floating-point range") from exc
        drift = (rate-dividend_yield)*i
        left, right = diffusion-drift/2, diffusion+drift/2
        if min(left, right) < 0:
            left, right = diffusion+max(-drift, 0), diffusion+max(drift, 0)
            upwind += 1
        a.append(left)
        c.append(right)
        b.append(-left-right-rate)
    if not all(isfinite(x) for vector in (a, b, c) for x in vector):
        raise ValueError("operator exceeds floating-point range")
    american = exercise_style == "american"

    def boundary(time: float) -> tuple[float, float]:
        if option_type == "put":
            return (strike if american else strike*exp(-rate*time)), 0.0
        asymptotic = max(smax*exp(-dividend_yield*time)-strike*exp(-rate*time), 0.0)
        return 0.0, max(smax-strike, asymptotic) if american else asymptotic

    residual = update = obstacle_violation = dual_violation = 0.0
    total_iterations = max_iterations_used = 0
    positive_rhs = True
    frontier = []
    time = 0.0
    for full_step in range(cfg.time_steps):
        startup = cfg.rannacher and full_step < 2
        h, theta = (dt/2, 1.0) if startup else (dt, 0.5)
        for _ in range(2 if startup else 1):
            next_time = time+h
            left_bc, right_bc = boundary(next_time)
            lower = [-theta*h*x for x in a[1:]]
            diagonal = [1-theta*h*x for x in b]
            upper = [-theta*h*x for x in c[:-1]]
            rhs = [v[i+1]+(1-theta)*h*(a[i]*v[i]+b[i]*v[i+1]+c[i]*v[i+2]) for i in range(m-1)]
            rhs[0] += theta*h*a[0]*left_bc
            rhs[-1] += theta*h*c[-1]*right_bc
            positive_rhs = positive_rhs and all(1+(1-theta)*h*x >= 0 for x in b)
            if american:
                solved = solve_psor(lower, diagonal, upper, rhs, payoff[1:-1], v[1:-1],
                                    scale=strike, tolerance=tolerance, omega=omega, max_iterations=cfg.max_iterations)
                interior = list(solved.values)
                residual = max(residual, solved.residual)
                update = max(update, solved.update)
                obstacle_violation = max(obstacle_violation, solved.obstacle_violation)
                dual_violation = max(dual_violation, solved.dual_violation)
                total_iterations += solved.iterations
                max_iterations_used = max(max_iterations_used, solved.iterations)
                contacts = [spots[i+1] for i, value in enumerate(interior)
                            if payoff[i+1] > 0 and abs(value-payoff[i+1]) <= max(10*tolerance, 1e-7)*strike]
                edge = ((max(contacts) if option_type == "put" else min(contacts)) if contacts else None)
                frontier.append((next_time, edge))
            else:
                interior = _tridiagonal(lower, diagonal, upper, rhs)
            v = [left_bc, *interior, right_bc]
            if not all(isfinite(x) for x in v):
                raise ValueError("finite differences produced nonfinite values")
            time = next_time
    cell = min(int(spot/ds), m-1)
    weight = (spot-spots[cell])/ds
    price = (1-weight)*v[cell]+weight*v[cell+1]
    return FDResult(price, cfg, smax, tuple(spots), tuple(v), tuple(frontier), residual,
                    update, obstacle_violation, dual_violation, total_iterations,
                    max_iterations_used, upwind, positive_rhs, "cn-psor" if american else "cn-thomas")
