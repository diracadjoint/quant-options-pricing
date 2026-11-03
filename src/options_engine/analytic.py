"""Scalar Black–Scholes–Merton prices with continuous dividends."""

from dataclasses import dataclass
from math import erfc, exp, isfinite, log, pi, sqrt
from numbers import Real
from typing import Literal


def _finite_real(name: str, value: float) -> float:
    """Validate and normalize a real scalar without accepting strings or bools."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real scalar")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real scalar") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite real scalar")
    return result


def _validate_inputs(
    spot: float, strike: float, maturity: float, rate: float,
    volatility: float, dividend_yield: float, option_type: str,
) -> tuple[float, float, float, float, float, float]:
    """Validate the shared scalar domain for analytic and tree pricers."""
    spot = _finite_real("spot", spot)
    strike = _finite_real("strike", strike)
    maturity = _finite_real("maturity", maturity)
    rate = _finite_real("rate", rate)
    volatility = _finite_real("volatility", volatility)
    dividend_yield = _finite_real("dividend_yield", dividend_yield)
    if spot <= 0.0:
        raise ValueError("spot must be strictly positive")
    if strike <= 0.0:
        raise ValueError("strike must be strictly positive")
    if maturity < 0.0:
        raise ValueError("maturity must be nonnegative")
    if volatility < 0.0:
        raise ValueError("volatility must be nonnegative")
    if not isinstance(option_type, str) or option_type not in ("call", "put"):
        raise ValueError('option_type must be "call" or "put"')

    return spot, strike, maturity, rate, volatility, dividend_yield


def _normal_cdf(value: float) -> float:
    # erfc avoids the tail cancellation in (1 + erf(x / sqrt(2))) / 2.
    return 0.5 * erfc(-value / sqrt(2.0))


class GreeksUnavailableError(ValueError):
    """The analytic interior Greek formulas are unavailable at a boundary."""


@dataclass(frozen=True)
class Greeks:
    """European sensitivities; vega/rho per absolute unit, theta per year."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


def bsm_greeks(
    spot: float, strike: float, maturity: float, rate: float,
    volatility: float, dividend_yield: float = 0.0,
    option_type: Literal["call", "put"] = "call",
) -> Greeks:
    """Return analytic European Delta, Gamma, Vega, calendar Theta and Rho.

    Inputs and assumptions match :func:`bsm_price`. Theta is minus the
    derivative in remaining maturity, per calendar year (daily = theta/365).
    Vega and Rho are per absolute unit of volatility/rate; divide by 100 for
    one percentage point, or Rho by 10,000 for one basis point.
    Raises GreeksUnavailableError at zero maturity or volatility; this API
    intentionally supplies only the classical interior formulas. No American
    sensitivities are implied. Invalid inputs/range errors raise ValueError.
    """
    spot, strike, maturity, rate, volatility, dividend_yield = _validate_inputs(
        spot, strike, maturity, rate, volatility, dividend_yield, option_type
    )
    if maturity == 0 or volatility == 0:
        raise GreeksUnavailableError("analytic Greeks require positive maturity and volatility")
    try:
        width = volatility * sqrt(maturity)
        if width == 0 or not isfinite(width):
            raise ValueError("parameters exceed the supported floating-point range")
        center = (log(spot) - log(strike) + (rate - dividend_yield) * maturity) / width
        d1, d2 = center + width / 2, center - width / 2
        if not (isfinite(d1) and isfinite(d2)):
            raise ValueError("parameters exceed the supported floating-point range")
        discount = exp(-dividend_yield * maturity)
        discounted_spot = spot * discount
        discounted_strike = strike * exp(-rate * maturity)
        density = exp(-0.5 * d1 * d1) / sqrt(2 * pi)
        sign = 1.0 if option_type == "call" else -1.0
        n1, n2 = _normal_cdf(sign * d1), _normal_cdf(sign * d2)
        result = Greeks(
            delta=sign * discount * n1,
            gamma=discount * density / spot / width,
            vega=discounted_spot * density * sqrt(maturity),
            theta=-discounted_spot * density * volatility / (2 * sqrt(maturity))
                  - sign * rate * discounted_strike * n2
                  + sign * dividend_yield * discounted_spot * n1,
            rho=sign * maturity * discounted_strike * n2,
        )
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("parameters exceed the supported floating-point range") from exc
    if not all(isfinite(value) for value in vars(result).values()):
        raise ValueError("parameters exceed the supported floating-point range")
    return result


def bsm_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    dividend_yield: float = 0.0,
    option_type: Literal["call", "put"] = "call",
) -> float:
    """Return a European call or put price per unit of the underlying asset.

    ``spot`` and ``strike`` must be strictly positive in the same currency.
    ``maturity`` is remaining time in years; ``volatility`` is annualized in
    decimal units (0.20 means 20%). Both must be nonnegative. ``rate`` and
    ``dividend_yield`` are constant, continuously compounded annual decimal
    rates and may be negative. All numeric inputs must be finite real scalars.
    ``option_type`` must be exactly "call" or "put".

    Assumes lognormal dynamics, constant parameters, frictionless markets and
    exercise only at maturity. At expiry return the intrinsic payoff; at zero
    volatility return the deterministic discounted payoff, without an epsilon.

    Raises:
        ValueError: For invalid inputs or intermediate values outside the
            supported floating-point range. Extreme tails may underflow to
            zero; cancellation can reduce relative accuracy for tiny prices.
    """
    spot, strike, maturity, rate, volatility, dividend_yield = _validate_inputs(
        spot, strike, maturity, rate, volatility, dividend_yield, option_type
    )

    sign = 1.0 if option_type == "call" else -1.0
    if maturity == 0.0:
        return max(sign * (spot - strike), 0.0)

    range_error = "parameters exceed the supported floating-point range"
    try:
        discounted_spot = spot * exp(-dividend_yield * maturity)
        discounted_strike = strike * exp(-rate * maturity)
    except OverflowError as exc:
        raise ValueError(range_error) from exc
    if not (isfinite(discounted_spot) and isfinite(discounted_strike)):
        raise ValueError(range_error)
    if volatility == 0.0:
        return max(sign * (discounted_spot - discounted_strike), 0.0)

    width = volatility * sqrt(maturity)
    if width == 0.0 or not isfinite(width):
        raise ValueError(range_error)
    # Subtract logs to avoid overflow/underflow in spot / strike, and avoid
    # squaring volatility in the usual expression for d1.
    center = (log(spot) - log(strike) + (rate - dividend_yield) * maturity) / width
    d1 = center + 0.5 * width
    d2 = center - 0.5 * width
    if not (isfinite(d1) and isfinite(d2)):
        raise ValueError(range_error)
    price = sign * (
        discounted_spot * _normal_cdf(sign * d1)
        - discounted_strike * _normal_cdf(sign * d2)
    )
    # Roundoff in the difference of two positive terms can produce a tiny
    # negative price; the mathematical formula is nonnegative.
    return max(price, 0.0)
