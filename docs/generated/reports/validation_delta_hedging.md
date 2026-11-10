# Static and dynamic self-financing Delta hedges

Python 3.12.14; Linux x86_64. All inputs are synthetic.
Short ONE European call, multiplier 100, K=100, expiry=1 year. S0=100, sigma=.20, r=.05, q=.02.
Every strategy starts with wealth 1000; opening cash finances option/stock holdings at their initial marks.
Same 65 observations (64 intervals) for every frequency; only the stock trading schedule changes.
Rise: 100→125; fall: 100→75; reversal: 100→125→100. Spot is piecewise linear.
Cash compounds continuously; trapezoidal signed dividends are credited at each right endpoint.
No fees, spread, margin, stock rounding or stock-borrow fee. These are not simulated GBM paths.

## Strategy and rebalance-frequency comparison

Opening wealth capitalized at r is the same benchmark for all strategies.
Unhedged/static rows ignore rebalance_every; dynamic closes stock at expiry, without computing an expiry Delta.

| Path | Strategy | Every k observations | Delta decisions | Final wealth | Risk-free benchmark | Excess wealth | Max trade conservation error |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rise | unhedged | N/A | 0 | -478.72048394 | 1051.27109638 | -1529.99158032 | 0 |
| rise | static | N/A | 1 | 822.74245517 | 1051.27109638 | -228.52864121 | 2.27e-13 |
| rise | dynamic | 16 | 4 | 1226.24656465 | 1051.27109638 | 174.97546827 | 9.09e-13 |
| rise | dynamic | 4 | 16 | 1317.05534199 | 1051.27109638 | 265.78424561 | 9.09e-13 |
| rise | dynamic | 1 | 64 | 1338.92099701 | 1051.27109638 | 287.64990064 | 1.82e-12 |
| fall | unhedged | N/A | 0 | 2021.27951606 | 1051.27109638 | 970.00841968 | 0 |
| fall | static | N/A | 1 | 358.66054256 | 1051.27109638 | -692.61055381 | 2.27e-13 |
| fall | dynamic | 16 | 4 | 1113.84875556 | 1051.27109638 | 62.57765918 | 4.55e-13 |
| fall | dynamic | 4 | 16 | 1276.02575658 | 1051.27109638 | 224.75466021 | 4.55e-13 |
| fall | dynamic | 1 | 64 | 1315.64159935 | 1051.27109638 | 264.37050298 | 9.09e-13 |
| reversal | unhedged | N/A | 0 | 2021.27951606 | 1051.27109638 | 970.00841968 | 0 |
| reversal | static | N/A | 1 | 1855.73909137 | 1051.27109638 | 804.46799499 | 2.27e-13 |
| reversal | dynamic | 16 | 4 | 1200.01621465 | 1051.27109638 | 148.74511827 | 1.36e-12 |
| reversal | dynamic | 4 | 16 | 1480.38667311 | 1051.27109638 | 429.11557673 | 1.82e-12 |
| reversal | dynamic | 1 | 64 | 1562.73426517 | 1051.27109638 | 511.46316879 | 1.82e-12 |

## P&L decomposition for every-observation dynamic hedges

Option P&L includes signed payoffs on settlement. Stock P&L is the gain on shares held over intervals;
trades change cash and inventory equally and do not themselves create wealth.

| Path | Option P&L | Stock P&L | Dividends | Financing | Total P&L | Max interval reconciliation error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rise | -1577.29944918 | 2057.27535004 | 187.10510848 | -328.16001232 | 338.92099701 | 1.9e-12 |
| fall | 922.70055082 | -611.46852655 | 45.70371468 | -41.29413959 | 315.64159935 | 6.71e-13 |
| reversal | 922.70055082 | -214.17283892 | 187.75025865 | -333.54370537 | 562.73426517 | 2.25e-12 |

## Opening and full trade/cash audit on a separate coarse rise path

This audit uses five observations, not the common 65-point grid above. All interval flows are shown.
Opening cash adjustment vs original portfolio NAV=1922.70055082.
Opening cash BEFORE stock = initial wealth - signed option mark; AFTER stock additionally subtracts H*S.

