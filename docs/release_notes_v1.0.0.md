# Options Pricing and Risk Engine v1.0.0

A standard-library Python engine for European/American vanilla option pricing,
sensitivity analysis, portfolio scenarios and self-financing Delta hedge
demonstrations. Code license: **MIT**, Copyright (c) 2026 Matheus de Oliveira Gomes.

## Included

- Black–Scholes–Merton prices and analytic Delta, Gamma, Vega, calendar Theta
  and Rho with continuous dividends and explicit degenerate cases.
- Independent European/American CRR trees and Crank–Nicolson/Rannacher finite
  differences with PSOR, complementarity diagnostics and grid exercise contacts.
- Numerical Greeks with separate bump, spatial and temporal stability studies,
  explicit unavailable values and preserved risk warnings.
- Signed contract quantities and multipliers, portfolio value/risk aggregation,
  isolated/combined shocks, expiry settlement and signed cash accounting.
- Unhedged/static/dynamic Delta hedges with fractional stock holdings, continuous
  cash financing, discrete dividend credits and auditable wealth reconciliation.
- Reproducible synthetic experiments, CSV/JSON data, eight PNG/SVG figure families,
  provenance manifests and fast/slow GitHub Actions workflows.

## Installation and checks

From the reviewed repository checkout, Python >=3.10:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/dev.txt
python -m pip install --no-build-isolation -e '.[test]'
python examples/bsm_price.py
python -m pytest -q
```

On Windows activate with `.venv\Scripts\activate`. The pricing/risk runtime has
no external dependencies. For figures use the tested Python 3.12 plotting lock:

```bash
python -m pip install -r requirements/visualization-py312.txt
python examples/reproduce.py --mode quick --output work/quick-v1.0.0
python scripts/verify_results.py work/quick-v1.0.0
# Extended studies, without overwriting historical artifacts:
python examples/reproduce.py --mode full --output work/full-v1.0.0
```

## Verified numerical examples

For S=K=100, maturity=1 year, r=.05, sigma=.20, q=0, the reference European
call/put prices are approximately 10.4505835722 / 5.5735260223. The American
put CN/PSOR benchmark at M=640,Nt=200,Smax=400 is 6.08883942; the CRR2400/2401
average is 6.09051979 and is an approximate comparison reference.

In the documented short-call hedge example with initial wealth 1000 and 65
observations, dynamic/1 final wealth is 1338.92099701 (rise), 1315.64159935
(fall) and 1562.73426517 (reversal), versus risk-free wealth 1051.27109638.
These are deterministic stress examples, not statistical hedge-performance claims.

The checked-in experiment artifacts deliberately retain their **1.0.0rc1**
execution metadata and original commit/source references. Their values and
hashes are not relabeled as newly executed 1.0.0 experiments. Current release
validation is documented in [the release record](release_v1.0.0_validation.md).

## Limits and conventions

Spot must be strictly positive. BSM/CRR accept negative rates/yields; the PDE
requires nonnegative r and q. Exercise boundaries are mesh estimates; default
numerical bumps require stability checks. The P&L expansion adds second order
only in spot. Scenario and hedge paths have different, explicit cash/expiry
conventions. Hedge examples hold American options to expiry without simulating
early exercise or assignment; stock dividends are credited at interval ends.
No market data feed, physical delivery, margin or transaction costs are modeled.

The MIT decision applies to code. The technical report is separately licensed
**CC BY-SA 4.0**, as selected by the owner. **DOI pending actual deposit.**
The release includes the report PDF/source, Zenodo metadata proposal and a Python
wheel. Zenodo submission is separate from GitHub publication.
