# Options Pricing and Risk Engine — implemented v1 specification

Status: **1.0.0; publication authorized by the owner**.
This document describes delivered behavior. The owner has approved MIT for the
code; see LICENSE. The report is separately licensed CC BY-SA 4.0. Release status
is recorded in GitHub Releases; Zenodo deposit and DOI remain pending actual
submission. All examples use synthetic data. Historical experimental artifacts keep
their original 1.0.0rc1 metadata and source/commit references unchanged.

## Purpose and scope

A Python library for comparing vanilla European/American prices, sensitivities,
exercise decisions, signed-portfolio scenario P&L and self-financing Delta hedges
under the same constant-parameter BSM dynamics. Core execution uses only the
Python standard library; plotting is an optional extra. Experiments consume the
library and retain parameters, warnings, tables, figures and environment data.

Delivered: analytic BSM and Greeks; independent CRR; European CN/Rannacher;
American CN/PSOR; grid exercise contacts; numerical Greeks; signed portfolios;
scenario/expiry/cash accounting; static/dynamic Delta hedge ledgers; tests and
reproduction tooling. There is one underlying and one currency, no market feed.

## Domain and units

- Public spot **S>0**, strike K>0; maturity tau>=0 and volatility sigma>=0.
  All numeric inputs are finite real scalars. The PDE's boundary S=0 is internal,
  not a public zero-spot price API.
- BSM and CRR accept finite negative rates and dividend yields. The FD solver
  explicitly requires **r>=0 and q>=0**; its boundary/M-matrix validation does
  not claim the broader domain. CRR probabilities must be valid on every bump.
- Maturity/elapsed time is in years; sigma/r/q are annual decimals, rates are
  continuously compounded. No date/day-count/calendar conversion is performed.
- Prices are per underlying unit. Quantity n is signed, multiplier m positive;
  portfolio contributions scale by n*m. Fractional quantities/shares are allowed.
- Delta=dV/dS, Gamma=d²V/dS², Vega=dV/dsigma, Rho=dV/dr. Vega/Rho are per
  absolute unit (divide by 100 for one percentage point; Rho/10000 for one bp).
  Calendar Theta=-dV/dtau is per year; daily display is Theta/365.

## Model and analytic reference

Risk-neutral dynamics and the BSM operator are

```text
dS = (r-q) S dt + sigma S dW
L V = .5 sigma² S² V_SS + (r-q) S V_S - r V
V_tau = L V,       V(S,0) = g(S)
g_call=max(S-K,0), g_put=max(K-S,0)
```

For S,sigma,tau>0:

```text
d1 = [log(S/K) + (r-q+sigma²/2) tau] / (sigma sqrt(tau))
d2 = d1 - sigma sqrt(tau)
C = S exp(-q tau) N(d1) - K exp(-r tau) N(d2)
P = K exp(-r tau) N(-d2) - S exp(-q tau) N(-d1)
C-P = S exp(-q tau) - K exp(-r tau)
```

The implementation uses standard-library erfc for the normal CDF and avoids
forming S/K directly. Expiry returns payoff; zero volatility returns discounted
deterministic European payoff without epsilon substitution. Analytic Greeks
use interior formulas with fixed q; zero maturity/volatility explicitly raises
`GreeksUnavailableError`, rather than asserting zero sensitivities. Finite
floating-point range, tail underflow and cancellation limitations are documented.

## American exercise and independent numerical methods

American price is the supremum of discounted payoff over stopping times. The
remaining-time obstacle is

```text
V-g >= 0, V_tau-LV >= 0, (V-g)(V_tau-LV)=0.
```

CRR uses u=exp(sigma sqrt(dt)), d=1/u and p=(exp((r-q)dt)-d)/(u-d).
Rollback discounts continuation and, for Americans, takes its maximum with
intrinsic value. Invalid p is rejected, never clipped. Memory is O(N); runtime
O(N²). Zero volatility is treated separately by optimizing discounted
deterministic exercise payoff over endpoints and interior stationary times.
Even and odd sequences are inspected separately; monotonic error is not assumed.

