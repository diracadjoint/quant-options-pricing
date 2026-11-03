"""Bump-and-reprice sensitivities with explicit stencils and solver metadata."""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal

from .analytic import _finite_real, _validate_inputs
from .binomial import crr_price
from .finite_difference import FDConfig, fd_price


@dataclass(frozen=True)
class Bumps:
    """Absolute perturbations; None selects documented relative/absolute floors."""

    spot: float | None = None
    volatility: float | None = None
    rate: float | None = None
    maturity: float | None = None


@dataclass(frozen=True)
class Sensitivity:
    """A finite-difference estimate, not an analytic or certified derivative."""

    value: float | None
    bump: float
    stencil: str
    flags: tuple[str, ...]


@dataclass(frozen=True)
class Repricing:
    parameter: str
    shift: float
    price: float
    exercise_active: bool
    residual: float | None
    iterations: int | None


@dataclass(frozen=True)
class NumericalGreeks:
    """Greeks in BSM units, actual bumps/configuration and every repricing.

    Theta is calendar theta per year, Vega/Rho per absolute unit. Divide by
    365 for daily theta, 100 for a volatility/rate percentage point. Flags
    describe detected hazards; absence of flags does not establish stability.
    """

    price: float
    delta: Sensitivity
    gamma: Sensitivity
    vega: Sensitivity
    theta: Sensitivity
    rho: Sensitivity
    bumps: Bumps
    method: str
    exercise_style: str
    fd_config: FDConfig | None
    tree_steps: int | None
    repricings: tuple[Repricing, ...]


