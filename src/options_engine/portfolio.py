"""Signed option positions, aggregate risk and deterministic shock scenarios."""

from dataclasses import dataclass, replace
from collections.abc import Iterable
from math import exp, fsum, isfinite
from numbers import Integral
from typing import Literal

from .analytic import GreeksUnavailableError, _finite_real, bsm_greeks, bsm_price
from .binomial import crr_price
from .contracts import Market, OptionContract
from .finite_difference import FDConfig, fd_price
from .risk import Bumps, NumericalGreeks, numerical_greeks


NAMES = ("delta", "gamma", "vega", "theta", "rho")


def _checked(value: float) -> float:
    if not isfinite(value):
        raise ValueError("portfolio calculation exceeds floating-point range")
    return value


def _sum(values: Iterable[float]) -> float:
    try:
        return _checked(fsum(values))
    except OverflowError as exc:
        raise ValueError("portfolio calculation exceeds floating-point range") from exc


def _future_value(amount: float, rate: float, years: float) -> float:
    if amount == 0:
        return 0.0
    try:
        return _checked(amount*exp(rate*years))
    except OverflowError as exc:
        raise ValueError("cash accrual exceeds floating-point range") from exc


@dataclass(frozen=True)
class Position:
    """Positive quantity buys contracts, negative sells; multiplier is positive.

    Finite fractional quantities are allowed. BSM applies only to Europeans.
    FD/CRR risk uses the existing numerical-Greek API and retains its warnings.
    """

    contract: OptionContract
    quantity: float = 1.0
    multiplier: float = 1.0
    method: Literal["bsm", "fd", "crr"] = "bsm"
    fd_config: FDConfig | None = None
    tree_steps: int = 500
    bumps: Bumps | None = None
    label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.contract, OptionContract):
            raise ValueError("contract must be OptionContract")
        quantity = _finite_real("quantity", self.quantity)
        multiplier = _finite_real("multiplier", self.multiplier)
        if multiplier <= 0:
            raise ValueError("multiplier must be positive")
        _checked(quantity*multiplier)
        if self.method not in ("bsm", "fd", "crr"):
            raise ValueError("method must be bsm, fd or crr")
        if self.method == "bsm" and self.contract.exercise_style != "european":
            raise ValueError("BSM cannot price American positions; select fd or crr")
        if self.fd_config is not None and (self.method != "fd" or not isinstance(self.fd_config, FDConfig)):
            raise ValueError("fd_config requires method=fd and FDConfig")
        if isinstance(self.tree_steps, bool) or not isinstance(self.tree_steps, Integral) or self.tree_steps < 1:
            raise ValueError("tree_steps must be a positive integer")
        if self.bumps is not None and not isinstance(self.bumps, Bumps):
            raise ValueError("bumps must be Bumps")
        if self.bumps is not None:
            normalized = {}
            for name in ("spot", "volatility", "rate", "maturity"):
                supplied = getattr(self.bumps, name)
                normalized[name] = None if supplied is None else _finite_real(f"bumps.{name}", supplied)
                if normalized[name] is not None and normalized[name] <= 0:
                    raise ValueError(f"bumps.{name} must be positive")
            object.__setattr__(self, "bumps", Bumps(**normalized))
        if not isinstance(self.label, str):
            raise ValueError("label must be a string")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "multiplier", multiplier)
        object.__setattr__(self, "tree_steps", int(self.tree_steps))

    @property
    def units(self) -> float:
        return self.quantity*self.multiplier


@dataclass(frozen=True)
class Portfolio:
    """One underlying/currency; cash can be negative to represent borrowing."""

    positions: tuple[Position, ...] = ()
    cash: float = 0.0

    def __post_init__(self) -> None:
        try:
            positions = tuple(self.positions)
        except TypeError as exc:
            raise ValueError("positions must be an iterable of Position") from exc
        if not all(isinstance(p, Position) for p in positions):
            raise ValueError("positions must contain only Position")
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "cash", _finite_real("cash", self.cash))


@dataclass(frozen=True)
class PortfolioGreeks:
    """Exposure units include quantity/multiplier; None means unavailable.

    Theta is per calendar year; Vega/Rho per absolute volatility/rate unit.
    Cash has zero current option Greeks; future cash carry is handled separately.
    """

    delta: float | None = 0.0
    gamma: float | None = 0.0
    vega: float | None = 0.0
    theta: float | None = 0.0
    rho: float | None = 0.0


@dataclass(frozen=True)
class PositionValue:
    position: Position
    unit_price: float
    value: float
    unit_greeks: PortfolioGreeks
    status: str
    fixed_fd_config: FDConfig | None
    numerical_risk: NumericalGreeks | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioValue:
    portfolio: Portfolio
    market: Market
    positions: tuple[PositionValue, ...]
    option_value: float
    cash: float
    total_value: float
    greeks: PortfolioGreeks
    flags: tuple[str, ...]


def _inputs(contract: OptionContract, market: Market) -> dict:
    return dict(spot=market.spot, strike=contract.strike, maturity=contract.maturity,
                rate=market.rate, volatility=market.volatility,
                dividend_yield=market.dividend_yield, option_type=contract.option_type)


