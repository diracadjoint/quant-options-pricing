# Signed option portfolio and scenario P&L

Python 3.12.14; Linux x86_64. Synthetic inputs only.
One underlying/currency: S=100, sigma=.20, r=.05, continuous q=.02.
Quantity signs represent long/short contracts; every multiplier=100.
American FD: M=320, Nt=100, Smax=400, Rannacher on, omega=1.2, PSOR tolerance=1e-10.
Absolute numerical bumps: spot=2.5, volatility=.005, rate=.001, maturity=.005 years.

## Initial holdings

| Leg | K | Years | Quantity | Multiplier | Unit price | Signed value |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| long European call | 100.0 | 1.0 | 2.0 | 100.0 | 9.22700551 | 1845.401102 |
| short European put | 95.0 | 0.75 | -1.0 | 100.0 | 3.63727060 | -363.727060 |
| long American put | 100.0 | 0.25 | 1.0 | 100.0 | 3.64602676 | 364.602676 |

Option value=1846.27671761; cash=-1500.00000000; total=346.27671761.

## Aggregate option risk

Delta/Gamma differentiate spot; Vega/Rho per absolute unit; calendar Theta per year.
Cash has zero current option Greeks; its exact carry is added separately in scenario approximations.

| Delta | Gamma | Vega | Theta | Rho |
| ---: | ---: | ---: | ---: | ---: |
| 101.33875945 | 5.90077266 | 6567.26834116 | -1394.66637493 | 11436.78376139 |

## Isolated and combined shocks

All changes are ABSOLUTE. Time is remaining calendar years elapsed, not a trading-day convention.
First order includes Delta/Vega/Rho/Theta plus exact initial cash carry. Second order adds Gamma*dS²/2.
Residual=full revaluation P&L minus approximation. N/A means expiry makes the local expansion inapplicable.

| Scenario | dS | dsigma | dr | Elapsed | Exact P&L | First order | Second order | Second residual |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| unchanged | 0.0 | 0.0 | 0.0 | 0.00000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| spot only | 0.5 | 0.0 | 0.0 | 0.00000000 | 52.222610 | 50.669380 | 51.406976 | 0.815634 |
| volatility only | 0.0 | 0.005 | 0.0 | 0.00000000 | 32.811610 | 32.836342 | 32.836342 | -0.024732 |
| rate only | 0.0 | 0.0 | 0.001 | 0.00000000 | 11.446207 | 11.436784 | 11.436784 | 0.009424 |
| one calendar day | 0.0 | 0.0 | 0.0 | 0.00273973 | -4.033112 | -4.026497 | -4.026497 | -0.006615 |
| small combined | 0.5 | 0.005 | 0.001 | 0.00273973 | 92.514589 | 90.911898 | 91.649494 | 0.865095 |
| large combined | -15.0 | 0.05 | 0.01 | 0.10000000 | -704.872473 | -1225.843829 | -562.006904 | -142.865569 |
| American expiry | -10.0 | 0.0 | 0.0 | 0.25000000 | -920.784302 | N/A | N/A | N/A |
| after American expiry | -10.0 | 0.0 | 0.0 | 0.50000000 | -1072.958306 | N/A | N/A | N/A |
| second expiry | -10.0 | 0.0 | 0.0 | 0.75000000 | -1215.216052 | N/A | N/A | N/A |
| after all expiries | 10.0 | 0.0 | 0.0 | 1.25000000 | 82.138497 | N/A | N/A | N/A |

## Settlement and cash audit

Spot/rate/vol shocks occur immediately at time zero. The shocked spot remains flat until the horizon.
Each expiry therefore uses that explicitly specified spot; no terminal spot is retrospectively inferred
as an unobserved expiry price. Already-due options settle at original spot before shocks.
At expiry cash settlement equals signed quantity * multiplier * payoff. It accrues from its own expiry
to horizon at the shocked constant rate. Negative cash and short settlements accrue with the same convention.

| Scenario | Live option value | Initial cash FV | Settlement cash FV | Total cash | Horizon total |
| --- | ---: | ---: | ---: | ---: | ---: |
| American expiry | -55.639907 | -1518.867677 | 1000.000000 | -518.867677 | -574.507584 |
| after American expiry | -201.287359 | -1537.972681 | 1012.578452 | -525.394229 | -726.681588 |
| second expiry | 163.063540 | -1557.317996 | 525.315121 | -1032.002875 | -868.939335 |
| after all expiries | 0.000000 | -1596.741688 | 2025.156903 | 428.415215 | 428.415215 |

| Scenario | Leg | Status | Expiry time | Settlement principal | Leg horizon value |
| --- | --- | --- | ---: | ---: | ---: |
| American expiry | long European call | active | None | 0.000000 | 653.552260 |
| American expiry | short European put | active | None | 0.000000 | -709.192167 |
| American expiry | long American put | settled | 0.25 | 1000.000000 | 1000.000000 |
| after American expiry | long European call | active | None | 0.000000 | 416.671048 |
| after American expiry | short European put | active | None | 0.000000 | -617.958407 |
| after American expiry | long American put | settled | 0.25 | 1000.000000 | 1012.578452 |
| second expiry | long European call | active | None | 0.000000 | 163.063540 |
| second expiry | short European put | settled | 0.75 | -500.000000 | -500.000000 |
| second expiry | long American put | settled | 0.25 | 1000.000000 | 1025.315121 |
| after all expiries | long European call | settled | 1.0 | 2000.000000 | 2025.156903 |
| after all expiries | short European put | settled | 0.75 | -0.000000 | 0.000000 |
| after all expiries | long American put | settled | 0.25 | 0.000000 | 0.000000 |

## Interpretation and limits

This is mark-to-market P&L from the initial valuation, not profit since a historical trade.
'Exact' means full repricing rather than Taylor; numerical solver errors and model assumptions remain.
Initial cash is supplied explicitly; purchase/sale premiums are not automatically booked.
Options are cash-settled, not physically delivered. American entitlement is repriced optimally
at endpoints, but no intermediate early exercise or short assignment transaction is simulated.
The hold-to-horizon/expiry policy is explicit; this is not optimal realized exercise P&L along a path.
The shocked spot path is a stress convention, not a simulated or risk-neutral prediction.
Dividends enter q in prices, not option-holder cash payments. No fees, margin, taxes or hedging trades.
The local expansion omits cross terms and higher orders; large shocks and frontier changes can produce large residuals.
FD interpolation and numerical-Greek noise also affect the residual, especially for small spot shocks.
No universal claim that adding Gamma improves every combined scenario is made.
Numerical Greek warnings propagate to the portfolio; one stable price does not certify stable risk.
The live FD positions retain r,q>=0 and their ORIGINAL spatial domain and controls across scenarios.
At/beyond any nonzero live position expiry, Taylor approximations are N/A, but exact settlement P&L remains defined.
