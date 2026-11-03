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
| put | 80 | 6.01646445 | 0.000741 | 1.53e-09 | 1.48e-09 | 1500 | 80.0 | 0.1428 |
| put | 160 | 6.07254270 | 0.00018 | 2.16e-09 | 2.16e-09 | 1282 | 80.0 | 0.2668 |
| put | 320 | 6.08554158 | 4.98e-05 | 2.55e-09 | 2.55e-09 | 1153 | 81.25 | 0.5015 |
| put | 640 | 6.08883942 | 1.68e-05 | 9.99e-09 | 9.99e-09 | 2844 | 80.625 | 2.1126 |
| call | 80 | 5.15170679 | 0.000736 | 1.56e-09 | 1.55e-09 | 1498 | 120.0 | 0.1265 |
| call | 160 | 5.20725413 | 0.000181 | 2.02e-09 | 2.02e-09 | 1433 | 117.5 | 0.2434 |
| call | 320 | 5.22058505 | 4.75e-05 | 5.97e-09 | 4.9e-09 | 1571 | 117.5 | 0.5848 |
| call | 640 | 5.22387677 | 1.45e-05 | 8.07e-09 | 8.07e-09 | 2361 | 118.125 | 1.6048 |

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

## Interpretation and limits

Price target is absolute difference/K < 1e-3 on declared benchmarks; LCP target is 1e-8.
These measure different errors. A small algebraic residual does not bound truncation,
interpolation or discretization error. Agreement with CRR alone does not prove exactness.
CN can have negative RHS coefficients despite Rannacher; check positivity/oscillations under refinement.
Local drift upwinding guarantees the required spatial sign structure but reduces local order.
Far-field call boundaries are asymptotic approximations; expand the domain, especially for dividend calls.
The PDE currently supports nonnegative rates/yields. BSM and CRR retain negative-rate support.