def _price(position: Position, contract: OptionContract, market: Market, config: FDConfig | None) -> float:
    inputs = _inputs(contract, market)
    if position.method == "bsm":
        return bsm_price(**inputs)
    if position.method == "fd":
        return fd_price(**inputs, exercise_style=contract.exercise_style, config=config).price
    return crr_price(**inputs, exercise_style=contract.exercise_style, steps=position.tree_steps).price


def _risk_key(position: Position, config: FDConfig | None) -> tuple:
    key = position.contract, position.method, config, position.tree_steps, position.bumps
    try:
        hash(key)
    except TypeError as exc:
        raise ValueError("pricing configuration must contain valid scalar controls") from exc
    return key


def value_portfolio(portfolio: Portfolio, market: Market, *, compute_greeks: bool = True) -> PortfolioValue:
    """Aggregate n*m*V and n*m*G; retain numerical diagnostics per unique leg.

    Contracts already at expiry settle at the ORIGINAL spot into current cash
    before any subsequent shock; they carry zero remaining option exposure.
    Zero quantities are skipped. Exact opposite exposures cancel even if their
    unit Greeks are unavailable; other unavailable components propagate None.
    """
    if not isinstance(portfolio, Portfolio) or not isinstance(market, Market):
        raise ValueError("expected Portfolio and Market")
    if not isinstance(compute_greeks, bool):
        raise ValueError("compute_greeks must be bool")
    lines, cache, groups = [], {}, {}
    for position in portfolio.positions:
        contract = position.contract
        config = None
        if position.method == "fd":
            cfg = position.fd_config or FDConfig()
            config = replace(cfg, s_max=cfg.s_max if cfg.s_max is not None else 4*max(market.spot, contract.strike))
        if position.units == 0:
            lines.append(PositionValue(position, 0, 0, PortfolioGreeks(), "zero", config, None, ()))
            continue
        if contract.maturity == 0:
            unit = bsm_price(**_inputs(contract, market))
            lines.append(PositionValue(position, unit, _checked(position.units*unit), PortfolioGreeks(),
                                       "settled", config, None, ()))
            continue
        key = _risk_key(position, config)
        if key not in cache:
            risk, flags = None, ()
            if not compute_greeks:
                unit = _price(position, contract, market, config)
                greek = PortfolioGreeks(*([None]*5))
                flags = ("Greeks not computed",)
            elif position.method == "bsm":
                unit = bsm_price(**_inputs(contract, market))
                try:
                    g = bsm_greeks(**_inputs(contract, market))
                    greek = PortfolioGreeks(*(getattr(g, name) for name in NAMES))
                except GreeksUnavailableError:
                    greek = PortfolioGreeks(*([None]*5))
                    flags = ("analytic Greeks unavailable at zero volatility",)
            else:
                risk = numerical_greeks(**_inputs(contract, market), method=position.method,
                                        exercise_style=contract.exercise_style, bumps=position.bumps,
                                        fd_config=config, tree_steps=position.tree_steps)
                unit = risk.price
                greek = PortfolioGreeks(*(getattr(risk, name).value for name in NAMES))
                flags = tuple(dict.fromkeys(flag for name in NAMES for flag in getattr(risk, name).flags))
            cache[key] = unit, greek, risk, flags
        unit, greek, risk, flags = cache[key]
        lines.append(PositionValue(position, unit, _checked(position.units*unit), greek, "active", config, risk, flags))
        groups.setdefault(key, []).append(position.units)
    exposure = {}
    for name in NAMES:
        terms, unavailable = [], False
        for key, quantities in groups.items():
            units = _sum(quantities)
            if units == 0:
                continue
            value = getattr(cache[key][1], name)
            if value is None:
                unavailable = True
            else:
                terms.append(_checked(units*value))
        exposure[name] = None if unavailable else _sum(terms)
    option_value = _sum(line.value for line in lines if line.status == "active")
    cash = _sum([portfolio.cash, *(line.value for line in lines if line.status == "settled")])
    flags = tuple(dict.fromkeys(flag for line in lines for flag in line.flags))
    return PortfolioValue(portfolio, market, tuple(lines), option_value, cash,
                          _sum((option_value, cash)), PortfolioGreeks(**exposure), flags)


@dataclass(frozen=True)
class Scenario:
    """Absolute shocks at horizon start; elapsed time is nonnegative years.

    The shocked spot stays flat until the horizon, including intermediate
    expiries. This is an explicit deterministic stress convention, not a GBM
    simulation or an inferred price at an unobserved intermediate expiry.
    """

    spot_change: float = 0.0
    volatility_change: float = 0.0
    rate_change: float = 0.0
    elapsed: float = 0.0
    label: str = ""

    def __post_init__(self) -> None:
        for name in ("spot_change", "volatility_change", "rate_change", "elapsed"):
            object.__setattr__(self, name, _finite_real(name, getattr(self, name)))
        if self.elapsed < 0:
            raise ValueError("elapsed must be nonnegative")
        if not isinstance(self.label, str):
            raise ValueError("label must be a string")


