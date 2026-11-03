"""Print measured CN/PSOR validation tables as Markdown; runs offline."""

import os
import platform
from time import perf_counter

from options_engine import FDConfig, bsm_price, crr_price, fd_price


def main() -> None:
    print("# Crank–Nicolson and PSOR validation\n")
    print(f"Python {platform.python_version()}; {platform.system()} {platform.machine()}; {os.cpu_count()} logical CPUs.")
    print("Synthetic inputs only. Timings are wall seconds and depend on hardware/load.\n")
    print("All cases: S=K=100, maturity=1 year, sigma=.20. FD uses Rannacher (four implicit")
    print("half steps replacing the first two full steps), omega=1.2, tolerance=1e-8,")
    print("max PSOR iterations=10,000 per step. Residuals/violations are scaled by K.\n")
    print("## American spatial refinement and independent CRR stability\n")
    print("Fixed Nt=200 and Smax=400; only spatial intervals M vary.")
    print("CRR references use 1200/1201 and 2400/2401 steps, inspecting both parities.")
    print("The average of the finest pair is a comparison reference, not an exact price.\n")
    print("| Case | CRR1200 | CRR1201 | CRR2400 | CRR2401 | Finest pair spread |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    cases = [("put", .05, 0), ("call", .02, .10)]
    references = {}
    for kind, rate, yield_ in cases:
        prices = [crr_price(100, 100, 1, rate, .2, yield_, kind, steps=n).price
                  for n in (1200, 1201, 2400, 2401)]
        references[kind] = (prices[-1]+prices[-2])/2
        print(f"| {kind}, r={rate}, q={yield_} | " + " | ".join(f"{p:.8f}" for p in prices)
              + f" | {abs(prices[-1]-prices[-2]):.3g} |")
    print("\n| Case | M | FD | Difference/K vs CRR pair | Max LCP residual | Dual violation | Iterations | Boundary S* | Seconds |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for kind, rate, yield_ in cases:
        for m in (80, 160, 320, 640):
            start = perf_counter()
            result = fd_price(100, 100, 1, rate, .2, yield_, kind, config=FDConfig(m, 200, 400))
            elapsed = perf_counter()-start
            boundary = result.exercise_boundary[-1][1]
            print(f"| {kind} | {m} | {result.price:.8f} | {abs(result.price-references[kind])/100:.3g} | "
                  f"{result.max_residual:.3g} | {result.dual_violation:.3g} | {result.total_iterations} | {boundary} | {elapsed:.4f} |")
    print("\nBoundary contacts exclude zero-payoff nodes; S* is a grid estimate at remaining time 1 year.")
    print("It is quantized by mesh spacing; no exact smooth-pasting claim follows from contact.\n")
    print("## European validation and isolated temporal refinement\n")
    print("Call, r=.05, q=0; fixed M=400, Smax=400. BSM=10.450583572185565.")
    print("Temporal error eventually reaches the fixed spatial error floor.\n")
    print("| Nt | FD | Absolute BSM error | CN RHS nonnegative coefficients |")
    print("| ---: | ---: | ---: | --- |")
    for nt in (25, 50, 100, 200):
        r = fd_price(100, 100, 1, .05, .2, exercise_style="european", config=FDConfig(400, nt, 400))
        error = abs(r.price-bsm_price(100, 100, 1, .05, .2))
        print(f"| {nt} | {r.price:.8f} | {error:.6g} | {r.cn_positive_rhs} |")
    print("\n## Domain expansion with fixed local resolution\n")
    print("American put, r=.05, q=0; fixed dS=1 and Nt=200; increase Smax and M together.\n")
    print("| Smax | M | FD | Max LCP residual |")
    print("| ---: | ---: | ---: | ---: |")
    for smax in (200, 300, 400, 500):
        r = fd_price(100, 100, 1, .05, .2, option_type="put", config=FDConfig(smax, 200, smax))
        print(f"| {smax} | {smax} | {r.price:.8f} | {r.max_residual:.3g} |")
    print("\n## Interpretation and limits\n")
    print("Price target is absolute difference/K < 1e-3 on declared benchmarks; LCP target is 1e-8.")
    print("These measure different errors. A small algebraic residual does not bound truncation,")
    print("interpolation or discretization error. Agreement with CRR alone does not prove exactness.")
    print("CN can have negative RHS coefficients despite Rannacher; check positivity/oscillations under refinement.")
    print("Local drift upwinding guarantees the required spatial sign structure but reduces local order.")
    print("Far-field call boundaries are asymptotic approximations; expand the domain, especially for dividend calls.")
    print("The PDE currently supports nonnegative rates/yields. BSM and CRR retain negative-rate support.")


if __name__ == "__main__":
    main()