def numerical_greeks(
    spot: float, strike: float, maturity: float, rate: float,
    volatility: float, dividend_yield: float = 0.0,
    option_type: Literal["call", "put"] = "call", *,
    method: Literal["fd", "crr"] = "fd",
    exercise_style: Literal["american", "european"] = "american",
    bumps: Bumps | None = None, fd_config: FDConfig | None = None,
    tree_steps: int = 500,
) -> NumericalGreeks:
    """Reprice every perturbation with optimal exercise solved afresh.

    Central second-order differences are preferred. When a lower domain
    boundary would be crossed, use second-order forward stencils instead.
    At expiry all Greeks are explicitly unavailable (price remains payoff).
    With FD, freeze Smax/M/Nt and all solver controls across spot/parameter
    bumps; the original maturity and each bumped maturity use the same Nt.
    This does not remove interpolation error: spot bumps smaller than dS
    can produce zero or spurious Gamma and are explicitly flagged.

    Default absolute bumps: max(.01*S,.01), max(.01*sigma,1e-4),
    max(.01*abs(r),1e-4), max(.01*tau,1/365), respectively.
    Explicit bumps must be finite and positive. q stays fixed. FD retains
    r,q>=0; CRR permits negative rates/yields. All pricing failures propagate;
    no clipping of invalid CRR probabilities or silent epsilon is used.
    """
    spot, strike, maturity, rate, volatility, dividend_yield = _validate_inputs(
        spot, strike, maturity, rate, volatility, dividend_yield, option_type
    )
    if method not in ("fd", "crr"):
        raise ValueError("method must be fd or crr")
    if bumps is None:
        bumps = Bumps()
    if not isinstance(bumps, Bumps):
        raise ValueError("bumps must be Bumps")
    default = Bumps(max(.01*spot, .01), max(.01*volatility, 1e-4),
                    max(.01*abs(rate), 1e-4), max(.01*maturity, 1/365))
    actual = {}
    for name in ("spot", "volatility", "rate", "maturity"):
        supplied = getattr(bumps, name)
        value = _finite_real(f"bumps.{name}", getattr(default, name) if supplied is None else supplied)
        if value <= 0:
            raise ValueError(f"bumps.{name} must be positive")
        actual[name] = value
    resolved = Bumps(**actual)
    fixed = None
    if method == "fd":
        if fd_config is not None and not isinstance(fd_config, FDConfig):
            raise ValueError("fd_config must be FDConfig")
        cfg = fd_config if fd_config is not None else FDConfig()
        fixed = replace(cfg, s_max=cfg.s_max if cfg.s_max is not None else 4*max(spot, strike))
    elif fd_config is not None:
        raise ValueError("fd_config applies only to method=fd")
    inputs = dict(spot=spot, strike=strike, maturity=maturity, rate=rate,
                  volatility=volatility, dividend_yield=dividend_yield, option_type=option_type)
    evaluations = []
    cache = {}

    def reprice(parameter: str, shift: float) -> Repricing:
        key = (parameter, shift) if shift else ("base", 0.0)
        if key in cache:
            return cache[key]
        parameters = {**inputs}
        if shift:
            bumped = parameters[parameter]+shift
            if not isfinite(bumped) or bumped == parameters[parameter]:
                raise ValueError(f"{parameter} bump is not representable")
            parameters[parameter] = bumped
        if method == "fd":
            solved = fd_price(**parameters, exercise_style=exercise_style, config=fixed)
            price, residual, iterations = solved.price, solved.max_residual, solved.total_iterations
        else:
            solved = crr_price(**parameters, exercise_style=exercise_style, steps=tree_steps)
            price, residual, iterations = solved.price, None, None
        payoff = max(parameters["spot"]-strike if option_type == "call" else strike-parameters["spot"], 0.0)
        # Price-based activity is diagnostic only; excludes zero-payoff tails.
        active = exercise_style == "american" and payoff > 0 and abs(price-payoff) <= 1e-7*strike
        result = Repricing(parameter if shift else "base", shift, price, active, residual, iterations)
        evaluations.append(result)
        cache[key] = result
        return result

    base = reprice("spot", 0.0)
    if maturity == 0:
        def unavailable(name: str) -> Sensitivity:
            return Sensitivity(None, actual[name], "unavailable", ("expiry: no classical Greek is asserted",))
        return NumericalGreeks(base.price, unavailable("spot"), unavailable("spot"),
                               unavailable("volatility"), unavailable("maturity"), unavailable("rate"),
                               resolved, method, exercise_style, fixed, tree_steps if method == "crr" else None,
                               tuple(evaluations))

    def estimate(parameter: str, second: bool = False, sign: float = 1) -> Sensitivity:
        h = actual[parameter]
        x = inputs[parameter]
        bounded = parameter != "rate" or method == "fd"
        forward = bounded and (x-h <= 0 if parameter == "spot" else x-h < 0)
        flags = []
        if forward:
            points = [base, reprice(parameter, h), reprice(parameter, 2*h)]
            if second:
                points.append(reprice(parameter, 3*h))
                value = (2*base.price-5*points[1].price+4*points[2].price-points[3].price)/h/h
            else:
                value = (-3*base.price+4*points[1].price-points[2].price)/(2*h)
            stencil = "forward-2"
            flags.append("one-sided domain boundary stencil")
        else:
            points = [base, reprice(parameter, h), reprice(parameter, -h)]
            value = ((points[1].price-2*base.price+points[2].price)/h/h if second
                     else (points[1].price-points[2].price)/(2*h))
            stencil = "central-2"
        if not isfinite(value):
            raise ValueError("sensitivity exceeds floating-point range")
        if parameter == "spot" and fixed is not None:
            if h < fixed.s_max/fixed.spatial_steps:
                flags.append("spot bump smaller than grid spacing: interpolation-limited")
        if len({p.exercise_active for p in points}) > 1:
            flags.append("exercise regime changes across repricings")
        if volatility == 0:
            flags.append("zero-volatility boundary: classical derivative not asserted")
        return Sensitivity(sign*value, h, stencil, tuple(flags))

    delta, gamma = estimate("spot"), estimate("spot", second=True)
    vega, theta, rho = estimate("volatility"), estimate("maturity", sign=-1), estimate("rate")
    return NumericalGreeks(base.price, delta, gamma, vega, theta, rho, resolved, method,
                           exercise_style, fixed, tree_steps if method == "crr" else None, tuple(evaluations))
