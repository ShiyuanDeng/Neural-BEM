"""Bounded qualification, not the full 117-frequency paper reproduction."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np

from .forward import Acquisition, Work, solve
from .geometry import FourierCurve
from .inverse import FitConfig, Observation, run_continuation
from .schedule import Stage
from .metrics import boundary_distance


def fixture(name):
    if name == "circle":
        return FourierCurve.circle(.9, .03 - .02j)
    if name == "ellipse":
        return FourierCurve(np.array([.125 * np.exp(.3j), .03 - .02j, .925 * np.exp(.3j)]))
    t = 2 * np.pi * np.arange(512) / 512
    radius = .9 * (1 + .2 * np.cos(3*t) + .02 * np.cos(4*t) + .1 * np.cos(6*t) + .1 * np.cos(8*t))
    return FourierCurve.from_samples(radius * np.exp(1j*t), 9)


def relative(first, second):
    return float(np.linalg.norm(first - second) / max(np.linalg.norm(second), np.finfo(float).tiny))


def provenance():
    root = Path(__file__).resolve().parents[2]
    files = [*Path(__file__).parent.glob("*.py"), *(root / "solvers/gpr_bem_kress").glob("*.py"),
             *(root / "solvers/ordered_boundary").glob("*.py"), *(root / "solvers/periodic_kress").glob("*.py")]
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        git_status=subprocess.check_output(["git", "status", "--short"], cwd=root, text=True),
        source_sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()},
        python=sys.version, platform=platform.platform(), command=sys.argv,
        timestamp=datetime.now(timezone.utc).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", choices=("circle", "ellipse", "glider"), default="ellipse")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contrast", type=float, default=1.44)
    parser.add_argument("--max-iterations", type=int, default=20)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        run(args)
    except Exception as exc:
        (args.output / "failure.json").write_text(json.dumps(dict(type=type(exc).__name__, message=str(exc)), indent=2) + "\n")
        raise


def run(args):
    manifest = provenance()
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    started = perf_counter()
    truth, initial = fixture(args.scene), FourierCurve.circle()
    # Fixed pilot settings; no target-derived choice of modes, resolution, or stages.
    waves = (1.0, 1.25, 1.5, 1.75, 2.0)
    stages = [Stage(k, max(1, int(3 * k * max(1, np.sqrt(args.contrast)))), 48, 128,
                    int(np.ceil(2 * k))) for k in waves]
    config = FitConfig(max_iterations=args.max_iterations)
    observation_work = Work(max_forwards=30)
    work = Work(max_forwards=550, max_seconds=600)
    observations, qualifications = [], []
    for k in waves:
        acquisition = Acquisition.ring(int(10 * k), int(10 * k))
        coarse = solve(truth, k, args.contrast, acquisition, 256, work=observation_work).prediction
        fine = solve(truth, k, args.contrast, acquisition, 512, work=observation_work).prediction
        error = relative(coarse, fine)
        qualifications.append(dict(wavenumber=k, nodes=[256, 512], relative_difference=error))
        observations.append(Observation(k, acquisition, fine))
    arrays = dict(truth=truth.coefficients, initial=initial.coefficients)
    for i, observation in enumerate(observations):
        arrays[f"data_{i}"] = observation.scattered
        arrays[f"directions_{i}"] = observation.acquisition.directions
        arrays[f"receivers_{i}"] = observation.acquisition.receivers
    np.savez_compressed(args.output / "inputs.npz", **arrays)
    if max(q["relative_difference"] for q in qualifications) > 1e-7:
        (args.output / "summary.json").write_text(json.dumps(dict(status="unqualified_observations", qualification=qualifications), indent=2))
        raise RuntimeError("Observation refinement gate failed; inverse not run.")
    result = run_continuation(initial, observations, stages, args.contrast, config=config, work=work)
    # Preserve the run before endpoint scoring or plotting, including budget stops.
    summary = dict(scene=args.scene, contrast=args.contrast, config=asdict(config),
        planned_stages=[asdict(s) for s in stages], observation_qualification=qualifications,
        stages=[dict(stage=asdict(r.stage), stop_reason=r.stop_reason,
                     relative_residual=r.relative_residual, history=r.history, trials=r.trials) for r in result],
        inverse_work=work.summary(), observation_work=observation_work.summary())
    np.savez_compressed(args.output / "states.npz", **{f"stage_{i}": r.shape.coefficients for i, r in enumerate(result)})
    np.savez_compressed(args.output / "accepted_states.npz", **{
        f"stage_{i}_iterate_{j}": state.coefficients
        for i, r in enumerate(result) for j, state in enumerate(r.states)})
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    final = result[-1].shape
    evaluation_work = Work(max_forwards=20)
    resolutions = []
    for observation in observations:
        low = solve(final, observation.wavenumber, args.contrast, observation.acquisition, 128, work=evaluation_work).prediction
        high = solve(final, observation.wavenumber, args.contrast, observation.acquisition, 256, work=evaluation_work).prediction
        resolutions.append(dict(wavenumber=observation.wavenumber,
            relative_difference=relative(low, high), common_frequency_error=relative(high, observation.scattered)))
    acquisition = Acquisition.ring(23, 29)
    angle = .071
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    holdout = Acquisition(acquisition.directions @ rotation.T, acquisition.receivers @ rotation.T)
    prediction = solve(final, 1.625, args.contrast, holdout, 256, work=evaluation_work).prediction
    target = solve(truth, 1.625, args.contrast, holdout, 512, work=evaluation_work).prediction
    # A sampled Hausdorff metric with its discretization bound explicitly saved.
    # This is not the paper's symmetric-area score.
    boundary_error, sampling_bound = boundary_distance(truth, final)
    radius = np.sqrt(truth.nodes(8192).signed_area / np.pi)
    summary.update(endpoint_resolution=resolutions, holdout_relative_error=relative(prediction, target),
        sampled_boundary_hausdorff=float(boundary_error),
        boundary_sampling_bound=float(sampling_bound),
        relative_boundary_error=float(boundary_error / radius),
        relative_area_difference=float(abs(final.nodes(8192).signed_area / truth.nodes(8192).signed_area - 1)),
        evaluation_work=evaluation_work.summary(), elapsed_seconds=perf_counter() - started)
    summary["qualification"] = dict(
        all_stages_completed=len(result) == len(stages),
        endpoint_resolution=max(r["relative_difference"] for r in resolutions) <= 1e-6,
        holdout=summary["holdout_relative_error"] <= 1e-3,
        shape=summary["relative_boundary_error"] <= 1e-2)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(10, 4))
    for shape, label, style in ((truth, "Truth", "k-"), (initial, "Initial", "--"), (final, "Recovered", "C1-")):
        z = shape.values(2048)
        axes[0].plot(np.r_[z.real, z.real[0]], np.r_[z.imag, z.imag[0]], style, label=label)
    axes[0].set_aspect("equal")
    axes[0].legend()
    for item in result:
        axes[1].semilogy([r["iteration"] for r in item.history], [r["relative_residual"] for r in item.history],
                         marker=".", label=f"k={item.stage.wavenumber:g}")
    axes[1].set(xlabel="Iteration within stage", ylabel="Relative data residual")
    axes[1].legend()
    figure.tight_layout()
    figure.savefig(args.output / "recovery.png", dpi=160)
    plt.close(figure)
    print(json.dumps({k: summary[k] for k in ("scene", "qualification", "relative_boundary_error", "holdout_relative_error", "inverse_work", "elapsed_seconds")}, indent=2))


if __name__ == "__main__":
    main()
