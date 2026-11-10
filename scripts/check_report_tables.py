"""Compare retained measured Markdown tables with freshly regenerated reports.

Only wall-clock Seconds columns are excluded. Financial times, flags, prices,
quantities, Greek values and accounting cells must remain unchanged.
"""

from pathlib import Path
from math import isclose
import sys


ROOT = Path(__file__).resolve().parents[1]


def cells(path: Path) -> list[tuple[str, ...]]:
    result, ignored = [], set()
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            ignored = set()
            continue
        row = tuple(s.strip() for s in line.strip().strip("|").split("|"))
        if all(set(value) <= set("-: ") for value in row):
            continue
        if any("seconds" in s.lower() for s in row):
            ignored = {i for i, s in enumerate(row) if "seconds" in s.lower()}
        result.append(tuple(s for i, s in enumerate(row) if i not in ignored))
    return result


def main(directory: Path) -> None:
    pairs = {
        "validation_greeks_american.md": "validation_greeks_and_american.md",
        "validation_finite_difference.md": "validation_finite_difference.md",
        "validation_american_greeks.md": "validation_american_greeks.md",
        "validation_portfolio.md": "validation_portfolio.md",
        "validation_delta_hedging.md": "validation_delta_hedging.md",
    }
    for previous, current in pairs.items():
        expected = cells(ROOT/"docs"/previous)
        measured = cells(directory/"reports"/current)
        def same(a, b):
            try:
                return isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-7)
            except ValueError:
                return a == b
        if len(expected) != len(measured):
            raise SystemExit(f"Table length mismatch in {previous}: {len(expected)} != {len(measured)}")
        for index, (a, b) in enumerate(zip(expected, measured)):
            if len(a) != len(b) or not all(same(x,y) for x,y in zip(a,b)):
                raise SystemExit(f"Table mismatch in {previous}, row {index}: {a} != {b}")
    print("All five retained financial reports match (abs=1e-7, rel=1e-10); wall timings excluded")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/check_report_tables.py FULL_OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
