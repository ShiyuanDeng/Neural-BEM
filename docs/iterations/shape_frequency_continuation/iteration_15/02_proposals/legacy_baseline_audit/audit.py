"""Read saved legacy/SC-030 artifacts; no optimizer or field solver is imported."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
BASE = ROOT / "results/validation/shape_continuation"
INPUT_HASHES = {}
THETA = np.arange(4096) * (2 * np.pi / 4096)


def read(path, lines=False):
    raw = path.read_bytes()
    INPUT_HASHES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return [json.loads(x) for x in raw.splitlines()] if lines else json.loads(raw)


def cartesian(state):
    k = state["maximum_mode"]
    v = np.asarray(state["parameters"])
    c = v[:2 * (k + 1)].reshape(k + 1, 2)
    s = np.vstack((np.zeros(2), v[2 * (k + 1):].reshape(k, 2)))
    phase = THETA[:, None] * np.arange(k + 1)
    return np.cos(phase) @ c + np.sin(phase) @ s


def package_points(shape):
    c = np.array(shape["real"]) + 1j * np.array(shape["imag"])
    k = len(c) // 2
    z = .5 + .5j + .05 * (np.exp(1j * THETA[:, None] * np.arange(-k, k + 1)) @ c)
    return np.column_stack((z.real, z.imag))


def radial_metrics(row):
    state = row["state"][0]
    offsets = cartesian(state) - np.asarray(state["parameters"][:2])
    radius = np.linalg.norm(offsets, axis=1)
    spectrum = np.fft.rfft(radius) / len(radius)
    return dict(iteration=row["iteration"], loss=row["loss"], damping=row["damping"],
                sampled_minimum_radius_mm=1000 * float(radius.min()),
                radius_certificate_mm=1000 * float(spectrum[0].real - 2 * abs(spectrum[2:18]).sum()),
                radial_above_mode5_rms_mm=1000 * float(np.sqrt(2 * np.sum(abs(spectrum[6:]) ** 2))))


def main():
    legacy = BASE / "SC-018-legacy-single-object"
    comparison = BASE / "SC-030-spd008-comparison/runs/repeat_0"
    report = dict(physical_field_solves=0, inverse_runs=0, geometry_grid=4096,
                  interpretation="Saved-artifact audit; not a causal optimizer ablation.")
    report["legacy_results"] = []
    for folder in sorted((legacy / "runs").glob("*/legacy_cartesian")):
        result = read(folder / "result.json")
        trace = read(folder / "trajectory.json")
        counts = Counter(row["stage"] for row in trace)
        report["legacy_results"].append(dict(case=result["case"], passed=result["passed"],
            boundary_upper_mm=1000 * result["scores"]["boundary_upper_m"],
            sampled_boundary_mm=1000 * result["scores"]["boundary_m"],
            accepted_updates_by_stage={str(k): n - 1 for k, n in counts.items()},
            first_loss=.5 * trace[0]["residual"] ** 2))
    assert len(report["legacy_results"]) == 6 and all(x["passed"] for x in report["legacy_results"])

    report["common_cases"] = []
    for old, new in (("circle-to-circle", "wrong_circle"), ("circle-to-star", "circle_to_star")):
        data = read(legacy / "inputs" / old / "input.json")
        catalog = read(BASE / "SC-022-atlas-survey/inputs" / new / "observations.json")
        truth = read(BASE / "SC-022-atlas-survey/inputs" / new / "truth.json")
        a = np.array(data["observations"]["real"]) + 1j * np.array(data["observations"]["imag"])
        b = np.array(catalog["observed_real"]) + 1j * np.array(catalog["observed_imag"])
        folder = comparison / new / "spd008"
        trajectory = read(folder / "stage_1/trajectory.jsonl", lines=True)
        initial = cartesian(trajectory[0]["state"][0])
        displacement = cartesian(trajectory[1]["state"][0]) - initial
        first_normal = np.sum(displacement * np.column_stack((np.cos(THETA), np.sin(THETA))), axis=1)
        row = dict(case=new,
            initial_curve_difference_m=float(np.max(np.linalg.norm(initial - package_points(data["initial"]), axis=1))),
            truth_curve_difference_m=float(np.max(np.linalg.norm(package_points(truth) - package_points(data["truth"]), axis=1))),
            common_observation_relative_differences={str(f): float(np.linalg.norm(a[:, i] - b[:, catalog["frequencies_hz"].index(f * 1e9)]) / np.linalg.norm(a[:, i])) for i, f in enumerate(data["frequencies_ghz"])},
            first_accepted_initial_normal_displacement_mm=1000 * float(np.max(abs(first_normal))),
            stage1_radial_history=[radial_metrics(x) for x in trajectory], stages=[])
        for stage in sorted(folder.glob("stage_*/terminal.json")):
            terminal = read(stage)
            record = {k: terminal[k] for k in ("accepted_steps", "stage_outcome", "reason", "production_loss", "one_sided_columns", "unresolved_columns", "active_frequencies_hz")}
            record["stage"] = stage.parent.name
            refusals = stage.parent / "feasibility.jsonl"
            if refusals.exists():
                record["refusals"] = dict(Counter(x["reason"] for x in read(refusals, lines=True)))
            row["stages"].append(record)
        assert row["initial_curve_difference_m"] < 1e-9
        assert row["truth_curve_difference_m"] < 1e-12
        assert max(row["common_observation_relative_differences"].values()) < 1e-9
        report["common_cases"].append(row)

    historical = read(ROOT / "results/inverse/cartesian_fourier/cartesian-k6-ellipse-to-star-nystrom-kress-20260910/metrics.json")
    report["historical_ellipse_star_config"] = historical["inverse_config"]
    report["historical_ellipse_star_stages"] = historical["continuation_stages"]
    manifest = read(legacy / "manifest.json")
    report["legacy_numerical_sources_still_match_SC018"] = {}
    for name in ("solvers/sdf_inverse/neural_optimization.py", "solvers/sdf_inverse/curve_updates.py", "run_explicit_cartesian_fourier_inverse.py", "experiments/shape_continuation/legacy_cases.py"):
        digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        INPUT_HASHES[name] = digest
        report["legacy_numerical_sources_still_match_SC018"][name] = digest == manifest["source_sha256"][name]
    assert all(report["legacy_numerical_sources_still_match_SC018"].values())
    report["input_sha256"] = dict(sorted(INPUT_HASHES.items()))
    destination = Path(__file__).with_name("audit.json")
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("PASS: six legacy recoveries; common starts/truth/data verified; zero field solves.")


if __name__ == "__main__":
    main()
