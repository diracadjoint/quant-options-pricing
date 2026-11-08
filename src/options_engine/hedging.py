"""Self-financing Delta hedges on supplied piecewise-linear spot paths."""

from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass, replace
from math import expm1
from numbers import Integral
from typing import Literal

from .analytic import _finite_real, bsm_price
from .contracts import Market
from .finite_difference import FDConfig
from .portfolio import Portfolio, PortfolioValue, _checked, _future_value, _sum, value_portfolio


class DeltaUnavailableError(ValueError):
    """A requested hedge decision has no available aggregate Delta."""

    def __init__(self, message: str, time: float, valuation: PortfolioValue):
        super().__init__(message)
        self.time, self.valuation = time, valuation


class DeltaWarningError(ValueError):
    """Strict warning policy rejected a warned hedge decision."""

    def __init__(self, message: str, time: float, valuation: PortfolioValue):
        super().__init__(message)
        self.time, self.valuation = time, valuation


@dataclass(frozen=True)
class PathPoint:
    """Observation time in years from valuation and strictly positive spot."""

    time: float
    spot: float

    def __post_init__(self) -> None:
        t, s = _finite_real("path time", self.time), _finite_real("path spot", self.spot)
        if t < 0 or s <= 0:
            raise ValueError("path times must be nonnegative and spots strictly positive")
        object.__setattr__(self, "time", t)
        object.__setattr__(self, "spot", s)


@dataclass(frozen=True)
class HedgeSettlement:
    position_index: int
    time: float
    spot: float
    units: float
    unit_payoff: float
    amount: float


@dataclass(frozen=True)
class HedgeRow:
    """Post-trade account, interval gains and pre/post trade reconciliation.

    Dividends and financing relate to the preceding interval. Option P&L
    includes settlement cash so extinguishing an option is not a loss twice.
    Opening option P&L and interval flows are zero, even for already-due legs.
    Delta is None when no Delta decision was requested; it is never silently
    substituted for an unavailable Delta. valuation retains risk diagnostics.
    """

    time: float
    spot: float
    action: str
    option_value: float
    delta_used: float | None
    shares_before: float
    shares_after: float
    trade_cost: float
    dividends: float
    financing: float
    settlement_cash: float
    cash_before_trade: float
    cash: float
    wealth_before_trade: float
    wealth: float
    rebalance_error: float
    option_pnl: float
    stock_pnl: float
    wealth_change: float
    reconciliation_error: float
    used_warned_delta: bool
    warnings: tuple[str, ...]
    settlements: tuple[HedgeSettlement, ...]
    valuation: PortfolioValue


@dataclass(frozen=True)
class HedgeResult:
    strategy: str
    rebalance_every: int
    warning_policy: str
    american_policy: str
    path: tuple[PathPoint, ...]
    history: tuple[HedgeRow, ...]
    initial_wealth: float
    opening_cash_adjustment: float
    final_wealth: float
    risk_free_wealth: float
    excess_wealth: float
    pnl: float
    option_pnl: float
    stock_pnl: float
    dividends: float
    financing: float