The FD solver uses a uniform spot grid [0,Smax], central spatial differences,
Crank–Nicolson `A=I-dt Lh/2`, `B=I+dt Lh/2` and both time levels of boundary
contributions. Rannacher startup replaces the first **two** full steps by **four**
implicit half steps. The American obstacle is solved in each half step too.
Europeans use Thomas tridiagonal elimination, not dense inversion. Locally
one-sided drift replaces central drift when required for generator sign structure;
its affected nodes are counted and the local spatial order becomes first order.
CN does not guarantee positivity on every mesh; explicit-side coefficient
positivity is reported separately.

At S=0, calls are zero, European puts K exp(-r tau), American puts K. At Smax,
puts are zero; European calls use the nonnegative asymptotic discounted
spot-strike difference; American calls take its maximum with Smax-K. These
upper conditions approximate domain truncation. Expand Smax at fixed dS to
test that error, including dividend calls. Default Smax is a starting choice,
not an accuracy guarantee. Spot prices use linear interpolation.

PSOR projects relaxed updates onto payoff. Required strict M-matrix diagonal
dominance is checked. Both scaled update and
`||min(v-g, Av-b)||inf/K` must meet the configured tolerance (default 1e-8).
Results retain worst residual, obstacle/dual violations and iterations over all
steps. Exhaustion raises `ConvergenceError`. A solver residual is not a price
error bound. The returned exercise frontier is a **mesh contact estimate**,
excluding zero-payoff nodes, not an exact free boundary or smooth-pasting proof.

## Numerical risk

Each distinct bump reprices optimal exercise. Central second-order first/second
differences are preferred; domain boundaries use documented second-order forward
stencils. Theta reverses the maturity derivative. Expiry sensitivities are None;
unavailable values are explicit. Default relative bumps/absolute floors require
an empirical stability study and are not automatically calibrated.

FD Smax/M/Nt and controls stay fixed inside each risk calculation. Linear
interpolation can produce zero or amplified Gamma for hS<dS, which is flagged.
Exercise regime changes are flagged separately; warnings and repricing metadata
remain visible. Bump studies fix the mesh; spatial/temporal studies fix bumps and
vary one resolution at a time. Near the free boundary no universal smooth Gamma
is claimed. Independent CRR Greeks also retain parity noise.

## Portfolio, scenarios and cash

```text
Option value = sum(n_j m_j V_j)
Greek exposure = sum(n_j m_j G_j)
First-order option P&L = Delta*dS + Vega*dsigma + Rho*dr + Theta*elapsed
Second approximation adds .5 Gamma*dS² ONLY
```

Cross terms and other second derivatives are omitted. Exact carry on initial
effective cash is added separately. `exact_pnl` means full repricing, not absence
of numerical/model error. Noncanceling unavailable Greeks propagate None.

Scenario shocks occur immediately, then spot is flat through the horizon;
r/sigma are constant at shocked values and q fixed. Each expiry uses the specified
spot on that stress path, settles signed payoff into cash, and accrues at shocked
r from its own expiry to horizon. Already-due options settle at original spot
before shocks. Negative cash represents borrowing at the same rate. Expired
marks are removed without double counting. Local Taylor approximations become
unavailable on reaching a nonzero live leg's expiry, but settlement P&L remains
defined. Original FD domains/controls are retained across scenarios.

## Self-financing hedge demonstration

Input spot paths are instead piecewise linear between supplied increasing times
starting at zero. Insert intermediate expiries with interpolated spot. Refresh
rights and Greeks at every observation. Unhedged inventory is zero; static
inventory is the opening Delta hedge; dynamic inventory rebalances every kth
original observation plus expiry events. At decisions H=-Delta_options.

```text
W = option_value + H*S + cash
cash_after_trade = cash_before_trade - (H_new-H_old)*S
opening cash = W0 - option_value - H0*S0
```

