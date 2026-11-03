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
    grids = {}
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
            grids[kind, m] = result
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
    print("\n## Exercise boundary validation, separate from price\n")
    print("Fixed Smax=400, Nt=200; samples at remaining years .25, .5 and 1.")
    print("The finest grid is a peer comparison, not an exact free-boundary reference.")
    print("Budget: each coarse level within two of its cells of M=1280; M=640 vs 1280")
    print("within one M=640 cell (0.625) at all sampled times. No monotonic convergence is imposed.\n")
    print("| Case | M | dS | S*(.25) | S*(.5) | S*(1) | Continuation secant at tau=1 | Target slope |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    def edges(result):
        return [min(result.exercise_boundary, key=lambda pair: abs(pair[0]-t))[1]
                for t in (.25, .5, 1.0)]
    for kind, rate, yield_ in cases:
        grids[kind, 1280] = fd_price(100, 100, 1, rate, .2, yield_, kind, config=FDConfig(1280, 200, 400))
        for m in (160, 320, 640, 1280):
            r = grids[kind, m]
            contacts = edges(r)
            i = round(contacts[-1]/(400/m))
            j = i+1 if kind == "put" else i-1
            slope = (r.values[j]-r.values[i])/(r.spots[j]-r.spots[i])
            print(f"| {kind} | {m} | {400/m} | " + " | ".join(str(e) for e in contacts)
                  + f" | {slope:.8f} | {-1 if kind == 'put' else 1} |")
    print("\nValue-matching budget at final contact: 1e-5 price units. Continuation-side")
    print("secant slope budget: 0.03 from -1 (put) or +1 (call) at M=640/1280.")
    print("This is a smooth-pasting diagnostic; slopes can oscillate with contact quantization.")
    print("It does not constitute convergence to an independently known exact frontier.\n")
    print("### Temporal stability of the frontier\n")
    print("Fixed M=640, Smax=400; compare Nt=200 and 400; budget one cell=0.625.\n")
    print("| Case | Max contact change across sampled dates | Budget |")
    print("| --- | ---: | ---: |")
    for kind, rate, yield_ in cases:
        refined = fd_price(100, 100, 1, rate, .2, yield_, kind, config=FDConfig(640, 400, 400))
        change = max(abs(a-b) for a,b in zip(edges(grids[kind, 640]), edges(refined)))
        print(f"| {kind} | {change} | 0.625 |")
    print("\n## Dividend-call domain expansion at fixed resolution\n")
    print("Fixed dS=1, Nt=200, contact tolerance=1e-5 price units; expand Smax and M together.")
    print("High yield tests exercise before the upper boundary. Low yield tests the approximate")
    print("continuation boundary. An extra Smax=150 row shows truncation effects below the tested")
    print("domain-stability range 200..500. Budget: price spread <1e-5 over 200..500.\n")
    print("| r | q | Smax=M | Price | S*(1), None means no grid contact |")
    print("| ---: | ---: | ---: | ---: | --- |")
    for rate, yield_ in ((.02, .10), (.05, .01)):
        for smax in (150, 200, 300, 400, 500):
            r = fd_price(100, 100, 1, rate, .2, yield_, "call", config=FDConfig(smax, 200, smax))
            print(f"| {rate} | {yield_} | {smax} | {r.price:.10f} | {r.exercise_boundary[-1][1]} |")
    print("\nNo grid contact at low yield does not imply absence of an exercise boundary beyond Smax.")
    print("The smaller-domain row illustrates why local mesh accuracy alone is insufficient.\n")
    print("\n## Interpretation and limits\n")
    print("Updated K=100 budgets: European absolute error <0.01 at M=640; American cross-cases <0.005 at M=400.")
    print("Core American benchmarks at M=640 and 1280 require absolute difference <0.003 against BOTH CRR2400 and CRR2401.")
    print("Each CRR parity refinement and finest parity spread must be <0.001; the reference is not treated as exact.")
    print("LCP target remains 1e-8 scaled by strike; these price budgets are benchmark-specific.")
    print("These measure different errors. A small algebraic residual does not bound truncation,")
    print("interpolation or discretization error. Agreement with CRR alone does not prove exactness.")
    print("CN can have negative RHS coefficients despite Rannacher; check positivity/oscillations under refinement.")
    print("Local drift upwinding guarantees the required spatial sign structure but reduces local order.")
    print("Far-field call boundaries are asymptotic approximations; expand the domain, especially for dividend calls.")
    print("The PDE currently supports nonnegative rates/yields. BSM and CRR retain negative-rate support.")


if __name__ == "__main__":
    main()
