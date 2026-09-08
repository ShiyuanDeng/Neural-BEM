#!/usr/bin/env python3
"""Bound observed coarse/fine spectral changes without repeating BEM solves.

The bound compares the two discretizations in an existing observability bundle.
It is not an error bound against the continuum problem or a noise certificate.
Existing result files are read only; two additional audit files are created.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys


THRESHOLDS = (1e-2, 1e-3, 1e-4)
INPUT_FILES = (
    "metrics.json", "resolution_validation.csv",
    "physical_jacobian.csv", "modal_jacobian.csv",
)


def _nonnegative(value, name):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return number


def rank_intervals(singular_values, delta, real_rows, columns, thresholds=THRESHOLDS):
    """Certify relative-threshold ranks for any matrix within spectral norm delta.

    Weyl bounds each singular value by +/- delta. The threshold's leading
    singular value is also allowed to change by +/- delta. Dimension-forced
    zeros stay exactly zero under any perturbation of the same matrix shape.
    """

    values = [_nonnegative(v, "singular value") for v in singular_values]
    delta = _nonnegative(delta, "delta")
    if real_rows < 1 or columns < 1 or len(values) != columns:
        raise ValueError("Supply positive matrix dimensions and one singular value per column.")
    if any(a < b for a, b in zip(values, values[1:])):
        raise ValueError("Singular values must be sorted in descending order.")
    ceiling = min(real_rows, columns)
    if any(value != 0 for value in values[ceiling:]):
        raise ValueError("Dimension-forced singular values must be zero.")
    leading_low, leading_high = max(0.0, values[0] - delta), values[0] + delta
    intervals = [
        {
            "index": i,
            "fine_value": value,
            "coarse_lower_bound": max(0.0, value - delta) if i < ceiling else 0.0,
            "coarse_upper_bound": value + delta if i < ceiling else 0.0,
            "structural_zero": i >= ceiling,
        }
        for i, value in enumerate(values)
    ]
    ranks = []
    for threshold in thresholds:
        threshold = float(threshold)
        if not 0 < threshold < 1:
            raise ValueError("Relative thresholds must lie strictly between zero and one.")
        above, below, unresolved = [], [], []
        for interval in intervals:
            i = interval["index"]
            if interval["structural_zero"]:
                below.append(i)
            elif interval["coarse_lower_bound"] > threshold * leading_high:
                above.append(i)
            elif interval["coarse_upper_bound"] <= threshold * leading_low:
                below.append(i)
            else:
                unresolved.append(i)
        ranks.append({
            "relative_threshold": threshold,
            "nominal_fine_rank": sum(v > threshold * values[0] for v in values),
            "guaranteed_minimum_rank": len(above),
            "guaranteed_maximum_rank": columns - len(below),
            "certainly_above_indices": above,
            "certainly_at_or_below_indices": below,
            "unresolved_indices": unresolved,
            "rank_is_certified": not unresolved,
        })
    return intervals, ranks


def _read_table(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def _key(row):
    return (row["location"], row["acquisition"], float(row["frequency_ghz"]), row["direction"])


def _unique_rows(rows):
    result = {}
    for row in rows:
        key = _key(row)
        if key in result:
            raise ValueError(f"Duplicate input row {key}.")
        result[key] = row
    return result


def audit_bundle(input_dir):
    """Compute a Frobenius/Weyl bound from per-column refinement differences."""

    input_dir = Path(input_dir)
    metrics = json.loads((input_dir / "metrics.json").read_text())
    changes = _unique_rows(_read_table(input_dir / "resolution_validation.csv"))
    sensitivities = {
        family: _unique_rows(_read_table(input_dir / f"{family}_jacobian.csv"))
        for family in ("physical", "modal")
    }
    spectra, flat_rows = [], []
    for spectrum in metrics["spectra"]:
        metadata = {name: spectrum[name] for name in (
            "location", "acquisition", "frequencies_ghz", "family", "weighting",
        )}
        if metadata["weighting"] not in ("absolute", "target_relative"):
            raise ValueError(f"Unknown spectrum weighting {metadata['weighting']}.")
        table = sensitivities[metadata["family"]]
        squared_differences = []
        directions = None
        for frequency in map(float, metadata["frequencies_ghz"].split("+")):
            selected = {
                key[3]: row for key, row in table.items()
                if key[:3] == (metadata["location"], metadata["acquisition"], frequency)
            }
            if len(selected) != spectrum["columns"]:
                raise ValueError(f"Missing sensitivity columns for {metadata}, {frequency} GHz.")
            if directions is not None and directions != set(selected):
                raise ValueError("The stacked frequencies must use the same column directions.")
            directions = set(selected)
            for direction, row in selected.items():
                change = changes.get(_key(row))
                if change is None:
                    raise ValueError(f"Missing refinement change for {_key(row)}.")
                error = _nonnegative(change["relative_change"], "relative refinement change")
                # The original driver fixes BOTH coarse and fine matrices to
                # the fine exact-target norm. Thus this column norm gives the
                # same per-frequency scale used by each reported spectrum.
                norm_key = ("sensitivity_norm_1mm" if metadata["weighting"] == "absolute"
                            else "relative_sensitivity_1mm")
                norm = _nonnegative(row[norm_key], norm_key)
                # The producer's relative() denominator has a 1e-30 floor.
                # Multiplication by the fine norm reconstructs the difference
                # only when that floor is inactive (or the difference is zero).
                native_norm = row.get("native_complex_sensitivity_norm")
                if error > 0 and (norm == 0 or (
                    native_norm is not None
                    and _nonnegative(native_norm, "native sensitivity norm") < 1e-30
                )):
                    raise ValueError("A zero/floored fine column needs its absolute refinement difference to certify a bound.")
                squared_differences.append((error * norm) ** 2)
        delta = math.sqrt(math.fsum(squared_differences))
        intervals, ranks = rank_intervals(
            spectrum["singular_values"], delta,
            spectrum["real_rows"], spectrum["columns"],
        )
        leading = spectrum["singular_values"][0]
        relative_delta = delta / leading if leading > 0 else (0.0 if delta == 0 else None)
        detail = dict(
            **metadata, real_rows=spectrum["real_rows"], columns=spectrum["columns"],
            coarse_fine_frobenius_bound=delta,
            bound_relative_to_fine_largest_singular_value=relative_delta,
            singular_value_intervals=intervals, rank_intervals=ranks,
        )
        spectra.append(detail)
        for rank in ranks:
            flat_rows.append(dict(
                **metadata, real_rows=spectrum["real_rows"], columns=spectrum["columns"],
                coarse_fine_frobenius_bound=delta,
                bound_relative_to_fine_largest_singular_value=relative_delta,
                **{name: rank[name] for name in (
                    "relative_threshold", "nominal_fine_rank", "guaranteed_minimum_rank",
                    "guaranteed_maximum_rank", "rank_is_certified",
                )},
                uncertain_singular_value_count=len(rank["unresolved_indices"]),
            ))
    if not spectra:
        raise ValueError("The input metrics contain no spectra.")
    result = {
        "input_dir": str(input_dir.resolve()),
        "utc": datetime.now(timezone.utc).isoformat(),
        "coarse_nodes": metrics["configuration"]["num_nodes"],
        "fine_nodes": metrics["configuration"]["refined_nodes"],
        "input_sha256": {name: hashlib.sha256((input_dir / name).read_bytes()).hexdigest()
                         for name in INPUT_FILES},
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "method": {
            "delta": "sqrt(sum_(frequency,column) (relative_column_change * fine_scaled_column_norm)^2)",
            "inequality": "abs(sigma_i(coarse)-sigma_i(fine)) <= ||J_coarse-J_fine||_2 <= delta_F",
            "real_stacking": "Real stacking preserves the sum of squared complex column norms.",
            "normalization": "Both resolutions use the same fine target norm per frequency for target_relative spectra.",
            "certainly_above": "sigma_i(fine)-delta > threshold*(sigma_0(fine)+delta)",
            "certainly_at_or_below": "sigma_i(fine)+delta <= threshold*max(0,sigma_0(fine)-delta); dimension-forced zeros are exact",
            "scope": "A bound on measured coarse/fine spectral changes only; not a continuum discretization error bound, statistical usable rank, or nonlinear recovery certificate.",
        },
        "relative_thresholds": list(THRESHOLDS),
        "summary": {
            "spectrum_count": len(spectra),
            "threshold_rows": len(flat_rows),
            "certified_threshold_rows": sum(row["rank_is_certified"] for row in flat_rows),
            "uncertain_threshold_rows": sum(not row["rank_is_certified"] for row in flat_rows),
        },
        "spectra": spectra,
    }
    return result, flat_rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, help="Defaults to the input result directory.")
    args = parser.parse_args(argv)
    output = args.output_dir or args.input_dir
    csv_path, json_path = (output / f"spectrum_refinement.{suffix}" for suffix in ("csv", "json"))
    if csv_path.exists() or json_path.exists():
        raise FileExistsError("Refusing to replace an existing spectrum refinement audit.")
    result, rows = audit_bundle(args.input_dir)
    output.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