def simulate_delta_hedge(
    portfolio: Portfolio, market: Market,
    path: Iterable[PathPoint | tuple[float, float]], *,
    strategy: Literal["unhedged", "static", "dynamic"] = "dynamic",
    rebalance_every: int = 1,
    initial_wealth: float | None = None,
    warning_policy: Literal["raise", "allow"] = "raise",
) -> HedgeResult:
    """Compare self-financing strategies with fixed sigma, r and q.

    Path starts at t=0 and market.spot; times strictly increase. Linear spot
    interpolation inserts every nonzero position expiry within the horizon.
    Dynamic hedge decisions occur at original observations [::rebalance_every]
    plus expiry events; static hedges only at opening. Stock is closed when
    all options expire or at final horizon (live options then remain marked).

    Opening cash = initial wealth - live option value - target shares*spot.
    If initial_wealth is None, preserve original portfolio NAV including cash
    and already-due payoffs. An explicit endowment overrides that NAV, with
    its opening cash adjustment reported. No external flows occur thereafter.

    Each interval holds shares fixed. Old cash accrues at exp(r*dt). Signed
    dividends q*H*(S_left+S_right)/2*dt are credited at the RIGHT endpoint:
    trapezoidal spot integration, with no intra-interval dividend interest.
    Settle options at expiry, then trade shares at current spot. American
    rights are repriced, but held to expiry: no early exercise/assignment.

    All risk flags/diagnostics at decisions remain in the snapshot/history.
    Default policy rejects warned decisions. 'allow' uses them with an explicit
    marker; an unavailable Delta always raises. Solver failures propagate.
    FD domains and all controls are frozen from the original spot.
    """
    if not isinstance(portfolio, Portfolio) or not isinstance(market, Market):
        raise ValueError("expected Portfolio and Market")
    if strategy not in ("unhedged", "static", "dynamic"):
        raise ValueError("strategy must be unhedged, static or dynamic")
    if warning_policy not in ("raise", "allow"):
        raise ValueError("warning_policy must be raise or allow")
    if isinstance(rebalance_every, bool) or not isinstance(rebalance_every, Integral) or rebalance_every < 1:
        raise ValueError("rebalance_every must be a positive integer")
    try:
        points = tuple(p if isinstance(p, PathPoint) else PathPoint(*p) for p in path)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid path: {exc}") from exc
    if len(points) < 2 or points[0].time != 0 or points[0].spot != market.spot:
        raise ValueError("path needs at least two points, starting at (0, market.spot)")
    if any(b.time <= a.time for a, b in zip(points, points[1:])):
        raise ValueError("path times must be strictly increasing")
    supplied_wealth = None if initial_wealth is None else _finite_real("initial_wealth", initial_wealth)
    horizon = points[-1].time
    original_times = tuple(p.time for p in points)
    schedule = set(original_times[::int(rebalance_every)])
    fixed_positions = []
    for p in portfolio.positions:
        if p.method == "fd":
            cfg = p.fd_config or FDConfig()
            p = replace(p, fd_config=replace(cfg, s_max=cfg.s_max if cfg.s_max is not None else 4*max(market.spot, p.contract.strike)))
        fixed_positions.append(p)
    expiries = {p.contract.maturity for p in fixed_positions if p.units != 0 and p.contract.maturity <= horizon}
    event_times = sorted(set(original_times) | expiries)

    def spot_at(t: float) -> float:
        i = bisect_left(original_times, t)
        if i < len(points) and original_times[i] == t:
            return points[i].spot
        left, right = points[i-1], points[i]
        weight = (t-left.time)/(right.time-left.time)
        return _checked((1-weight)*left.spot+weight*right.spot)

    rows = []
    cash = shares = wealth0 = adjustment = 0.0
    for index, t in enumerate(event_times):
        spot = spot_at(t)
        current_market = replace(market, spot=spot)
        active = tuple(replace(p, contract=replace(p.contract, maturity=p.contract.maturity-t))
                       for p in fixed_positions if p.units != 0 and p.contract.maturity > t)
        final = t == horizon
        decision = bool(active) and not final and (index == 0 and strategy != "unhedged" or
                    strategy == "dynamic" and (t in schedule or t in expiries))
        # Refresh rights and risk at every observation/event, even when a
        # static/sparse strategy holds inventory rather than using that Delta.
        valuation = value_portfolio(Portfolio(active), current_market, compute_greeks=bool(active))
        warnings = valuation.flags
        delta = None
        warned = False
        before = shares
        if decision:
            delta = valuation.greeks.delta
            if delta is None:
                raise DeltaUnavailableError(f"aggregate Delta unavailable at time {t}; no hedge decision made", t, valuation)
            if warnings and warning_policy == "raise":
                raise DeltaWarningError(f"warned risk at time {t}: {'; '.join(warnings)}", t, valuation)
            warned = bool(warnings)
            target = _checked(-delta)
            action = "open_hedge" if index == 0 else "rebalance"
        elif final or not active:
            target = 0.0
            action = "horizon_stock_liquidation" if final else "expiry_stock_liquidation"
            if final and active:
                warnings = (*warnings, "horizon precedes option expiry: live options remain marked")
        else:
            target = shares
            action = "open_unhedged" if index == 0 else "hold"
        settlements = []
        for position_index, p in enumerate(fixed_positions):
            if p.units != 0 and p.contract.maturity == t:
                payoff = bsm_price(spot, p.contract.strike, 0, market.rate, market.volatility,
                                   market.dividend_yield, p.contract.option_type)
                settlements.append(HedgeSettlement(position_index, t, spot, p.units, payoff, _checked(p.units*payoff)))
        settled = _sum(s.amount for s in settlements)
        dividends = financing = option_pnl = stock_pnl = change = reconciliation = 0.0
        if index == 0:
            inherited_nav = _sum((valuation.option_value, portfolio.cash, settled))
            wealth0 = inherited_nav if supplied_wealth is None else supplied_wealth
            adjustment = _checked(wealth0-inherited_nav)
            cash_before = _sum((wealth0, -valuation.option_value))
        else:
            previous = rows[-1]
            dt = t-previous.time
            try:
                financing = _checked(cash*expm1(market.rate*dt))
            except OverflowError as exc:
                raise ValueError("hedge financing exceeds floating-point range") from exc
            dividends = _checked(market.dividend_yield*before*(.5*previous.spot+.5*spot)*dt)
            cash_before = _sum((cash, financing, dividends, settled))
            option_pnl = _sum((valuation.option_value, -previous.option_value, settled))
            stock_pnl = _checked(before*(spot-previous.spot))
        wealth_before = _sum((valuation.option_value, _checked(before*spot), cash_before))
        cost = _checked((target-before)*spot)
        cash = _sum((cash_before, -cost))
        shares = target
        wealth = _sum((valuation.option_value, _checked(shares*spot), cash))
        error = _checked(wealth-wealth_before)
        if index:
            change = _checked(wealth-rows[-1].wealth)
            reconciliation = _checked(change-_sum((option_pnl, stock_pnl, dividends, financing)))
        rows.append(HedgeRow(t, spot, action, valuation.option_value, delta, before, shares, cost,
                             dividends, financing, settled, cash_before, cash, wealth_before, wealth,
                             error, option_pnl, stock_pnl, change, reconciliation, warned,
                             warnings, tuple(settlements), valuation))
    totals = {name: _sum(getattr(row, name) for row in rows[1:])
              for name in ("option_pnl", "stock_pnl", "dividends", "financing")}
    benchmark = _future_value(wealth0, market.rate, horizon)
    final_wealth = rows[-1].wealth
    return HedgeResult(strategy, int(rebalance_every), warning_policy, "hold_to_expiry_no_early_assignment",
                       points, tuple(rows), wealth0, adjustment, final_wealth, benchmark,
                       _checked(final_wealth-benchmark), _checked(final_wealth-wealth0), **totals)
