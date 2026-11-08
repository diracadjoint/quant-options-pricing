"""Reproducible self-financing hedge comparisons on deterministic paths."""

import platform

from options_engine import (Bumps, FDConfig, Market, OptionContract, Portfolio, Position,
                            simulate_delta_hedge)


def main() -> None:
    market = Market(100, .20, .05, .02)
    portfolio = Portfolio((Position(OptionContract(100, 1), -1, 100),))
    paths = {
        "rise": [(i/64, 100+25*i/64) for i in range(65)],
        "fall": [(i/64, 100-25*i/64) for i in range(65)],
        "reversal": [(i/64, 100+50*min(i/64, 1-i/64)) for i in range(65)],
    }
    settings = [("unhedged", 1), ("static", 1), ("dynamic", 16), ("dynamic", 4), ("dynamic", 1)]
    results = {}
    print("# Static and dynamic self-financing Delta hedges\n")
    print(f"Python {platform.python_version()}; {platform.system()} {platform.machine()}. All inputs are synthetic.")
    print("Short ONE European call, multiplier 100, K=100, expiry=1 year. S0=100, sigma=.20, r=.05, q=.02.")
    print("Every strategy starts with wealth 1000; opening cash finances option/stock holdings at their initial marks.")
    print("Same 65 observations (64 intervals) for every frequency; only the stock trading schedule changes.")
    print("Rise: 100→125; fall: 100→75; reversal: 100→125→100. Spot is piecewise linear.")
    print("Cash compounds continuously; trapezoidal signed dividends are credited at each right endpoint.")
    print("No fees, spread, margin, stock rounding or stock-borrow fee. These are not simulated GBM paths.\n")
    print("## Strategy and rebalance-frequency comparison\n")
    print("Opening wealth capitalized at r is the same benchmark for all strategies.")
    print("Unhedged/static rows ignore rebalance_every; dynamic closes stock at expiry, without computing an expiry Delta.\n")
    print("| Path | Strategy | Every k observations | Delta decisions | Final wealth | Risk-free benchmark | Excess wealth | Max trade conservation error |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, path in paths.items():
        for strategy, k in settings:
            result = simulate_delta_hedge(portfolio, market, path, strategy=strategy,
                                          rebalance_every=k, initial_wealth=1000)
            results[name, strategy, k] = result
            decisions = sum(row.delta_used is not None for row in result.history)
            error = max(abs(row.rebalance_error) for row in result.history)
            print(f"| {name} | {strategy} | {k if strategy == 'dynamic' else 'N/A'} | {decisions} | "
                  f"{result.final_wealth:.8f} | {result.risk_free_wealth:.8f} | {result.excess_wealth:.8f} | {error:.3g} |")
    print("\n## P&L decomposition for every-observation dynamic hedges\n")
    print("Option P&L includes signed payoffs on settlement. Stock P&L is the gain on shares held over intervals;")
    print("trades change cash and inventory equally and do not themselves create wealth.\n")
    print("| Path | Option P&L | Stock P&L | Dividends | Financing | Total P&L | Max interval reconciliation error |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name in paths:
        r = results[name, "dynamic", 1]
        print(f"| {name} | {r.option_pnl:.8f} | {r.stock_pnl:.8f} | {r.dividends:.8f} | {r.financing:.8f} | "
              f"{r.pnl:.8f} | {max(abs(row.reconciliation_error) for row in r.history):.3g} |")
    print("\n## Opening and full trade/cash audit on a separate coarse rise path\n")
    print("This audit uses five observations, not the common 65-point grid above. All interval flows are shown.")
    audit = simulate_delta_hedge(portfolio, market, [(i/4, 100+25*i/4) for i in range(5)], initial_wealth=1000)
    print(f"Opening cash adjustment vs original portfolio NAV={audit.opening_cash_adjustment:.8f}.")
    print("Opening cash BEFORE stock = initial wealth - signed option mark; AFTER stock additionally subtracts H*S.\n")
    print("| Time | Spot | Option value | Delta used | Shares before | Shares after | Trade cost | Wealth before trade | Wealth after trade |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in audit.history:
        delta = "not needed" if row.delta_used is None else f"{row.delta_used:.8f}"
        print(f"| {row.time} | {row.spot} | {row.option_value:.8f} | {delta} | {row.shares_before:.8f} | "
              f"{row.shares_after:.8f} | {row.trade_cost:.8f} | {row.wealth_before_trade:.8f} | {row.wealth:.8f} |")
    print("\n| Time | Dividends | Financing | Settlement | Cash before trade | Cash after trade | Action |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in audit.history:
        print(f"| {row.time} | {row.dividends:.8f} | {row.financing:.8f} | {row.settlement_cash:.8f} | "
              f"{row.cash_before_trade:.8f} | {row.cash:.8f} | {row.action} |")
    print("\n## Mixed portfolio including an American FD position\n")
    mixed = Portfolio((Position(OptionContract(100, 1), -1, 10),
                       Position(OptionContract(100, .5, "put", "american"), 1, 10, "fd",
                                FDConfig(80, 40, 400, tolerance=1e-10), bumps=Bumps(1, .005, .001, .01))))
    r = simulate_delta_hedge(mixed, market, [(0, 100), (.25, 98), (.75, 105), (1, 110)],
                             initial_wealth=1000, warning_policy="allow")
    print("American policy: HOLD TO EXPIRY, no early exercise or assignment. Rights and risk refresh at every observation/event.")
    print("FD domain/grid fixed at Smax=400, M=80, Nt=40; residual tolerance=1e-10; spot bump=1 < dS=5.")
    print("The coarse numerical warning is deliberate: default 'raise' would reject it; explicit 'allow' marks decisions.")
    print("Expiry at .5 is inserted by linear interpolation, independently of the requested rebalance schedule.\n")
    print("| Time | Spot | Delta used | Shares after | Warned decision | Numerical repricings retained | Warnings |")
    print("| ---: | ---: | ---: | ---: | --- | ---: | --- |")
    for row in r.history:
        trace = sum(len(line.numerical_risk.repricings) for line in row.valuation.positions if line.numerical_risk is not None)
        delta = "not needed" if row.delta_used is None else f"{row.delta_used:.8f}"
        print(f"| {row.time} | {row.spot} | {delta} | {row.shares_after:.8f} | {row.used_warned_delta} | {trace} | {'; '.join(row.warnings) or 'none'} |")
    print(f"\nMixed-portfolio final wealth={r.final_wealth:.8f}; risk-free benchmark={r.risk_free_wealth:.8f}; excess={r.excess_wealth:.8f}.\n")
    print("## Interpretation and limits\n")
    print("The paths are deterministic stress examples, not a statistical assessment of hedge quality.")
    print("More frequent rebalancing need not improve excess wealth on every individual path; no monotonicity is imposed.")
    print("Refining trades along a smooth deterministic path does not reproduce BSM diffusion quadratic variation; excess need not tend to zero.")
    print("Initial wealth is controlled across strategies. If omitted, initial wealth defaults to the original option-book NAV including cash.")
    print("Financing applies to signed cash; stock dividends include payments on short shares. Dividends receive no intra-interval interest.")
    print("This discrete dividend-credit convention has timing error, even though trapezoidal integration is exact on linear spot segments with fixed shares.")
    print("At expiry, options cash-settle at interpolated path spot and disappear; stock closes when all options expire or at final horizon.")
    print("Cash continues accruing after the last expiry. Live options at a shorter horizon remain marked, with a warning; stock still closes.")
    print("American early-exercise/assignment path modeling is explicitly outside this hold-to-expiry demonstration.")
    print("Unavailable Delta always raises; numerical warnings raise by default or are explicitly allowed and preserved in history.")
    print("A self-financing ledger identity is not a proof that the Delta estimates or market model are accurate.")


if __name__ == "__main__":
    main()
