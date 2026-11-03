"""Independent Cox–Ross–Rubinstein pricing with O(N) memory."""

from dataclasses import dataclass
from math import exp, expm1, isfinite, log, sqrt
from numbers import Integral
from typing import Literal

from .analytic import _validate_inputs


@dataclass(frozen=True)
class BinomialResult:
    """Tree price and European control on exactly the same lattice.

    Refinement must establish price accuracy; a single tree cannot certify
    convergence. Probability is None in expiry/deterministic branches.
    """

    price: float
    european_price: float
    steps: int
    probability: float | None
    method: str

    @property
    def early_exercise_premium(self) -> float:
        """Premium over the European control, not over a different solver."""
        return self.price - self.european_price


def crr_price(
    spot: float, strike: float, maturity: float, rate: float,
    volatility: float, dividend_yield: float = 0.0,
    option_type: Literal["call", "put"] = "call", *,
    exercise_style: Literal["european", "american"] = "american",
    steps: int = 500,
) -> BinomialResult:
    """Price vanilla European/American options under constant BSM dynamics.

    Units and scalar domains match bsm_price, including negative rates/yields.
    CRR checks 0 <= probability <= 1 and rejects invalid step counts or a
    lattice violating this condition; increase steps rather than clipping p.
    American exercise is allowed at tree dates, approximating continuous
    exercise under refinement. Runtime O(steps**2), memory O(steps).
    At zero volatility maximize discounted payoff over continuous exercise
    time, including interior stationary points, without constructing a tree.
    Numerical range errors raise ValueError; no convergence claim is made.
    """
    spot, strike, maturity, rate, volatility, dividend_yield = _validate_inputs(
        spot, strike, maturity, rate, volatility, dividend_yield, option_type
    )
    if isinstance(steps, bool) or not isinstance(steps, Integral) or steps < 1:
        raise ValueError("steps must be a positive integer")
    steps = int(steps)
    if not isinstance(exercise_style, str) or exercise_style not in ("european", "american"):
        raise ValueError('exercise_style must be "european" or "american"')
    sign = 1.0 if option_type == "call" else -1.0

    def discounted_payoff(time: float) -> float:
        return max(sign * (spot * exp(-dividend_yield * time)
                           - strike * exp(-rate * time)), 0.0)

    try:
        european = discounted_payoff(maturity)
        if maturity == 0 or volatility == 0:
            candidates = [0.0, maturity]
            if ((rate > 0 and dividend_yield > 0) or (rate < 0 and dividend_yield < 0)) and rate != dividend_yield:
                stationary = (log(abs(rate)) + log(strike)
                              - log(abs(dividend_yield)) - log(spot)) / (rate - dividend_yield)
                if 0 < stationary < maturity:
                    candidates.append(stationary)
            price = (max(discounted_payoff(t) for t in candidates)
                     if exercise_style == "american" else european)
            if not (isfinite(price) and isfinite(european)):
                raise ValueError("parameters exceed the supported floating-point range")
            return BinomialResult(price, european, steps, None, "deterministic")

        dt = maturity / steps
        width = volatility * sqrt(dt)
        if width == 0 or not isfinite(width):
            raise ValueError("parameters exceed the supported floating-point range")
        # Algebraically equivalent to (exp((r-q)dt)-d)/(u-d), using expm1
        # to reduce cancellation at small dt.
        probability = expm1((rate - dividend_yield) * dt + width) / expm1(2 * width)
        if not isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("CRR probability outside [0, 1]; increase steps")
        discount = exp(-rate * dt)
        log_spot = log(spot)

        def payoff(level: int, node: int) -> float:
            return max(sign * (exp(log_spot + (2 * node - level) * width) - strike), 0.0)

        values = [payoff(steps, j) for j in range(steps + 1)]
        controls = values.copy()
        for level in range(steps - 1, -1, -1):
            for j in range(level + 1):
                controls[j] = discount * ((1 - probability) * controls[j] + probability * controls[j + 1])
                continuation = discount * ((1 - probability) * values[j] + probability * values[j + 1])
                values[j] = (max(payoff(level, j), continuation)
                             if exercise_style == "american" else continuation)
        if not (isfinite(values[0]) and isfinite(controls[0])):
            raise ValueError("parameters exceed the supported floating-point range")
        return BinomialResult(values[0], controls[0], steps, probability, "crr")
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("parameters exceed the supported floating-point range") from exc
