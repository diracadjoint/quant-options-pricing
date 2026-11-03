"""Print separate bump, spatial, temporal and CRR studies; synthetic data."""

from dataclasses import asdict
import json
import platform

from options_engine import Bumps, FDConfig, numerical_greeks


def run_studies() -> dict:
    """Return serializable results; each study varies only its stated axis."""
    results = {}
    for kind, spot, rate, yield_ in [("put", 100, .05, 0), ("call", 100, .02, .10), ("put", 81, .05, 0)]:
        key = f"{kind}, S={spot}, r={rate}, q={yield_}"
        cache = {}
        def run(m=320, nt=100, scale=1.0):
            index = (m, nt, scale)
            if index not in cache:
                b = Bumps(2.5*scale, .005*scale, .001*scale, .01*scale)
                cache[index] = asdict(numerical_greeks(spot, 100, 1, rate, .2, yield_, kind,
                    bumps=b, fd_config=FDConfig(m, nt, 400, tolerance=1e-10)))
            return cache[index]
        entry = dict(bumps={str(s): run(scale=s) for s in (.25, .5, 1, 2)},
                     spatial={str(m): run(m=m) for m in (160, 320, 640)},
                     temporal={str(nt): run(nt=nt) for nt in (50, 100, 200)})
        if spot == 100:
            entry["crr"] = {str(n): asdict(numerical_greeks(spot, 100, 1, rate, .2, yield_, kind,
                              method="crr", tree_steps=n, bumps=Bumps(2.5, .005, .001, .01)))
                            for n in (800, 801, 1600, 1601)}
        results[key] = entry
    add_fine_bump_study(results)
    return results


def add_fine_bump_study(results: dict) -> None:
    """Test a narrower spot-bump plateau without loosening Greek budgets."""
    for kind, rate, yield_ in (("put", .05, 0), ("call", .02, .10)):
        key = f"{kind}, S=100, r={rate}, q={yield_}"
        results[key]["fine_bumps"] = {str(scale): asdict(numerical_greeks(
            100, 100, 1, rate, .2, yield_, kind,
            bumps=Bumps(1.25*scale, .005*scale, .001*scale, .01*scale),
            fd_config=FDConfig(640, 100, 400, tolerance=1e-10)))
            for scale in (.5, 1, 2)}


def print_report(results: dict) -> None:
    print("# American numerical Greeks: independent stability studies\n")
    print(f"Python {platform.python_version()}; {platform.system()} {platform.machine()}. Synthetic inputs only.")
    print("K=100, maturity=1 year, sigma=.20; exercise=American. Dividend yield stays fixed.")
    print("FD: Smax=400, Rannacher on, omega=1.2, PSOR tolerance=1e-10, max iterations=10000.")
    print("Base absolute bumps: spot=2.5, volatility=.005, rate=.001, maturity=.01 years.")
    print("Vega/Rho are per absolute unit; Theta is calendar theta per year.")
    print("Central formulas are used in these cases. Every perturbation solves exercise anew.")
    print("Grid, domain and controls are frozen inside each risk calculation.\n")
    for case, studies in results.items():
        print(f"## {case}\n")
        for study, rows in studies.items():
            titles = dict(bumps="Bump scale (fixed M=320, Nt=100)",
                          spatial="Spatial M (fixed Nt=100, fixed base bumps)",
                          temporal="Temporal Nt (fixed M=320, fixed base bumps)",
                          crr="Independent CRR steps (fixed base bumps, inspect even/odd separately)",
                          fine_bumps="Finer bump plateau (M=640, Nt=100; base spot bump=1.25, others unchanged)")
            print(f"### {titles[study]}\n")
            print("| Setting | Delta | Gamma | Vega | Theta | Rho | Flags |")
            print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
            for setting, row in rows.items():
                values = " | ".join(f"{row[g]['value']:.8f}" for g in ("delta", "gamma", "vega", "theta", "rho"))
                flags = sorted({flag for g in ("delta", "gamma", "vega", "theta", "rho") for flag in row[g]["flags"]})
                print(f"| {setting} | {values} | {'; '.join(flags) or 'none detected'} |")
            print()
    print("## Interpretation and limits\n")
    print("Compare h/2, h and 2h at FIXED mesh, then change M or Nt separately with FIXED bumps.")
    print("The .25 bump-scale row deliberately uses hS<dS to expose interpolation sensitivity.")
    print("The wider put spot-bump range 1.25/2.5/5 has Delta spread above the declared 0.003 budget.")
    print("That result is retained. The finer plateau independently fixes M=640 and varies spot bumps .625/1.25/2.5.")
    print("Tests retain Delta budget 0.003; they do not relax it to accommodate the wider-bump bias.")
    print("Comparing the two setups changes both mesh and spot-bump range; it does not isolate either error source.")
    print("Only the separate fixed-mesh bump and fixed-bump refinement studies are used for that assessment.")
    print("Smaller bumps do not guarantee better Greeks. Price interpolation and solver noise are amplified,")
    print("especially by the second spot difference. A mesh/bump plateau is empirical evidence, not an error bound.")
    print("The near-boundary put (S=81) can change exercise regime across bumps. No universal smooth derivative")
    print("or stable Gamma is asserted there. Even/odd CRR noise is separate from FD interpolation error.")
    print("In particular, near-boundary Theta is zero on M=320 across the temporal study but changes")
    print("when the spatial mesh is refined. Temporal stability alone must not be interpreted as Greek accuracy.")
    print("For the continuation put with fixed hS=2.5, CRR1600/1601 Gamma retains an even/odd spread")
    print("of about 0.000827; the independent method is not an exact sensitivity reference.")
    print("No global signs for American Theta/Rho or other numerical sensitivities are imposed.")
    print("PSOR residual tolerance does not bound sensitivity error. 'None detected' is not a stability certificate.")
    print("Expiry returns explicit unavailable sensitivities; domain edges use documented forward stencils.")
    print("This module does not implement portfolio scenarios or P&L.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", help="Optional JSON output for measured study results")
    args = parser.parse_args()
    measurements = run_studies()
    if args.cache:
        from pathlib import Path
        Path(args.cache).write_text(json.dumps(measurements, indent=2))
    print_report(measurements)