Default W0 is original option-book NAV including cash; explicit W0 overrides it
with the opening adjustment recorded. Between events shares are fixed, old cash
compounds continuously, and signed dividends use q*H*(Sleft+Sright)/2*dt,
credited at the right endpoint. This trapezoid is exact for nominal dividends
on a linear segment, but omits intra-interval interest on the dividend stream.
At expiry options cash-settle once; stock closes at last expiry or final horizon.
Live options at a shorter horizon remain marked with a warning.

Interval wealth changes reconcile to option P&L (including settlement), stock
P&L, dividends and financing. Trades preserve wealth up to rounding. History
retains both balances and diagnostics. Delta unavailable at a decision always
raises; warned risk raises by default or is explicitly allowed and marked.
FD domains/control settings remain fixed. Explicit bumps stay fixed; omitted
bump fields follow existing state-dependent defaults, recorded per observation.

American demonstration policy is **hold to expiry, no early exercise or
assignment simulation**. Endpoint prices retain optimal exercise rights, but
realized early-exercise strategies need separate rules. There are no external
cash injections after opening, physical delivery, hedge fees, margin, taxes,
stock-borrow charges, funding spreads or automatic premium booking.

## Architecture and validation

| Module/path | Delivered responsibility |
| --- | --- |
| src/options_engine/analytic.py | BSM prices, analytic Greeks, scalar validation |
| contracts.py | Immutable Market/OptionContract |
| binomial.py | Independent European/American CRR |
| finite_difference.py, psor.py | CN, Rannacher, obstacle, contacts and diagnostics |
| risk.py | Numerical Greeks, stencils, warnings and repricing records |
| portfolio.py | Signed positions, aggregate risk, scenario/expiry/cash ledger |
| hedging.py | Static/dynamic self-financing stock/cash histories |
| tests/ | Financial identities, references, failures and refinement checks |
| examples/ | Executable experiments and shared demo inputs |
| examples/reproduce.py | Tables, PNG/SVG figures and provenance manifest |
| docs/ | Detailed API, measured reports, gallery and release checks |

Validation distinguishes model identities, algebraic residual, price error,
frontier stability, Greek stability and accounting identities. At least four
levels vary spatial/time/domain resolution separately in detailed experiments.
Core K=100 American comparisons at M=640/1280 require absolute difference <.003
against **both** CRR2400/2401, with parity/refinement spread checks <.001.
European FD cases at M=640 require absolute error <.01. These are declared
benchmark budgets, not global accuracy claims. Frontier budgets use mesh cells;
Greek budgets depend on units and the declared continuation cases. Full details
and warnings are in [the API reference](docs/api_reference.md) and
[reproduction guide](docs/reproduction.md).

Fast CI covers pricing, analytic risk, FD controls, portfolios and hedges on
Python 3.10/3.12/3.13. Fine-grid boundary and numerical-risk modules are marked
slow, retained in weekly/manual CI. Only actually executed environments are
claimed in [the validation record](docs/v1_validation.md). Performance measurements
retain machine/package metadata; single-run timings are not speedup guarantees.

## Limits and extensions

Validation is a synthetic benchmark set, not calibration or universal numerical
accuracy. Free-boundary/Gamma estimates remain sensitive to resolution, bumps
and nonsmooth exercise transitions. Deterministic hedge paths do not recreate
BSM diffusion quadratic variation; more rebalancing need not improve every path.
The code is MIT-licensed; the technical report is separately CC BY-SA 4.0.

Possible extensions: negative-rate PDE boundary analysis, nonuniform/adaptive
grids, American exercise/assignment path rules, discrete dividends, date handling,
market calibration, multi-asset/currency portfolios, transaction costs and a fuller
P&L Hessian. Stochastic volatility, exotics, market feeds and broker execution are
outside delivered v1. See [license decision](docs/license_decision.md).
