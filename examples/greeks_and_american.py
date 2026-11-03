"""Print a reproducible Markdown validation report using synthetic inputs."""

import platform
from dataclasses import asdict
from time import perf_counter

from options_engine import bsm_greeks, bsm_price, crr_price


def main() -> None:
    print("# European Greeks and American CRR validation\n")
    print(f"Measured on Python {platform.python_version()}, {platform.system()} {platform.machine()}.")
    print("Timings depend on hardware and load; no market data is used.\n")
    print("## Analytic Greek check\n")
    print("S=K=100, remaining years=1, r=0.05, sigma=0.20, q=0.02; European call.\n")
    parameters = dict(spot=100, strike=100, maturity=1, rate=0.05,
                      volatility=0.20, dividend_yield=0.02)
    g = bsm_greeks(**parameters)
    print("| Greek | Analytic | Central difference | Absolute difference |")
    print("| --- | ---: | ---: | ---: |")
    base = bsm_price(**parameters)
    for name, field, bump, sign in [("delta", "spot", 0.01, 1),
                                    ("gamma", "spot", 0.01, 1),
                                    ("vega", "volatility", 1e-5, 1),
                                    ("theta", "maturity", 1e-5, -1),
                                    ("rho", "rate", 1e-5, 1)]:
        up = bsm_price(**{**parameters, field: parameters[field]+bump})
        down = bsm_price(**{**parameters, field: parameters[field]-bump})
        numeric = ((up-2*base+down)/bump**2 if name == "gamma"
                   else sign*(up-down)/(2*bump))
        analytic = asdict(g)[name]
        print(f"| {name} | {analytic:.10f} | {numeric:.10f} | {abs(analytic-numeric):.3g} |")
    print("\nSpot bump=0.01; other bumps=1e-5. Vega/Rho are per absolute unit;")
    print("Theta is per calendar year. Daily Theta=Theta/365; 1pp Vega/Rho=value/100.\n")
    print("## Tree refinement\n")
    print("S=K=100, remaining years=1, r=0.05, sigma=0.20, q=0.")
    print("European reference=BSM. Premium uses the European control on the same tree.\n")
    print("| Option | N | American | European tree | BSM | European error/K | Premium | Seconds |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for kind in ("call", "put"):
        reference = bsm_price(100, 100, 1, 0.05, 0.20, option_type=kind)
        for n in (100, 200, 400, 800):
            for steps in (n, n+1):
                start = perf_counter()
                result = crr_price(100, 100, 1, 0.05, 0.20, option_type=kind, steps=steps)
                seconds = perf_counter()-start
                print(f"| {kind} | {steps} | {result.price:.8f} | {result.european_price:.8f} | "
                      f"{reference:.8f} | {abs(result.european_price-reference)/100:.3g} | "
                      f"{result.early_exercise_premium:.8f} | {seconds:.4f} |")
    print("\nEven and odd sequences oscillate around their limits; refine them separately.")
    print("The non-dividend call has zero early-exercise premium. The put has a positive premium.")
    print("Tests require European error/K < 1e-3 at N=800/801, and the refined")
    print("American put within 0.003 of the standard 6.0896 benchmark at N=1600.")
    print("This is a limited benchmark, not an exhaustive parameter-domain accuracy guarantee.")
    print("No continuous exercise frontier or American Greeks are reported by this implementation.")


if __name__ == "__main__":
    main()
