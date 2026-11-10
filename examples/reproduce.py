"""Generate numerical tables, figures and provenance; optional plotting only."""

import argparse
from contextlib import redirect_stdout
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

from options_engine import FDConfig, bsm_price, crr_price, fd_price, scenario_pnl, simulate_delta_hedge, value_portfolio
from american_greeks_validation import print_report, run_studies
from delta_hedging_validation import demo_inputs as hedge_inputs
from portfolio_validation import demo_inputs as portfolio_inputs


ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})


def provenance(mode: str) -> dict:
    cpu = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        cpu = next((line.split(":", 1)[1].strip() for line in cpuinfo.read_text().splitlines()
                    if line.startswith("model name")), cpu)
    files = sorted([*(ROOT/"src").rglob("*.py"), *(ROOT/"examples").glob("*.py"),
                    *(ROOT/"requirements").glob("*.txt"), ROOT/"pyproject.toml"])
    digest = hashlib.sha256()
    for file in files:
        digest.update(str(file.relative_to(ROOT)).encode())
        digest.update(file.read_bytes())
    return dict(mode=mode, measured_at_utc=datetime.now(timezone.utc).isoformat(),
                python=platform.python_version(), platform=platform.platform(), machine=platform.machine(),
                cpu=cpu, logical_cpus=os.cpu_count(),
                packages={p: version(p) for p in ("options-engine", "matplotlib", "numpy", "pytest", "setuptools")},
                source_sha256=digest.hexdigest(), base_branch="feat/self-financing-delta-hedging",
                base_commit="68aaee42a115667068495f8df7bb2e3d964c9bb8",
                timing="single perf_counter wall-time samples; no warm-up, no statistical speedup claim",
                synthetic_data=True)


def european_figure(plt, european):
    """Render measured European errors with explicit, non-overlapping log ticks."""
    import matplotlib
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, study in zip(axes, ("spatial", "temporal")):
        rows = [r for r in european if r["study"] == study]
        ax.loglog([r["level"] for r in rows], [r["absolute_error"] for r in rows], "o-", label="CN vs BSM")
        ax.set(xlabel="Spatial intervals M" if study == "spatial" else "Time intervals Nt",
               ylabel="Absolute price error (currency/unit)", title=f"European call: {study} refinement")
        ax.set_xticks([r["level"] for r in rows], [str(r["level"]) for r in rows])
        ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.legend()
    return fig


