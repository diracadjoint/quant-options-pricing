# Crank–Nicolson and PSOR validation

Python 3.12.14; Linux x86_64; 3 logical CPUs.
Synthetic inputs only. Timings are wall seconds and depend on hardware/load.

All cases: S=K=100, maturity=1 year, sigma=.20. FD uses Rannacher (four implicit
half steps replacing the first two full steps), omega=1.2, tolerance=1e-8,
max PSOR iterations=10,000 per step. Residuals/violations are scaled by K.

## American spatial refinement and independent CRR stability

Fixed Nt=200 and Smax=400; only spatial intervals M vary.
CRR references use 1200/1201 and 2400/2401 steps, inspecting both parities.
The average of the finest pair is a comparison reference, not an exact price.

| Case | CRR1200 | CRR1201 | CRR2400 | CRR2401 | Finest pair spread |
| --- | ---: | ---: | ---: | ---: | ---: |
| put, r=0.05, q=0 | 6.08972774 | 6.09159142 | 6.09005372 | 6.09098586 | 0.000932 |
| call, r=0.02, q=0.1 | 5.22469855 | 5.22598810 | 5.22500837 | 5.22565318 | 0.000645 |

| Case | M | FD | Difference/K vs CRR pair | Max LCP residual | Dual violation | Iterations | Boundary S* | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| put | 80 | 6.01646445 | 0.000741 | 1.53e-09 | 1.48e-09 | 1500 | 80.0 | 0.1150 |
| put | 160 | 6.07254270 | 0.00018 | 2.16e-09 | 2.16e-09 | 1282 | 80.0 | 0.1972 |
| put | 320 | 6.08554158 | 4.98e-05 | 2.55e-09 | 2.55e-09 | 1153 | 81.25 | 0.3858 |
| put | 640 | 6.08883942 | 1.68e-05 | 9.99e-09 | 9.99e-09 | 2844 | 80.625 | 1.7185 |
| call | 80 | 5.15170679 | 0.000736 | 1.56e-09 | 1.55e-09 | 1498 | 120.0 | 0.1204 |
| call | 160 | 5.20725413 | 0.000181 | 2.02e-09 | 2.02e-09 | 1433 | 117.5 | 0.2472 |
| call | 320 | 5.22058505 | 4.75e-05 | 5.97e-09 | 4.9e-09 | 1571 | 117.5 | 0.4822 |
| call | 640 | 5.22387677 | 1.45e-05 | 8.07e-09 | 8.07e-09 | 2361 | 118.125 | 1.5540 |

Boundary contacts exclude zero-payoff nodes; S* is a grid estimate at remaining time 1 year.
It is quantized by mesh spacing; no exact smooth-pasting claim follows from contact.

## European validation and isolated temporal refinement

Call, r=.05, q=0; fixed M=400, Smax=400. BSM=10.450583572185565.
Temporal error eventually reaches the fixed spatial error floor.

| Nt | FD | Absolute BSM error | CN RHS nonnegative coefficients |
| ---: | ---: | ---: | --- |
| 25 | 10.44682911 | 0.00375446 | False |
| 50 | 10.44779174 | 0.00279183 | False |
| 100 | 10.44803225 | 0.00255132 | False |
| 200 | 10.44809237 | 0.0024912 | False |

## Domain expansion with fixed local resolution

American put, r=.05, q=0; fixed dS=1 and Nt=200; increase Smax and M together.

| Smax | M | FD | Max LCP residual |
| ---: | ---: | ---: | ---: |
| 200 | 200 | 6.08715457 | 3.77e-09 |
| 300 | 300 | 6.08715457 | 3.77e-09 |
| 400 | 400 | 6.08715457 | 3.77e-09 |
| 500 | 500 | 6.08715457 | 3.77e-09 |

## Exercise boundary validation, separate from price

Fixed Smax=400, Nt=200; samples at remaining years .25, .5 and 1.
The finest grid is a peer comparison, not an exact free-boundary reference.
Budget: each coarse level within two of its cells of M=1280; M=640 vs 1280
within one M=640 cell (0.625) at all sampled times. No monotonic convergence is imposed.