| Time | Spot | Option value | Delta used | Shares before | Shares after | Trade cost | Wealth before trade | Wealth after trade |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 100.0 | -922.70055082 | -58.68511461 | 0.00000000 | 58.68511461 | 5868.51146135 | 1000.00000000 | 1000.00000000 |
| 0.25 | 106.25 | -1189.08670010 | -70.38435372 | 58.68511461 | 70.38435372 | 1243.04415552 | 1081.02313795 | 1081.02313795 |
| 0.5 | 112.5 | -1522.51598671 | -83.52687610 | 70.38435372 | 83.52687610 | 1478.53376765 | 1160.47606525 | 1160.47606525 |
| 0.75 | 118.75 | -1955.65517319 | -96.25473777 | 83.52687610 | 96.25473777 | 1511.43357316 | 1213.21985429 | 1213.21985429 |
| 1.0 | 125.0 | 0.00000000 | not needed | 96.25473777 | 0.00000000 | -12031.84222152 | 1225.20706325 | 1225.20706325 |

| Time | Dividends | Financing | Settlement | Cash before trade | Cash after trade | Action |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.0 | 0.00000000 | 0.00000000 | 0.00000000 | 1922.70055082 | -3945.81091053 | open_hedge |
| 0.25 | 30.25951222 | -49.63219133 | 0.00000000 | -3965.18358964 | -5208.22774516 | rebalance |
| 0.5 | 38.49144344 | -65.51144031 | 0.00000000 | -5235.24774202 | -6713.78150967 | rebalance |
| 0.75 | 48.28897525 | -84.44897537 | 0.00000000 | -6749.94150980 | -8261.37508296 | rebalance |
| 1.0 | 58.65523083 | -103.91530614 | -2500.00000000 | -10806.63515827 | 1225.20706325 | horizon_stock_liquidation |

## Mixed portfolio including an American FD position

American policy: HOLD TO EXPIRY, no early exercise or assignment. Rights and risk refresh at every observation/event.
FD domain/grid fixed at Smax=400, M=80, Nt=40; residual tolerance=1e-10; spot bump=1 < dS=5.
The coarse numerical warning is deliberate: default 'raise' would reject it; explicit 'allow' marks decisions.
Expiry at .5 is inserted by linear interpolation, independently of the requested rebalance schedule.

| Time | Spot | Delta used | Shares after | Warned decision | Numerical repricings retained | Warnings |
| ---: | ---: | ---: | ---: | --- | ---: | --- |
| 0.0 | 100.0 | -10.32280052 | 10.32280052 | True | 9 | spot bump smaller than grid spacing: interpolation-limited |
| 0.25 | 98.0 | -10.99578407 | 10.99578407 | True | 9 | spot bump smaller than grid spacing: interpolation-limited |
| 0.5 | 101.5 | -6.04969321 | 6.04969321 | False | 0 | none |
| 0.75 | 105.0 | -7.26388275 | 7.26388275 | False | 0 | none |
| 1.0 | 110.0 | not needed | 0.00000000 | False | 0 | none |

Mixed-portfolio final wealth=1045.97211487; risk-free benchmark=1051.27109638; excess=-5.29898151.

## Interpretation and limits

The paths are deterministic stress examples, not a statistical assessment of hedge quality.
More frequent rebalancing need not improve excess wealth on every individual path; no monotonicity is imposed.
Refining trades along a smooth deterministic path does not reproduce BSM diffusion quadratic variation; excess need not tend to zero.
Initial wealth is controlled across strategies. If omitted, initial wealth defaults to the original option-book NAV including cash.
Financing applies to signed cash; stock dividends include payments on short shares. Dividends receive no intra-interval interest.
This discrete dividend-credit convention has timing error, even though trapezoidal integration is exact on linear spot segments with fixed shares.
At expiry, options cash-settle at interpolated path spot and disappear; stock closes when all options expire or at final horizon.
Cash continues accruing after the last expiry. Live options at a shorter horizon remain marked, with a warning; stock still closes.
American early-exercise/assignment path modeling is explicitly outside this hold-to-expiry demonstration.
Unavailable Delta always raises; numerical warnings raise by default or are explicitly allowed and preserved in history.
A self-financing ledger identity is not a proof that the Delta estimates or market model are accurate.