def run(mode: str, output: Path) -> None:
    # Keep optional library/font caches in the workspace, including on hosts
    # whose home directory is read-only. Respect explicit caller overrides.
    for name, directory in (("MPLCONFIGDIR", ROOT/"work/matplotlib"), ("XDG_CACHE_HOME", ROOT/"work/cache")):
        os.environ.setdefault(name, str(directory))
        Path(os.environ[name]).mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("Install the visualization extra or requirements/visualization-py312.txt") from exc
    plt.rcParams.update({"svg.hashsalt": "options-engine-v1", "axes.grid": True,
                         "grid.alpha": .25, "font.size": 10})
    output.mkdir(parents=True, exist_ok=True)
    figures, tables = output/"figures", output/"tables"
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    meta = provenance(mode)
    start_all = perf_counter()
    data = {"metadata": meta}

    def save(name, fig):
        fig.tight_layout()
        fig.savefig(figures/f"{name}.png", dpi=150)
        fig.savefig(figures/f"{name}.svg", metadata={"Date": None})
        plt.close(fig)

    def timed(call):
        start = perf_counter()
        value = call()
        return value, perf_counter()-start

    print("European spatial and temporal refinements", flush=True)
    european = []
    reference = bsm_price(100, 100, 1, .05, .2)
    for study, levels in (("spatial", (80, 160, 320, 640)), ("temporal", (25, 50, 100, 200))):
        for level in levels:
            m, nt = (level, 400) if study == "spatial" else (400, level)
            result, seconds = timed(lambda: fd_price(100, 100, 1, .05, .2, exercise_style="european", config=FDConfig(m, nt, 400)))
            european.append(dict(study=study, level=level, M=m, Nt=nt, Smax=400,
                price=result.price, reference=reference, absolute_error=abs(result.price-reference), seconds=seconds))
    data["european"] = european
    write_csv(tables/"european.csv", european)
    fig = european_figure(plt, european)
    save("european_convergence", fig)

    print("American CN/PSOR and independent even/odd CRR", flush=True)
    american, surfaces, boundaries = [], [], []
    finest = {}
    for kind, r, q in (("put", .05, 0), ("call", .02, .10)):
        for m in (80, 160, 320, 640):
            result, seconds = timed(lambda: fd_price(100, 100, 1, r, .2, q, kind, config=FDConfig(m, 200, 400)))
            american.append(dict(case=kind, method="CN/PSOR", level=m, M=m, Nt=200, Smax=400,
                rate=r, yield_=q, price=result.price, seconds=seconds, residual=result.max_residual))
            if m == 640:
                finest[kind] = result
        levels = (100, 200, 400, 800) if mode == "quick" else (200, 400, 1200, 2400)
        for n in levels:
            for parity in (0, 1):
                result, seconds = timed(lambda: crr_price(100, 100, 1, r, .2, q, kind, steps=n+parity))
                american.append(dict(case=kind, method="CRR odd" if parity else "CRR even", level=n+parity,
                    rate=r, yield_=q, price=result.price, european=result.european_price,
                    premium=result.early_exercise_premium, seconds=seconds))
        control = fd_price(100, 100, 1, r, .2, q, kind, exercise_style="european", config=FDConfig(640, 200, 400))
        for s, va, ve in zip(finest[kind].spots, finest[kind].values, control.values):
            if 40 <= s <= 160:
                surfaces.append(dict(case=kind, spot=s, premium=va-ve, american=va, european=ve))
        boundaries.extend(dict(case=kind, remaining_time=t, contact=s) for t, s in finest[kind].exercise_boundary)
    data.update(american=american, premium=surfaces, boundary=boundaries)
    for name, rows in (("american", american), ("premium", surfaces), ("boundary", boundaries)):
        write_csv(tables/f"{name}.csv", rows)
    refs = {}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, kind in zip(axes, ("put", "call")):
        crr = [row for row in american if row["case"] == kind and row["method"].startswith("CRR")]
        refs[kind] = sum(row["price"] for row in crr[-2:])/2
        for method in ("CN/PSOR", "CRR even", "CRR odd"):
            rows = [row for row in american if row["case"] == kind and row["method"] == method]
            ax.plot([x["level"] for x in rows], [x["price"] for x in rows], "o-", label=method)
        ax.set(xlabel="Spatial intervals M / tree steps N", ylabel="Price (currency/unit)", title=f"American {kind}")
        ax.legend()
    save("american_convergence", fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for study in ("spatial", "temporal"):
        rows = [r for r in european if r["study"] == study]
        axes[0].loglog([r["seconds"] for r in rows], [r["absolute_error"] for r in rows], "o-", label=f"European {study}")
    for kind in ("put", "call"):
        for method in ("CN/PSOR", "CRR even", "CRR odd"):
            rows = [r for r in american if r["case"] == kind and r["method"] == method]
            axes[1].loglog([r["seconds"] for r in rows], [max(abs(r["price"]-refs[kind]), 1e-15) for r in rows], "o-", label=f"{kind}: {method}")
    for ax in axes:
        ax.set(xlabel="Single solve wall time (seconds)", ylabel="Absolute price difference (currency/unit)")
        ax.legend(fontsize=7)
    axes[0].set_title("European error vs exact BSM")
    axes[1].set_title("American difference vs finest CRR pair (proxy)")
    save("error_cost", fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for kind in ("put", "call"):
        rows = [r for r in surfaces if r["case"] == kind]
        axes[0].plot([x["spot"] for x in rows], [x["premium"] for x in rows], label=kind)
        rows = [r for r in boundaries if r["case"] == kind and r["contact"] is not None]
        axes[1].step([x["remaining_time"] for x in rows], [x["contact"] for x in rows], where="post", label=kind)
    axes[0].set(xlabel="Spot (currency)", ylabel="American − European (currency/unit)", title="Early exercise premium: same FD grid")
    axes[1].set(xlabel="Remaining maturity (years)", ylabel="Contact spot (currency)", title="Grid-estimated exercise boundary")
    for ax in axes:
        ax.legend()
    save("exercise", fig)

    print(f"Numerical Greek studies ({mode})", flush=True)
    risk = run_studies(quick=mode == "quick")
    data["risk"] = risk
    risk_rows = []
    for case, studies in risk.items():
        for study, runs in studies.items():
            for setting, row in runs.items():
                risk_rows.append(dict(case=case, study=study, setting=setting,
                    **{name: row[name]["value"] for name in ("delta", "gamma", "vega", "theta", "rho")},
                    bumps=row["bumps"], config=row["fd_config"],
                    flags={name: row[name]["flags"] for name in ("delta", "gamma", "vega", "theta", "rho")}))
    write_csv(tables/"greeks.csv", risk_rows)
    first_case = next(iter(risk))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for col, study in enumerate(("bumps", "spatial")):
        rows = [r for r in risk_rows if r["case"] == first_case and r["study"] == study]
        for ax, greek in zip(axes[:, col], ("gamma", "vega")):
            ax.plot([float(x["setting"]) for x in rows], [x[greek] for x in rows], "o-", label="American put")
            ax.set(xlabel="Bump scale (mesh fixed)" if study == "bumps" else "Spatial M (bumps fixed)",
                   ylabel="Gamma (per spot²)" if greek == "gamma" else "Vega (per absolute volatility)",
                   title=f"{greek.capitalize()}: separate {study} study")
            ax.legend()
    save("greek_stability", fig)

    print("Portfolio P&L and self-financing hedge ledgers", flush=True)
    market, book, scenarios = portfolio_inputs()
    initial = value_portfolio(book, market)
    pnl_rows = []
    for scenario in scenarios:
        result = scenario_pnl(book, market, scenario, initial=initial)
        pnl_rows.append(dict(**asdict(scenario), exact=result.exact_pnl,
            first=result.first_order_pnl, second=result.second_order_pnl, residual=result.second_order_residual,
            cash=result.cash, settlement_cash=result.settlement_cash_at_horizon, options=result.option_value,
            flags=result.flags, ledger=[asdict(leg) for leg in result.positions]))
    data["portfolio"] = pnl_rows
    write_csv(tables/"portfolio.csv", pnl_rows)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, rows in zip(axes, (pnl_rows[:6], pnl_rows[6:7])):
        for offset, field in ((-.25, "exact"), (0, "first"), (.25, "second")):
            ax.bar([i+offset for i in range(len(rows))], [r[field] for r in rows], width=.25, label=field)
        ax.set_xticks(range(len(rows)), [r["label"] for r in rows], rotation=25, ha="right")
        ax.set(ylabel="P&L (currency)", title="Small isolated/combined shocks" if len(rows)>1 else "Large combined shock")
        ax.legend()
    save("portfolio_pnl", fig)

    market, book, paths, settings = hedge_inputs()
    hedge_rows, histories, decomposition = [], [], []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (case, path) in zip(axes, paths.items()):
        for strategy, k in settings:
            result = simulate_delta_hedge(book, market, path, strategy=strategy, rebalance_every=k, initial_wealth=1000)
            label = f"dynamic/{k}" if strategy == "dynamic" else strategy
            hedge_rows.append(dict(case=case, strategy=strategy, every=k, final=result.final_wealth,
                risk_free=result.risk_free_wealth, excess=result.excess_wealth,
                max_rebalance_error=max(abs(row.rebalance_error) for row in result.history)))
            for row in result.history:
                histories.append(dict(case=case, strategy=label, time=row.time, spot=row.spot,
                    options=row.option_value, delta_used=row.delta_used, shares=row.shares_after,
                    trade_cost=row.trade_cost, dividends=row.dividends, financing=row.financing,
                    settlement=row.settlement_cash, cash=row.cash, wealth=row.wealth,
                    warnings=row.warnings, used_warned_delta=row.used_warned_delta,
                    reconciliation_error=row.reconciliation_error))
            ax.plot([r.time for r in result.history], [r.wealth for r in result.history], label=label)
            if strategy == "dynamic" and k == 1:
                decomposition.append(dict(case=case, option=result.option_pnl, stock=result.stock_pnl,
                    dividends=result.dividends, financing=result.financing, total=result.pnl))
        ax.set(xlabel="Elapsed time (years)", ylabel="Wealth (currency)", title=case)
        ax.legend(fontsize=7)
    save("hedge_wealth", fig)
    data.update(hedge=hedge_rows, hedge_components=decomposition)
    for name, rows in (("hedge", hedge_rows), ("hedge_ledger", histories), ("hedge_components", decomposition)):
        write_csv(tables/f"{name}.csv", rows)
    fig, ax = plt.subplots(figsize=(9, 4))
    positives, negatives = [0.]*3, [0.]*3
    for field in ("option", "stock", "dividends", "financing"):
        values = [r[field] for r in decomposition]
        bottoms = [positives[i] if v>=0 else negatives[i] for i, v in enumerate(values)]
        ax.bar(range(3), values, bottom=bottoms, label=field)
        positives = [positives[i]+max(v,0) for i,v in enumerate(values)]
        negatives = [negatives[i]+min(v,0) for i,v in enumerate(values)]
    ax.scatter(range(3), [r["total"] for r in decomposition], color="black", label="Total P&L", zorder=3)
    ax.set_xticks(range(3), [r["case"] for r in decomposition])
    ax.set(ylabel="Interval P&L components (currency)", title="Dynamic/1 hedge: signed P&L decomposition")
    ax.legend(ncol=5, fontsize=8)
    save("hedge_components", fig)

    if mode == "full":
        print("Regenerating original detailed example reports", flush=True)
        reports = output/"reports"
        reports.mkdir(exist_ok=True)
        import greeks_and_american, finite_difference_validation, portfolio_validation, delta_hedging_validation
        for name, function in (("greeks_and_american", greeks_and_american.main),
                               ("finite_difference", finite_difference_validation.main),
                               ("portfolio", portfolio_validation.main), ("delta_hedging", delta_hedging_validation.main)):
            with (reports/f"validation_{name}.md").open("w") as stream, redirect_stdout(stream):
                function()
        with (reports/"validation_american_greeks.md").open("w") as stream, redirect_stdout(stream):
            print_report(risk)
        example = subprocess.run([sys.executable, str(ROOT/"examples/bsm_price.py")], check=True, capture_output=True, text=True)
        (reports/"bsm_example.txt").write_text(example.stdout)
    meta["total_wall_seconds"] = perf_counter()-start_all
    (output/"data.json").write_text(json.dumps(data, indent=2))
    artifacts = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    (output/"manifest.json").write_text(json.dumps(dict(metadata=meta, artifacts=artifacts), indent=2))
    print(f"Generated {len(artifacts)} artifacts in {output} ({meta['total_wall_seconds']:.1f}s)")


def refresh_presentation(output: Path) -> None:
    """Re-render only European axes from saved measurements, retaining provenance."""
    for key, path in (("MPLCONFIGDIR", ROOT/"work/matplotlib"), ("XDG_CACHE_HOME", ROOT/"work/cache")):
        os.environ.setdefault(key, str(path))
        Path(os.environ[key]).mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"svg.hashsalt": "options-engine-v1", "axes.grid": True,
                         "grid.alpha": .25, "font.size": 10})
    data = json.loads((output/"data.json").read_text())
    figure = european_figure(plt, data["european"])
    figure.tight_layout()
    figure.savefig(output/"figures/european_convergence.png", dpi=150)
    figure.savefig(output/"figures/european_convergence.svg", metadata={"Date": None})
    plt.close(figure)
    manifest = json.loads((output/"manifest.json").read_text())
    for suffix in ("png", "svg"):
        name = f"figures/european_convergence.{suffix}"
        manifest["artifacts"][name] = hashlib.sha256((output/name).read_bytes()).hexdigest()
    manifest["presentation_refresh"] = {
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "change": "Explicit European log-axis labels; original numerical measurements/provenance retained"}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Refreshed European figure labels from saved data; numerical results unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("quick", "full"), default="quick")
    parser.add_argument("--output", type=Path, default=Path("work/results"))
    parser.add_argument("--refresh-presentation", action="store_true", help="Render European labels from saved data, no repricing")
    arguments = parser.parse_args()
    if arguments.refresh_presentation:
        refresh_presentation(arguments.output)
    else:
        run(arguments.mode, arguments.output)