| Case | M | dS | S*(.25) | S*(.5) | S*(1) | Continuation secant at tau=1 | Target slope |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| put | 160 | 2.5 | 87.5 | 82.5 | 80.0 | -0.98784134 | -1 |
| put | 320 | 1.25 | 86.25 | 83.75 | 81.25 | -0.96198259 | -1 |
| put | 640 | 0.625 | 86.875 | 83.75 | 80.625 | -0.99779330 | -1 |
| put | 1280 | 0.3125 | 86.875 | 84.0625 | 80.9375 | -0.99169700 | -1 |
| call | 160 | 2.5 | 112.5 | 115.0 | 117.5 | 0.94183924 | 1 |
| call | 320 | 1.25 | 112.5 | 115.0 | 117.5 | 0.96180681 | 1 |
| call | 640 | 0.625 | 112.5 | 115.0 | 118.125 | 0.99515390 | 1 |
| call | 1280 | 0.3125 | 112.5 | 115.3125 | 117.8125 | 0.98929498 | 1 |

Value-matching budget at final contact: 1e-5 price units. Continuation-side
secant slope budget: 0.03 from -1 (put) or +1 (call) at M=640/1280.
This is a smooth-pasting diagnostic; slopes can oscillate with contact quantization.
It does not constitute convergence to an independently known exact frontier.

### Temporal stability of the frontier

Fixed M=640, Smax=400; compare Nt=200 and 400; budget one cell=0.625.

| Case | Max contact change across sampled dates | Budget |
| --- | ---: | ---: |
| put | 0.0 | 0.625 |
| call | 0.0 | 0.625 |

## Dividend-call domain expansion at fixed resolution

Fixed dS=1, Nt=200, contact tolerance=1e-5 price units; expand Smax and M together.
High yield tests exercise before the upper boundary. Low yield tests the approximate
continuation boundary. An extra Smax=150 row shows truncation effects below the tested
domain-stability range 200..500. Budget: price spread <1e-5 over 200..500.

| r | q | Smax=M | Price | S*(1), None means no grid contact |
| ---: | ---: | ---: | ---: | --- |
| 0.02 | 0.1 | 150 | 5.2221631728 | 118.0 |
| 0.02 | 0.1 | 200 | 5.2221631728 | 118.0 |
| 0.02 | 0.1 | 300 | 5.2221631728 | 118.0 |
| 0.02 | 0.1 | 400 | 5.2221631728 | 118.0 |
| 0.02 | 0.1 | 500 | 5.2221631728 | 118.0 |
| 0.05 | 0.01 | 150 | 9.8237447748 | None |
| 0.05 | 0.01 | 200 | 9.8238438809 | None |
| 0.05 | 0.01 | 300 | 9.8238440162 | None |
| 0.05 | 0.01 | 400 | 9.8238440164 | None |
| 0.05 | 0.01 | 500 | 9.8238440164 | None |

No grid contact at low yield does not imply absence of an exercise boundary beyond Smax.
The smaller-domain row illustrates why local mesh accuracy alone is insufficient.


## Interpretation and limits

Updated K=100 budgets: European absolute error <0.01 at M=640; American cross-cases <0.005 at M=400.
Core American benchmarks at M=640 and 1280 require absolute difference <0.003 against BOTH CRR2400 and CRR2401.
Each CRR parity refinement and finest parity spread must be <0.001; the reference is not treated as exact.
LCP target remains 1e-8 scaled by strike; these price budgets are benchmark-specific.
These measure different errors. A small algebraic residual does not bound truncation,
interpolation or discretization error. Agreement with CRR alone does not prove exactness.
CN can have negative RHS coefficients despite Rannacher; check positivity/oscillations under refinement.
Local drift upwinding guarantees the required spatial sign structure but reduces local order.
Far-field call boundaries are asymptotic approximations; expand the domain, especially for dividend calls.
The PDE currently supports nonnegative rates/yields. BSM and CRR retain negative-rate support.
