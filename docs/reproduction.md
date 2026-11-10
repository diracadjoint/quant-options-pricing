# Installation, tests and reproduction

Run commands from the repository root. Core: Python >=3.10, standard library only.
The exact plotting lock is for **Python 3.12**; other Python versions can resolve
the optional visualization extra but are not claimed to reproduce this lock.

## Fresh development environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/dev.txt
python -m pip install --no-build-isolation -e '.[test]'
python -c "from options_engine import bsm_price; print(bsm_price(100,100,1,.05,.2))"
python -m pytest -m 'not slow' -q
python -m pytest -m slow -q
```

Windows activation: `.venv\Scripts\activate`. `python -m pytest -q` runs BOTH
groups. Fine-grid/numerical-risk tests in test_fd_validation.py and test_risk.py
are marked slow; none were deleted or skipped. The other numerical/financial
controls stay in fast feedback. See the actual counts in [validation](v1_validation.md).

For core-only installation, `python -m pip install .` does not install plotting
or testing dependencies. Importing the package does not import Matplotlib/NumPy.
The clean-environment record verifies core import before installing visualization.

## Figures and numerical tables

In Python 3.12:

```bash
python -m pip install -r requirements/visualization-py312.txt
python -m pip install --no-build-isolation -e '.[test,visualization]'
python examples/reproduce.py --mode quick --output work/quick-results
python scripts/verify_results.py work/quick-results
```

Quick mode is a representative overview, not the full parameter coverage: all
eight figure families, four European spatial/time refinements, American price
comparisons, a continuation-put Greek study, portfolio scenarios and hedge
comparisons. Full mode adds the dividend-call/near-boundary/finer-bump/CRR Greek
studies and regenerates the detailed original example reports:

```bash
python examples/reproduce.py --mode full --output work/full-results-v1.0.0
python scripts/verify_results.py work/full-results-v1.0.0
python scripts/check_report_tables.py work/full-results-v1.0.0
python scripts/check_docs.py
```

Expect minutes for the full pure-Python numerical risk study. Execution times
depend on CPU/load; consult each run's manifest rather than a fixed runtime
promise. Quick writes to work/ so it does not overwrite committed full results.
Each output directory should be new or dedicated to one mode: the generator
never deletes pre-existing files. The committed [gallery](gallery.md) uses full
results, measured with 1.0.0rc1. Their source/commit metadata and bytes are preserved;
v1.0.0 reruns use a separate work/ directory. Neither command fetches market data
or needs network once installed.

Outputs: eight named figures in both PNG/SVG, machine-readable CSV tables,
data.json (including full numerical risk configurations, repricings and flags),
and manifest.json with hardware/OS/Python/package versions, base commit, source
content digest, runtime and artifact SHA256 hashes. Full mode additionally writes
reports/ with all pre-existing demonstration outputs. Timing samples use
perf_counter wall time without warm-up or CPU isolation; no speedup inference is
made from a single point. Prices should reproduce within declared tolerances;
timings and generated file hashes may change with hardware/load/tool versions.

## Experiment definitions

Unless stated otherwise, convergence contracts use S=K=100, tau=1, sigma=.20.
The European call has r=.05,q=0. Spatial refinement varies M=80/160/320/640 with
Nt=400; temporal refinement Nt=25/50/100/200 fixes M=400; Smax=400 throughout.
Americans use Nt=200, the same four spatial levels: put r=.05,q=0; dividend call
r=.02,q=.10. Quick CRR pairs are 100/101,200/201,400/401,800/801; full pairs are
200/201,400/401,1200/1201,2400/2401. Their finest average is a comparison proxy,
not exact American truth. Error/time figures label that distinction. Positive
differences below plotting range can use a 1e-15 plotting floor; raw prices are
retained in CSV. No observed order is presumed or imposed.

EEP compares American and European values on the SAME FD grid. Contact plots
show raw stepwise mesh estimates, not interpolated exact boundaries. FD has
Rannacher four-half-step startup, omega=1.2 and tolerance=1e-8. Original reports
also preserve separate domain expansion, contact and smooth-pasting diagnostics.

Greek studies reuse absolute bumps spot=2.5,vol=.005,rate=.001,time=.01,
Smax=400, Nt=100 and PSOR tolerance=1e-10. Vary bump scale .25/.5/1/2 at M=320;
vary M=160/320/640 at fixed bumps; vary Nt=50/100/200 at fixed M=320. Full adds
finer M=640 bump tests and CRR parity. Warnings remain in CSV/JSON and detailed
reports; small bumps can double or erase Gamma, and near-boundary Greeks can
change substantially under spatial refinement.

Portfolio and hedge inputs are shared with the existing demonstration builders
(`demo_inputs` in portfolio_validation.py and delta_hedging_validation.py), not
maintained as separate formula implementations. Portfolio shock tables retain
unavailable Taylor values at expiry and cash-settlement ledgers. Hedge tables
retain warnings and decision markers; full detailed reports include a deliberately
warned American FD example. The hedge wealth curves share the same 65-point grid
and W0=1000, varying only stock rebalancing. P&L bars show signed option, stock,
dividend and financing components. More trading need not improve each path.

## Continuous integration and release checks

Fast GitHub Actions run on pushes/PRs/manual dispatch for Python 3.10,3.12,3.13,
install a non-editable package, import it outside the checkout and run fast tests
plus local-link checks. Weekly Monday 06:00 UTC and manual numerical workflows
retain all slow tests and full reproduction on Python 3.12, uploading artifacts.
Scheduled workflows apply after integration into the default branch. CI is
configured here; remote status is distinct from local validation and must be
reviewed before release.

MIT is approved and installed for the code. Before publication, review the full
implementation PR against main, check remote CI and intended visibility, and
authorize merge and release/tag separately. The preparation performs no publication.
Zenodo report licensing/deposit is a separate decision; no DOI has been assigned.
