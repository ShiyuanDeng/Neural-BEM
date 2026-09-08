"""Read-only diagnostics behind the iteration-2 third review.

Six independent probes over already-saved September 8 artifacts:

1. runtime split of one candidate evaluation (geometry build versus Kress solve)
   and a cProfile share of the geometry build;
2. on-contour field-gradient norms and radial spectra at selected accepted
   states, rebuilt from the saved trajectory weights;
3. proximity of the fixed Eikonal sample set to the final contours;
4. a forward-only data-misfit transect between saved contours and the exact
   target contour, in curve space;
5. single-mode data sensitivity of the correction toward the target at the
   final star state;
6. line-search statistics recomputed from the saved trial records.

No inverse is run, no weights are changed, and no saved result is modified.
Probe 4 and 5 solve Kress on curves built from saved node sets; they never
touch the neural field.  Probe 4 is self-checked against the recorded final
training loss.
"""

from __future__ import annotations

import collections
import cProfile
import csv
import hashlib
import io
import json
import pstats
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "solvers"))
sys.path.insert(0, str(ROOT))   # the repository's own config package must win

from ordered_boundary import PeriodicParameterization2D  # noqa: E402
from sdf_inverse import forward as F  # noqa: E402
from sdf_inverse.geometry import (  # noqa: E402
    OrderedSDFGeometryConfig,
    build_ordered_sdf_geometry,
)
from sdf_inverse.models import SirenImplicitField2D  # noqa: E402
from sdf_inverse.optimization import normalized_complex_residual  # noqa: E402

BUNDLES = ROOT / "results/inverse/implicit_mlp/2026-09-08"
STATES = {"star": (0, 8, 16, 24, 32, 40, 47), "circle": (0, 20, 40, 55, 60)}
CITED_SOURCES = (
    "solvers/sdf_inverse/implicit_adjoint.py",
    "solvers/sdf_inverse/geometry.py",
    "solvers/sdf_inverse/forward.py",
    "solvers/sdf_to_ordered_boundary/frontend.py",
    "run_sdf_inverse_comparison.py",
)
EPS0 = 8.8541878128e-12
MU0 = 1.25663706212e-6


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_case(case: str):
    checkpoint = torch.load(BUNDLES / case / "kress_model.pt", map_location="cpu",
                            weights_only=False)
    constructor = dict(checkpoint["constructor"])
    constructor["dtype"] = torch.float64
    model = SirenImplicitField2D(**constructor)
    model.load_state_dict(checkpoint["state_dict"])
    settings = dict(checkpoint["geometry_config"])
    settings["bounds"] = tuple(tuple(v) for v in settings["bounds"])
    settings["grid_shape"] = tuple(settings["grid_shape"])
    return model, OrderedSDFGeometryConfig(**settings), checkpoint


def assign(model, vector: np.ndarray) -> None:
    offset = 0
    with torch.no_grad():
        for parameter in model.parameters():
            count = parameter.numel()
            parameter.copy_(torch.tensor(vector[offset:offset + count],
                                         dtype=parameter.dtype).reshape(parameter.shape))
            offset += count


def trajectory_states(case: str) -> dict[int, np.ndarray]:
    rows = list(csv.reader(open(BUNDLES / case / "kress_trajectory.csv")))
    header = rows[0]
    columns = [index for index, name in enumerate(header) if name.startswith("raw_")]
    iteration = header.index("iteration")
    return {int(float(row[iteration])): np.array([float(row[i]) for i in columns])
            for row in rows[1:]}


def contour_gradient_norms(model, points: np.ndarray) -> np.ndarray:
    tensor = torch.tensor(points, dtype=torch.float64, requires_grad=True)
    gradients = torch.autograd.grad(model(tensor).reshape(-1).sum(), tensor)[0]
    return gradients.norm(dim=1).detach().numpy()


def radial_spectrum(points: np.ndarray, samples: int = 512):
    """Polar-radius Fourier amplitudes about the polygon centroid."""
    x, y = points[:, 0], points[:, 1]
    xr, yr = np.roll(x, -1), np.roll(y, -1)
    weights = x * yr - xr * y
    area = weights.sum() / 2.0
    cx = ((x + xr) * weights).sum() / (6.0 * area)
    cy = ((y + yr) * weights).sum() / (6.0 * area)
    angle = np.arctan2(y - cy, x - cx)
    radius = np.hypot(x - cx, y - cy)
    order = np.argsort(angle)
    single_valued = bool(np.all(np.diff(np.unwrap(angle)) > 0.0)
                         or np.all(np.diff(np.unwrap(angle)) < 0.0))
    grid = np.linspace(-np.pi, np.pi, samples, endpoint=False)
    resampled = np.interp(grid, angle[order], radius[order], period=2.0 * np.pi)
    spectral = np.fft.rfft(resampled) / samples
    amplitude = np.abs(spectral)
    amplitude[1:] *= 2.0
    perimeter = float(np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1).sum())
    return amplitude, perimeter, single_valued


