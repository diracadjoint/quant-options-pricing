# v1 release-candidate validation record

This record distinguishes executed local checks from configured remote CI and
owner decisions. The candidate is 1.0.0rc1; no release or license was published.

## Clean environment and provenance

A NEW Python 3.12.14 virtual environment was created at work/v1-clean, with no
system-site packages. Tested builder setuptools 84.2.1; pytest 9.2.0;
Matplotlib 3.10.8; NumPy 2.3.5. Host: Linux x86_64, glibc 2.41,
AMD EPYC 9V74 80-Core Processor, three logical CPUs exposed. The complete
OS/package/source metadata and original measured UTC timestamps are retained in
[the full manifest](generated/manifest.json).

Initial core check, before installing ANY visualization packages:

```bash
python -m venv work/v1-clean
work/v1-clean/bin/python -m pip install setuptools==84.2.1
work/v1-clean/bin/python -m pip install --no-index --no-build-isolation .
# From /tmp, with the new interpreter:
# import options_engine succeeds; find_spec('matplotlib') is None.
# bsm_price(100,100,1,.05,.2) -> 10.45058357218555.
```

This non-editable installation/import verifies the packaged core, not only
imports from an editable source checkout. Development/visualization dependencies
were then installed from requirements/visualization-py312.txt; pip check reported
no broken requirements. The final wheel metadata was rebuilt after documentation
consolidation, and public package imports were checked again outside the checkout.
The plotting dependencies remain optional and are not imported by the core.

## Executed checks

| Command/check | Observed result |
| --- | --- |
| python -m pytest -m 'not slow' -q | 763 passed, 39 deselected; 13.78 s |
| python -m pytest -m slow -q | 39 passed, 763 deselected; 333.75 s |
| Combined retained coverage | All 802 cases executed; no test removed or skipped |
| Core non-editable wheel install and external-directory import | Passed before visualization installation |
| pip check | No broken requirements |
| Quick reproduction, after workspace-cache fix | 26 artifacts plus manifest; 100.08 s |
| Final full reproduction | 32 artifacts plus manifest; 369.62 s |
| verify_results.py, quick and full outputs | Artifact hashes, references, warnings and accounting checks passed |
| check_report_tables.py, full output | Five retained financial reports agree at abs=1e-7, rel=1e-10; wall timings excluded |
| check_docs.py | 54 relative links in 17 Markdown documents resolved |
| PNG/SVG review | Eight figure families inspected; explicit European log ticks avoid label overlap |
| git diff --check | Passed |

The separate fast/slow invocations together execute the complete suite; the
slow marker is a scheduling decision, not a waiver of numerical coverage.
Local executions used Python 3.12 only. Python 3.10/3.13 are configured CI targets,
not locally verified results. Remote Actions status must be reviewed on the PR.

The first plot run exposed a read-only home/cache path issue. The plotting
command now defaults Matplotlib/font caches to work/, respecting explicit user
overrides. The quick command was repeated successfully after that fix; the final
full run used the corrected cache setup. A later PRESENTATION-only refresh
removed overlapping European log-axis labels from saved measurements without
recalculating prices. Its producer digest is separately recorded in the manifest
as presentation_refresh; the numerical source snapshot remains intact. The same
explicit labels are part of normal fresh reproduction.

Performance measurements used single perf_counter wall-clock samples, without
warm-up, CPU pinning or load isolation. Tests/reproduction overlapped during some
runs. The recorded durations are observed workloads, not cross-machine promises
or evidence of statistical speedups. Generated hash equality is not promised
across runs with different timing samples or tool versions.

## Current measured financial results

All five original detailed reports were regenerated through their executable
examples; this also exercised the shared demo-input refactor. Financial table
cells agree with the retained reports at the tolerance above. Only Seconds
performance columns are excluded; expiry times, quantities, flags, prices,
Greeks, cash and wealth cells are checked.

- European reference call/put: 10.450583572185565 / 5.573526022256971.
- American put FD M=640,Nt=200,Smax=400: 6.08883942; CRR2400/2401 average
  6.09051979. Both CRR parities remain in tables/figures; their average is a proxy.
- Dividend call FD with r=.02,q=.10: 5.22387677; refined CRR average 5.22533078.
- Mixed portfolio small combined-shock P&L: 92.514589, versus spot-second-order
  approximation 91.649494; large-shock residual approximately -142.865569.
- Hedge dynamic/1 final wealth: rise 1338.92099701, fall 1315.64159935,
  reversal 1562.73426517; risk-free benchmark 1051.27109638 from opening 1000.
  Stock/option/dividend/funding components reconcile. No per-path monotonic
  performance requirement is imposed.

The full numerical-risk reports preserve interpolation and exercise-transition
warnings. Near-boundary temporal stability can coexist with spatial instability.
Portfolio expiry rows retain unavailable Taylor values; the American hedge
example explicitly permits and records warned FD decisions instead of hiding
those flags. The ledger's self-financing identity does not certify Greek accuracy.

## Branch and publication decisions

The implementation base was verified as feat/self-financing-delta-hedging at
68aaee42a115667068495f8df7bb2e3d964c9bb8. Main was still the initial commit during
preparation; preceding feature PRs remain a dependency chain. The consolidation
is a separate draft PR targeting that implementation branch, not an unrelated
main-branch rewrite. Public core interfaces and numerical implementations remain
unchanged. Version metadata is a release candidate for review.

No LICENSE existed; MIT is recommended in [the owner decision](license_decision.md)
but has NOT been adopted. Remaining publication steps are owner approval of a
license/attribution, review and integration of the PR chain, inspection of remote
CI (including scheduled/manual numerical checks), visibility/distribution choice,
and explicit approval of a release/tag. No merge, registry upload, visibility
change or release publication was performed.
