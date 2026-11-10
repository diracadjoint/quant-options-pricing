# Proposed Zenodo technical-report metadata

Status: owner authorized deposit; access/submission pending, no report deposited.
Report license: **CC BY-SA 4.0**, explicitly selected by the owner. Code license: MIT.
DOI: **pending until deposit**; no DOI is reserved or claimed here.

Upload-ready [report PDF](technical_report.pdf), [source](technical_report.md),
[license record](report_license.md) and [metadata JSON](zenodo_metadata.json).
The JSON is an input proposal for the Zenodo deposition API, not a service response
or proof of deposit. It intentionally contains no DOI or fabricated record ID.

## Title

Options Pricing and Risk Engine: Reproducible Valuation, Sensitivity Analysis,
and Self-Financing Delta Hedging

## Abstract

This report presents a reproducible Python implementation of vanilla option
valuation and risk analysis under constant-parameter Black–Scholes–Merton
dynamics with continuous dividends. European analytic prices and Greeks provide
controls for independent Cox–Ross–Rubinstein trees and Crank–Nicolson finite
differences with Rannacher startup. American exercise is treated as an obstacle
problem solved by projected successive over-relaxation, with complementarity
diagnostics and mesh-estimated exercise boundaries. Numerical sensitivity
studies separate perturbation size from spatial and temporal refinement and
retain warnings near interpolation and exercise transitions. Signed portfolio
scenarios account explicitly for expiry settlement, cash financing and local
Greek P&L approximations. Deterministic hedge demonstrations compare unhedged,
static and rebalanced Delta strategies using an auditable self-financing stock
and cash ledger. Automated tests and synthetic experiments accompany tables,
figures and execution provenance. Results are benchmark-specific; grid boundaries,
American sensitivities and individual-path hedge outcomes are not presented as
universal accuracy or performance guarantees.
