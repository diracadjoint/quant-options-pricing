"""Immutable single-underlying contracts and market inputs."""

from dataclasses import dataclass
from typing import Literal

from .analytic import _validate_inputs


@dataclass(frozen=True)
class OptionContract:
    """Cash-settled vanilla option; maturity is remaining years at valuation."""

    strike: float
    maturity: float
    option_type: Literal["call", "put"] = "call"
    exercise_style: Literal["european", "american"] = "european"

    def __post_init__(self) -> None:
        _, strike, maturity, _, _, _ = _validate_inputs(1, self.strike, self.maturity, 0, 0, 0, self.option_type)
        if self.exercise_style not in ("european", "american"):
            raise ValueError("exercise_style must be european or american")
        object.__setattr__(self, "strike", strike)
        object.__setattr__(self, "maturity", maturity)


@dataclass(frozen=True)
class Market:
    """Common spot and constant annual decimal parameters for one underlying."""

    spot: float
    volatility: float
    rate: float
    dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        s, _, _, r, v, q = _validate_inputs(self.spot, 1, 0, self.rate, self.volatility, self.dividend_yield, "call")
        for name, value in (("spot", s), ("rate", r), ("volatility", v), ("dividend_yield", q)):
            object.__setattr__(self, name, value)