@dataclass(frozen=True)
class ScenarioLeg:
    position: Position
    status: str
    remaining_maturity: float
    unit_price: float
    value_at_horizon: float
    settlement_time: float | None
    settlement_principal: float


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    initial: PortfolioValue
    shocked_market: Market
    positions: tuple[ScenarioLeg, ...]
    option_value: float
    initial_cash_at_horizon: float
    settlement_cash_at_horizon: float
    cash: float
    total_value: float
    exact_pnl: float
    first_order_pnl: float | None
    second_order_pnl: float | None
    first_order_residual: float | None
    second_order_residual: float | None
    flags: tuple[str, ...]


def scenario_pnl(portfolio: Portfolio, market: Market, scenario: Scenario, *,
                 initial: PortfolioValue | None = None) -> ScenarioResult:
    """Full repricing and local Greek approximations under explicit cash policy.

    Cash-settle at payoff when elapsed>=maturity; accrue each signed settlement
    from its own expiry to horizon at the shocked constant rate. Existing cash
    accrues over the whole horizon at the same rate (negative cash is borrowing).
    Already-due contracts settle at original spot before the instantaneous
    shock. American options are held until the horizon/expiry: no intervening
    early-exercise transaction is simulated. Repricing still values the full
    American entitlement at each endpoint. No dividends on options are paid
    to cash; q enters option prices only. No fees, margin or trade history.

    Approximation = Delta*dS + Vega*dsigma + Rho*dr + Theta*elapsed,
    plus exact carry on initial effective cash; second order adds Gamma*dS²/2.
    Cross terms and higher orders are omitted. If a nonzero live position
    reaches expiry, approximations are unavailable; exact P&L remains defined.
    'Exact' means full repricing rather than Taylor; numerical solver errors
    and model assumptions still apply.
    FD domains and solver controls are frozen from the original valuation.
    """
    if not isinstance(scenario, Scenario):
        raise ValueError("scenario must be Scenario")
    if initial is None:
        initial = value_portfolio(portfolio, market)
    elif not isinstance(initial, PortfolioValue) or initial.portfolio != portfolio or initial.market != market:
        raise ValueError("initial valuation must match portfolio and market")
    shocked = Market(_checked(market.spot+scenario.spot_change),
                     _checked(market.volatility+scenario.volatility_change),
                     _checked(market.rate+scenario.rate_change), market.dividend_yield)
    legs, live_values, settlements = [], [], []
    flags = list(initial.flags)
    crosses_expiry = False
    for line in initial.positions:
        p, contract = line.position, line.position.contract
        remaining = max(contract.maturity-scenario.elapsed, 0.0)
        if p.units == 0:
            legs.append(ScenarioLeg(p, "zero", remaining, 0, 0, None, 0))
        elif line.status == "settled" or scenario.elapsed >= contract.maturity:
            unit = line.unit_price if line.status == "settled" else bsm_price(
                shocked.spot, contract.strike, 0, shocked.rate, shocked.volatility,
                shocked.dividend_yield, contract.option_type)
            principal = _checked(p.units*unit)
            value = _future_value(principal, shocked.rate, scenario.elapsed-contract.maturity)
            settlements.append(value)
            status = "already_settled" if line.status == "settled" else "settled"
            crosses_expiry = crosses_expiry or status == "settled"
            legs.append(ScenarioLeg(p, status, 0, unit, value, contract.maturity, principal))
        else:
            unit = _price(p, replace(contract, maturity=remaining), shocked, line.fixed_fd_config)
            value = _checked(p.units*unit)
            live_values.append(value)
            legs.append(ScenarioLeg(p, "active", remaining, unit, value, None, 0))
    option_value = _sum(live_values)
    initial_cash = _future_value(portfolio.cash, shocked.rate, scenario.elapsed)
    settlement_cash = _sum(settlements)
    cash = _sum((initial_cash, settlement_cash))
    total = _sum((cash, option_value))
    pnl = _checked(total-initial.total_value)
    cash_carry = _checked(_future_value(initial.cash, shocked.rate, scenario.elapsed)-initial.cash)
    first, second = None, None
    if crosses_expiry:
        flags.append("expiry reached: local Greek approximation unavailable")
    else:
        terms, missing = [cash_carry], False
        for name, shock in (("delta", scenario.spot_change), ("vega", scenario.volatility_change),
                            ("rho", scenario.rate_change), ("theta", scenario.elapsed)):
            if shock == 0:
                continue
            greek = getattr(initial.greeks, name)
            if greek is None:
                missing = True
            else:
                terms.append(_checked(greek*shock))
        if not missing:
            first = _sum(terms)
            gamma = initial.greeks.gamma
            if scenario.spot_change == 0:
                second = first
            elif gamma is not None:
                second = _sum((first, _checked(.5*gamma*scenario.spot_change*scenario.spot_change)))
        if first is None or second is None:
            flags.append("required Greek unavailable: approximation omitted")
    return ScenarioResult(scenario, initial, shocked, tuple(legs), option_value, initial_cash,
                          settlement_cash, cash, total, pnl, first, second,
                          None if first is None else _checked(pnl-first),
                          None if second is None else _checked(pnl-second), tuple(dict.fromkeys(flags)))
