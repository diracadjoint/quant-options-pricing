"""Verify generated files, measured regression values and accounting (offline)."""

import hashlib
import json
from pathlib import Path
import sys


def main(directory: Path) -> None:
    data = json.loads((directory/"data.json").read_text())
    manifest = json.loads((directory/"manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        file = directory/name
        assert file.is_file(), f"Missing artifact {name}"
        assert hashlib.sha256(file.read_bytes()).hexdigest() == expected, f"Changed artifact {name}"
    assert len(list((directory/"figures").glob("*.png"))) == 8
    assert len(list((directory/"figures").glob("*.svg"))) == 8
    assert len(data["european"]) == 8
    for study in ("spatial", "temporal"):
        assert len([r for r in data["european"] if r["study"] == study]) == 4
    for row in data["european"]:
        assert abs(row["reference"]-10.450583572185565) < 1e-11
    expected_fd = {"put": 6.088839418925684, "call": 5.223876774933277}
    for row in data["american"]:
        if row["method"] == "CN/PSOR":
            assert row["residual"] <= 1e-8
            if row["level"] == 640:
                assert abs(row["price"]-expected_fd[row["case"]]) < 1e-7
    for row in data["portfolio"]:
        if row["label"] == "small combined":
            assert abs(row["exact"]-92.514589) < 2e-6
        if row["label"] == "American expiry":
            assert row["first"] is None and row["second"] is None
            assert any("expiry" in flag for flag in row["flags"])
    expected_hedge = {"rise": 1338.92099701, "fall": 1315.64159935, "reversal": 1562.73426517}
    for row in data["hedge"]:
        assert row["max_rebalance_error"] < 1e-9
        if row["strategy"] == "dynamic" and row["every"] == 1:
            assert abs(row["final"]-expected_hedge[row["case"]]) < 1e-7
    for row in data["hedge_components"]:
        assert abs(sum(row[k] for k in ("option", "stock", "dividends", "financing"))-row["total"]) < 1e-8
    first = next(iter(data["risk"].values()))
    assert any("interpolation-limited" in flag for flag in first["bumps"]["0.25"]["gamma"]["flags"])
    if manifest["metadata"]["mode"] == "full":
        assert len(list((directory/"reports").glob("*.md"))) == 5
        assert "spot bump smaller than grid spacing" in (directory/"reports/validation_delta_hedging.md").read_text()
    print(f"Verified {len(manifest['artifacts'])} artifacts, measured reference values, warnings and ledger identities")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_results.py OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
