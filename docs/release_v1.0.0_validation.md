# v1.0.0 release preparation and validation

Status: preparation for owner review; no merge, visibility change, tag, GitHub
release, registry upload or Zenodo deposit is authorized by this preparation.

## Initial repository audit

- main: 8911aa877f3de6d4b3ffebfabc5d3c34fc51e1c8 (initial commit).
- release/v1-consolidation: 1616940e3157b43f899774b44bc686ac1f0f144b.
- Compare: eight commits ahead of main, zero behind; the full implementation
  chain is present. PR #8 was open/draft and targeted the hedge branch.
- Package version was 1.0.0rc1. The tags collection was empty.
- Release changes are appended as a fast-forward child, without squashing or
  rewriting any implementation commit. PR #8 is to target main and remain draft.

## Approved scope

Version metadata becomes 1.0.0. The owner-approved MIT code license has the
standard root LICENSE text and exact notice Copyright (c) 2026 Matheus de Oliveira
Gomes. SPDX License-Expression and packaged license-file metadata are checked
with the tested setuptools 84.2.1 builder; the minimum backend is raised to 77
for PEP 639 support. The report's Zenodo license and DOI remain separate/pending.

All financial source files and every docs/generated artifact are protected by
before/after SHA256 checks. Historical RC1 versions, commit references, measured
values, figures and timestamps are intentionally preserved. No experimental
rerun is needed for these version/license/documentation-only changes.

## Current checks

Executed on 2026-11-10 with Python 3.12.14, setuptools 84.2.1 and pytest 9.2.0
in the isolated `work/v1-clean` environment:

```bash
PY=work/v1-clean/bin/python
mkdir -p work/v100-dist
$PY -m pip wheel --no-index --no-deps --no-build-isolation -w work/v100-dist .
$PY -m pip install --no-index --no-deps --force-reinstall work/v100-dist/options_engine-1.0.0-py3-none-any.whl
$PY -m pip check
$PY -m pytest -q
$PY scripts/check_docs.py
$PY scripts/verify_results.py docs/generated
$PY scripts/check_report_tables.py docs/generated
```

- Wheel build and installation succeeded without fetching dependencies.
  Importing from `/tmp` confirmed the installed package, version `1.0.0`, SPDX
  `License-Expression: MIT`, and `License-File: LICENSE`. The packaged license
  matches the root file, including the approved copyright notice. A core import
  did not import matplotlib. The BSM reference call returned 10.45058357218555.
- `pip check`: no broken requirements.
- Full suite: **802 passed in 303.23 seconds**, including slow tests.
- Documentation: **64 relative links in 20 Markdown documents** checked.
- Results: **32 artifacts**, reference values, warnings and ledger identities
  verified against the preserved historical manifest/data.
- Tables: all **five retained financial reports** match with absolute tolerance
  `1e-7` and relative tolerance `1e-10`; wall timings are excluded by the checker.
- Before/after SHA256 comparisons preserve all **33 generated files and nine
  financial source files** byte for byte. No experiments were regenerated.

Historical experiment timings and results remain in
[the original RC1 record](v1_validation.md), not relabeled as new measurements.
The local release build/full suite above used Python 3.12; other interpreter
versions are covered by the configured PR matrix, whose current results should
be checked on GitHub. No remote slow workflow was manually dispatched here.

## Review materials and publication boundary

English [release notes](release_notes_v1.0.0.md) and a proposed
[Zenodo title/abstract](zenodo_v1.0.0_proposal.md) are prepared for copying/review.
No DOI is assigned. Separate owner authorization remains required for merge,
visibility changes, tag/release publication and any report deposit. Slow CI can
also be triggered manually after workflow integration into the default branch;
configured automation is distinct from the checks actually executed here.
