"""Print an offline signed-portfolio, shock and settlement validation report."""

import platform

from options_engine import (Bumps, FDConfig, Market, OptionContract, Portfolio, Position,
                            Scenario, scenario_pnl, value_portfolio)


def demo_inputs():
    market = Market(100, .20, .05, .02)
    book = Portfolio((
        Position(OptionContract(100, 1), 2, 100, label="long European call"),
        Position(OptionContract(95, .75, "put"), -1, 100, label="short European put"),
        Position(OptionContract(100, .25, "put", "american"), 1, 100, "fd",
                 FDConfig(320, 100, 400, tolerance=1e-10), bumps=Bumps(2.5, .005, .001, .005),
                 label="long American put"),
    ), cash=-1500)
    scenarios = [Scenario(label="unchanged"), Scenario(.5, label="spot only"),
        Scenario(volatility_change=.005, label="volatility only"), Scenario(rate_change=.001, label="rate only"),
        Scenario(elapsed=1/365, label="one calendar day"), Scenario(.5, .005, .001, 1/365, "small combined"),
        Scenario(-15, .05, .01, .1, "large combined"), Scenario(-10, elapsed=.25, label="American expiry"),
        Scenario(-10, elapsed=.5, label="after American expiry"), Scenario(-10, elapsed=.75, label="second expiry"),
        Scenario(10, elapsed=1.25, label="after all expiries")]
    return market, book, scenarios


def main() -> None:
    market, book, scenarios = demo_inputs()
    initial = value_portfolio(book, market)
    print("# Signed option portfolio and scenario P&L\n")
    print(f"Python {platform.python_version()}; {platform.system()} {platform.machine()}. Synthetic inputs only.")
    print("One underlying/currency: S=100, sigma=.20, r=.05, continuous q=.02.")
    print("Quantity signs represent long/short contracts; every multiplier=100.")
    print("American FD: M=320, Nt=100, Smax=400, Rannacher on, omega=1.2, PSOR tolerance=1e-10.")
    print("Absolute numerical bumps: spot=2.5, volatility=.005, rate=.001, maturity=.005 years.\n")
    print("## Initial holdings\n")
    print("| Leg | K | Years | Quantity | Multiplier | Unit price | Signed value |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for line in initial.positions:
        p = line.position
        print(f"| {p.label} | {p.contract.strike} | {p.contract.maturity} | {p.quantity} | {p.multiplier} | {line.unit_price:.8f} | {line.value:.6f} |")
    print(f"\nOption value={initial.option_value:.8f}; cash={initial.cash:.8f}; total={initial.total_value:.8f}.\n")
    print("## Aggregate option risk\n")
    print("Delta/Gamma differentiate spot; Vega/Rho per absolute unit; calendar Theta per year.")
    print("Cash has zero current option Greeks; its exact carry is added separately in scenario approximations.\n")
    print("| Delta | Gamma | Vega | Theta | Rho |")
    print("| ---: | ---: | ---: | ---: | ---: |")
    print("| " + " | ".join(f"{getattr(initial.greeks, n):.8f}" for n in ("delta", "gamma", "vega", "theta", "rho")) + " |")
    print("\n## Isolated and combined shocks\n")
    print("All changes are ABSOLUTE. Time is remaining calendar years elapsed, not a trading-day convention.")
    print("First order includes Delta/Vega/Rho/Theta plus exact initial cash carry. Second order adds Gamma*dS²/2.")
    print("Residual=full revaluation P&L minus approximation. N/A means expiry makes the local expansion inapplicable.\n")
    print("| Scenario | dS | dsigma | dr | Elapsed | Exact P&L | First order | Second order | Second residual |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    results = []
    def formatted(value):
        return "N/A" if value is None else f"{value:.6f}"
    for scenario in scenarios:
        r = scenario_pnl(book, market, scenario, initial=initial)
        results.append(r)
        print(f"| {scenario.label} | {scenario.spot_change} | {scenario.volatility_change} | {scenario.rate_change} | {scenario.elapsed:.8f} | "
              f"{r.exact_pnl:.6f} | {formatted(r.first_order_pnl)} | {formatted(r.second_order_pnl)} | {formatted(r.second_order_residual)} |")
    print("\n## Settlement and cash audit\n")
    print("Spot/rate/vol shocks occur immediately at time zero. The shocked spot remains flat until the horizon.")
    print("Each expiry therefore uses that explicitly specified spot; no terminal spot is retrospectively inferred")
    print("as an unobserved expiry price. Already-due options settle at original spot before shocks.")
    print("At expiry cash settlement equals signed quantity * multiplier * payoff. It accrues from its own expiry")
    print("to horizon at the shocked constant rate. Negative cash and short settlements accrue with the same convention.\n")
    print("| Scenario | Live option value | Initial cash FV | Settlement cash FV | Total cash | Horizon total |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for r in results[-4:]:
        print(f"| {r.scenario.label} | {r.option_value:.6f} | {r.initial_cash_at_horizon:.6f} | {r.settlement_cash_at_horizon:.6f} | {r.cash:.6f} | {r.total_value:.6f} |")
    print("\n| Scenario | Leg | Status | Expiry time | Settlement principal | Leg horizon value |")
    print("| --- | --- | --- | ---: | ---: | ---: |")
    for r in results[-4:]:
        for leg in r.positions:
            print(f"| {r.scenario.label} | {leg.position.label} | {leg.status} | {leg.settlement_time} | {leg.settlement_principal:.6f} | {leg.value_at_horizon:.6f} |")
    print("\n## Interpretation and limits\n")
    print("This is mark-to-market P&L from the initial valuation, not profit since a historical trade.")
    print("'Exact' means full repricing rather than Taylor; numerical solver errors and model assumptions remain.")
    print("Initial cash is supplied explicitly; purchase/sale premiums are not automatically booked.")
    print("Options are cash-settled, not physically delivered. American entitlement is repriced optimally")
    print("at endpoints, but no intermediate early exercise or short assignment transaction is simulated.")
    print("The hold-to-horizon/expiry policy is explicit; this is not optimal realized exercise P&L along a path.")
    print("The shocked spot path is a stress convention, not a simulated or risk-neutral prediction.")
    print("Dividends enter q in prices, not option-holder cash payments. No fees, margin, taxes or hedging trades.")
    print("The local expansion omits cross terms and higher orders; large shocks and frontier changes can produce large residuals.")
    print("FD interpolation and numerical-Greek noise also affect the residual, especially for small spot shocks.")
    print("No universal claim that adding Gamma improves every combined scenario is made.")
    print("Numerical Greek warnings propagate to the portfolio; one stable price does not certify stable risk.")
    print("The live FD positions retain r,q>=0 and their ORIGINAL spatial domain and controls across scenarios.")
    print("At/beyond any nonzero live position expiry, Taylor approximations are N/A, but exact settlement P&L remains defined.")


if __name__ == "__main__":
    main()