def segment_distances(query: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    start = polygon
    edge = np.roll(polygon, -1, axis=0) - polygon
    projection = np.clip(((query[:, None, :] - start[None]) * edge[None]).sum(-1)
                         / np.maximum((edge * edge).sum(-1)[None], np.finfo(float).tiny),
                         0.0, 1.0)
    closest = start[None] + projection[..., None] * edge[None]
    return np.linalg.norm(query[:, None, :] - closest, axis=2).min(axis=1)


def trigonometric_interpolant(nodes: np.ndarray):
    """Exact interpolant through uniformly parameterized closed nodes."""
    count = nodes.shape[0]
    coefficients = np.fft.fft(nodes, axis=0) / count
    modes = np.fft.fftfreq(count, d=1.0 / count)
    if count % 2 == 0:                                   # split the Nyquist mode
        nyquist = count // 2
        coefficients[nyquist] *= 0.5
        coefficients = np.vstack([coefficients, coefficients[nyquist][None, :]])
        modes = np.concatenate([modes, [-modes[nyquist]]])

    def evaluate(parameters):
        parameters = np.asarray(parameters, dtype=np.float64).reshape(-1)
        phase = np.exp(1j * np.outer(parameters, modes))
        return (
            (phase @ coefficients).real.copy(),
            ((phase * (1j * modes)[None, :]) @ coefficients).real.copy(),
            ((phase * (-(modes ** 2))[None, :]) @ coefficients).real.copy(),
        )

    return evaluate


def curve_loss(nodes: np.ndarray, config, problem, observed) -> tuple[float, float]:
    parameterization = PeriodicParameterization2D(
        component_id="review-transect", evaluator=trigonometric_interpolant(nodes))
    curve = parameterization.discretize(config.num_nodes, require_even=True)
    build = F._curve_geometry_build(curve, config)
    result = F._predict_paired_response_from_geometry(
        build, problem, solver="kress", geometry_seconds=0.0,
        total_started=time.perf_counter())
    residual, relative = normalized_complex_residual(result.scattered_response, observed)
    return 0.5 * float(residual @ residual), float(relative)


def main() -> None:
    destination = Path(__file__).with_name("probe.json")
    if destination.exists():
        raise SystemExit(f"{destination} already exists; preserve it before repeating.")

    record: dict = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only diagnostics over saved September 8 bundles for the "
                 "iteration-2 third review. No inverse, no weight change, no "
                 "modified artifact.",
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "torch": torch.__version__,
            "platform": platform.platform(),
            "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         capture_output=True, text=True).stdout.strip(),
            "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                             capture_output=True, text=True).stdout.strip()),
        },
        "source_sha256": {name: sha256(ROOT / name) for name in CITED_SOURCES},
        "bundle_sha256": {
            f"{case}/{name}": sha256(BUNDLES / case / name)
            for case in ("star", "circle")
            for name in ("kress_model.pt", "metrics.json", "kress_trials.jsonl")
        },
    }

    # --- probes 1-3: runtime, field conditioning, spectra, sample proximity ---
    record["cases"] = {}
    for case in ("star", "circle"):
        model, config, checkpoint = load_case(case)
        metrics = json.load(open(BUNDLES / case / "metrics.json"))["solvers"]["kress"]
        experiment = json.load(open(BUNDLES / case / "metrics.json"))["experiment"]

        builds = []
        for _ in range(3):
            started = time.perf_counter()
            build = build_ordered_sdf_geometry(model, config)
            builds.append(time.perf_counter() - started)

        train = [float(v) for v in json.load(open(BUNDLES / case / "metrics.json"))["train_frequencies_ghz"]]
        responses = np.load(BUNDLES / case / "kress_responses.npz", allow_pickle=True)
        frequencies = responses["frequencies_ghz"]
        indices = [int(np.argmin(np.abs(frequencies - value))) for value in train]
        problem = F.PairedForwardProblem(
            source_points=np.asarray(experiment["source_points_m"]),
            receiver_points=np.asarray(experiment["receiver_points_m"]),
            angular_frequencies=2.0 * np.pi * 1.0e9 * np.asarray([frequencies[i] for i in indices]),
            source_strengths=1e-6 + 0j,
            exterior=F.MaterialSpec(**experiment["exterior"]),
            interior=F.MaterialSpec(**experiment["interior"]),
            eps0=EPS0, mu0=MU0)
        started = time.perf_counter()
        F._predict_paired_response_from_geometry(
            build, problem, solver="kress", geometry_seconds=0.0,
            total_started=started, retain_kress_state=True)
        solve_seconds = time.perf_counter() - started

        profiler = cProfile.Profile()
        profiler.enable()
        build_ordered_sdf_geometry(model, config)
        profiler.disable()
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        totals = {}
        for (path, _, name), (_, _, _, cumulative, _) in stats.stats.items():
            if name in ("build_ordered_sdf_geometry", "polygon_self_intersection_count",
                        "_check_conversion_fidelity", "fit_method_b", "evaluate_cartesian_grid",
                        "project_to_zero_set"):
                totals[name] = totals.get(name, 0.0) + float(cumulative)

        rng = np.random.default_rng(0)
        bounds = np.asarray(config.bounds, dtype=np.float64)
        samples = rng.uniform(bounds[0], bounds[1], (512, 2))
        final_contour = np.asarray(checkpoint["accepted_geometry_points"], dtype=np.float64)
        distances = segment_distances(samples, final_contour)

        states = {}
        weights = trajectory_states(case)
        for state in STATES[case]:
            assign(model, weights[state])
            state_build = build_ordered_sdf_geometry(model, config)
            points = np.asarray(state_build.curve.points, dtype=np.float64)
            norms = contour_gradient_norms(model, points)
            amplitude, perimeter, single_valued = radial_spectrum(points)
            variance = float((amplitude[1:] ** 2).sum())
            band = lambda lo, hi: float((amplitude[lo:hi + 1] ** 2).sum() / variance)
            states[str(state)] = {
                "minimum_contour_gradient_norm": float(norms.min()),
                "maximum_contour_gradient_norm": float(norms.max()),
                "contour_gradient_norm_ratio": float(norms.max() / norms.min()),
                "perimeter_m": perimeter,
                "radial_variation_rms_m": float(np.sqrt(variance / 2.0)),
                "radial_amplitude_m": {str(m): float(amplitude[m]) for m in range(0, 21)},
                "variance_share_modes_1_10": band(1, 10),
                "variance_share_modes_11_20": band(11, 20),
                "variance_share_modes_above_20": band(21, amplitude.size - 1),
                "single_valued_radius": single_valued,
                "conversion_error_m": state_build.maximum_conversion_error_m,
                "conversion_refinement_change_m": state_build.conversion_refinement_change_m,
            }
        assign(model, weights[max(weights)])

        trials = [json.loads(line) for line in open(BUNDLES / case / "kress_trials.jsonl")]
        solved = [t for t in trials if "loss" in t]
        record["cases"][case] = {
            "geometry_build_seconds": builds,
            "kress_solve_seconds_two_training_frequencies": solve_seconds,
            "profiled_cumulative_seconds": totals,
            "recorded_forward_seconds": metrics["inverse_forward_seconds"],
            "recorded_wall_seconds": metrics["inverse_wall_seconds"],
            "recorded_gradient_seconds": metrics["optimizer_diagnostics"]["gradient_seconds"],
            "recorded_evaluations": metrics["total_forward_evaluations"],
            "eikonal_samples_within_1mm": int((distances <= 1.0e-3).sum()),
            "eikonal_samples_within_2mm": int((distances <= 2.0e-3).sum()),
            "eikonal_samples_within_5mm": int((distances <= 5.0e-3).sum()),
            "eikonal_sample_minimum_distance_m": float(distances.min()),
            "states": states,
            "trials": len(trials),
            "trials_reaching_solve": len(solved),
            "trials_rejected_only_by_motion_cap": sum(
                1 for t in solved if t["rejection_reasons"] == ["boundary_motion_limit"]),
            "accepted_backtrack_histogram": dict(sorted(collections.Counter(
                t["backtracks"] for t in trials if t["accepted"]).items())),
            "rejection_reason_counts": dict(collections.Counter(
                reason for t in trials for reason in t.get("rejection_reasons", []))),
        }

    # --- probes 4-5: curve-space transect and single-mode sensitivity (star) ---
    metrics = json.load(open(BUNDLES / "star" / "metrics.json"))
    _, config, _ = load_case("star")
    responses = np.load(BUNDLES / "star" / "kress_responses.npz", allow_pickle=True)
    frequencies = responses["frequencies_ghz"]
    indices = [int(np.argmin(np.abs(frequencies - float(v))))
               for v in metrics["train_frequencies_ghz"]]
    observed = responses["exact_scattered_response"][:, indices]
    experiment = metrics["experiment"]
    problem = F.PairedForwardProblem(
        source_points=np.asarray(experiment["source_points_m"]),
        receiver_points=np.asarray(experiment["receiver_points_m"]),
        angular_frequencies=2.0 * np.pi * 1.0e9 * np.asarray([frequencies[i] for i in indices]),
        source_strengths=1e-6 + 0j,
        exterior=F.MaterialSpec(**experiment["exterior"]),
        interior=F.MaterialSpec(**experiment["interior"]),
        eps0=EPS0, mu0=MU0)

    final = np.asarray(responses["final_curve_points"], dtype=np.float64)
    initial = np.asarray(responses["initial_curve_points"], dtype=np.float64)
    target = np.asarray(responses["target_curve_points"], dtype=np.float64)
    grid = np.linspace(0.0, 2.0 * np.pi, final.shape[0], endpoint=False)

    transect = {"self_check": {
        "recorded_final_training_loss": metrics["solvers"]["kress"]["final_training_loss"],
        "recorded_final_training_relative_l2": metrics["solvers"]["kress"]["final_training_relative_l2"],
        "interpolant_node_reproduction_error_m": float(
            np.max(np.abs(trigonometric_interpolant(final)(grid)[0] - final))),
        "target_curve_maximum_distance_to_exact_boundary_m": float(
            segment_distances(target, np.asarray(responses["exact_boundary_points"])).max()),
    }}
    started = time.perf_counter()
    for name, source in (("final_to_target", final), ("initial_to_target", initial)):
        entries = []
        for alpha in np.linspace(0.0, 1.0, 21):
            loss, relative = curve_loss((1.0 - alpha) * source + alpha * target,
                                        config, problem, observed)
            entries.append({"alpha": float(alpha), "loss": loss, "relative_l2": relative})
        transect[name] = entries
    transect["seconds"] = time.perf_counter() - started

    correction = target - final
    count = correction.shape[0]
    coefficients = np.fft.fft(correction, axis=0) / count
    base_loss, _ = curve_loss(final, config, problem, observed)
    modal = {"base_loss": base_loss,
             "correction_rms_m": float(np.sqrt((np.linalg.norm(correction, axis=1) ** 2).mean())),
             "modes": []}
    for mode in list(range(0, 13)) + [15, 20]:
        component = np.zeros_like(correction)
        for index in ({mode} if mode == 0 else {mode, count - mode}):
            phase = np.exp(2j * np.pi * index * np.arange(count) / count)[:, None]
            component = component + (coefficients[index][None, :] * phase).real
        rms = float(np.sqrt((np.linalg.norm(component, axis=1) ** 2).mean()))
        unit_loss, _ = curve_loss(final + component * (1.0e-3 / max(rms, 1e-30)),
                                  config, problem, observed)
        full_loss, _ = curve_loss(final + component, config, problem, observed)
        modal["modes"].append({"mode": mode, "actual_rms_m": rms,
                               "loss_at_1mm_rms_correction": unit_loss,
                               "loss_with_full_correction": full_loss})

    record["curve_space_transect"] = transect
    record["single_mode_sensitivity_final_star"] = modal
    record["caveats"] = [
        "Timings are single-machine engineering measurements; cProfile totals are "
        "inflated by profiling overhead and are meaningful only as shares.",
        "Radial spectra use a polar decomposition about the polygon centroid, "
        "resampled to 512 uniform angles; they are not the arc-length modal basis "
        "the proposals specify, and the single_valued_radius flag records the "
        "assumption each state satisfies.",
        "The transect is one straight path in node coordinates between saved node "
        "sets. It ignores MLP reachability, the conversion audit and the boundary "
        "motion cap by construction; the absence of a barrier along it is not a "
        "convexity claim.",
        "Single-mode sensitivities are finite 1 mm RMS differences, not "
        "derivatives, and use Cartesian node-index modes in which mode 0 is a "
        "rigid translation.",
    ]

    destination.write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
