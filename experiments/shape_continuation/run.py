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
from .geometry import FourierCurve, grid_size
from .inverse import FitConfig, Observation, run_continuation
from .schedule import Stage, paper_stage
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
    parser.add_argument("--backtracks", type=int, default=8,
                        help="Step halvings before stronger filtering; 0 follows the paper's filter sequence.")
    parser.add_argument("--k-start", type=float, default=1.)
    parser.add_argument("--k-stop", type=float, default=2.)
    parser.add_argument("--k-step", type=float, default=.25)
    parser.add_argument("--curve-modes", type=int, default=48)
    parser.add_argument("--nodes", type=int, default=128)
    parser.add_argument("--data-nodes", type=int, default=512)
    parser.add_argument("--resolution", choices=("fixed", "paper"), default="fixed")
    parser.add_argument("--points-per-wavelength", type=float, default=20.)
    parser.add_argument("--verify-stages", action="store_true")
    parser.add_argument("--max-forwards", type=int, default=550)
    parser.add_argument("--max-seconds", type=float, default=600.)
    args = parser.parse_args()
    if not 0 < args.k_start <= args.k_stop or not np.isfinite(args.k_step) or args.k_step <= 0:
        parser.error("Require 0 < k-start <= k-stop and a positive finite k-step.")
    intervals = (args.k_stop - args.k_start) / args.k_step
    if not np.isfinite(intervals) or not np.isclose(intervals, round(intervals)):
        parser.error("The frequency range must be a whole number of k-step intervals.")
    if args.data_nodes < 32 or args.data_nodes % 4:
        parser.error("data-nodes must be a multiple of four and at least 32.")
    if args.max_forwards < 1 or not np.isfinite(args.max_seconds) or args.max_seconds <= 0:
        parser.error("Work budgets must be positive.")
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
    # Resolutions depend only on declared controls and the current iterate.
    waves = args.k_start + args.k_step * np.arange(round((args.k_stop-args.k_start)/args.k_step) + 1)
    stages = [Stage(k, max(1, int(3 * k * max(1, np.sqrt(args.contrast)))), args.curve_modes, args.nodes,
                    int(np.ceil(2 * k))) for k in waves] if args.resolution == "fixed" else None
    def stage_policy(shape, k, previous):
        return paper_stage(k, args.contrast, shape.nodes(grid_size(shape.band)).perimeter,
            previous_curve_modes=max(args.curve_modes, previous.curve_modes if previous else 1),
            points_per_wavelength=args.points_per_wavelength, minimum_nodes=args.nodes)
    config = FitConfig(max_iterations=args.max_iterations, backtracks=args.backtracks)
    observation_work = Work(max_forwards=2 * len(waves), max_seconds=args.max_seconds)
    observations, qualifications = [], []
    for k in waves:
        acquisition = Acquisition.ring(int(10 * k), int(10 * k))
        coarse = solve(truth, k, args.contrast, acquisition, args.data_nodes // 2, work=observation_work).prediction
        fine = solve(truth, k, args.contrast, acquisition, args.data_nodes, work=observation_work).prediction
        error = relative(coarse, fine)
        qualifications.append(dict(wavenumber=k, nodes=[args.data_nodes // 2, args.data_nodes], relative_difference=error))
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
    phase_seconds = dict(observation_generation=perf_counter()-started)
    work = Work(max_forwards=args.max_forwards, max_seconds=args.max_seconds)
    evaluation_work = Work(max_forwards=4 * len(waves) + 2, max_seconds=3 * args.max_seconds)
    stage_checks = []
    def checkpoint(index, result):
        np.savez_compressed(args.output / f"checkpoint_{index:03d}.npz", shape=result.shape.coefficients)
        record = dict(stage=asdict(result.stage), stop_reason=result.stop_reason,
                      relative_residual=result.relative_residual, work=work.summary(),
                      history=result.history, trials=result.trials)
        path = args.output / f"checkpoint_{index:03d}.json"
        path.write_text(json.dumps(record, indent=2) + "\n")
        if args.verify_stages and result.stop_reason != "budget_exhausted":
            observation = observations[index]
            low = solve(result.shape, observation.wavenumber, args.contrast, observation.acquisition,
                        result.stage.nodes, work=evaluation_work).prediction
            high = solve(result.shape, observation.wavenumber, args.contrast, observation.acquisition,
                         2 * result.stage.nodes, work=evaluation_work).prediction
            check = dict(wavenumber=observation.wavenumber, nodes=result.stage.nodes,
                         relative_difference=relative(low, high))
            stage_checks.append(check)
            record["resolution_check"] = check
            path.write_text(json.dumps(record, indent=2) + "\n")
            if check["relative_difference"] > 1e-6:
                raise RuntimeError(f"Stage k={observation.wavenumber:g} failed forward refinement; checkpoint retained.")
        print(json.dumps({"k": result.stage.wavenumber, "nodes": result.stage.nodes,
              "curve_modes": result.stage.curve_modes, "residual": result.relative_residual,
              "stop": result.stop_reason, "forward_evaluations": work.attempted}), flush=True)
    inverse_started = perf_counter()
    result = run_continuation(initial, observations, stages if stages is not None else stage_policy,
        args.contrast, config=config, work=work, on_stage=checkpoint)
    phase_seconds["inverse_including_stage_checks"] = perf_counter() - inverse_started
    # Preserve the run before endpoint scoring or plotting, including budget stops.
    summary = dict(scene=args.scene, contrast=args.contrast, config=asdict(config),
        planned_stages=[asdict(s) for s in stages] if stages is not None else None,
        requested_wavenumbers=waves.tolist(), resolution_policy=args.resolution,
        stage_resolution_checks=stage_checks, observation_qualification=qualifications,
        stages=[dict(stage=asdict(r.stage), stop_reason=r.stop_reason,
                     relative_residual=r.relative_residual, history=r.history, trials=r.trials) for r in result],
        inverse_work=work.summary(), observation_work=observation_work.summary())
    np.savez_compressed(args.output / "states.npz", **{f"stage_{i}": r.shape.coefficients for i, r in enumerate(result)})
    np.savez_compressed(args.output / "accepted_states.npz", **{
        f"stage_{i}_iterate_{j}": state.coefficients
        for i, r in enumerate(result) for j, state in enumerate(r.states)})
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    final = result[-1].shape
    evaluation_started = perf_counter()
    endpoint_nodes = result[-1].stage.nodes
    resolutions = []
    for observation in observations:
        low = solve(final, observation.wavenumber, args.contrast, observation.acquisition, endpoint_nodes, work=evaluation_work).prediction
        high = solve(final, observation.wavenumber, args.contrast, observation.acquisition, 2*endpoint_nodes, work=evaluation_work).prediction
        resolutions.append(dict(wavenumber=observation.wavenumber,
            relative_difference=relative(low, high), common_frequency_error=relative(high, observation.scattered)))
    acquisition = Acquisition.ring(23, 29)
    angle = .071
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    holdout = Acquisition(acquisition.directions @ rotation.T, acquisition.receivers @ rotation.T)
    holdout_k = args.k_start + (np.floor(.625 * (len(waves)-1)) + .5) * args.k_step
    prediction = solve(final, holdout_k, args.contrast, holdout, 2*endpoint_nodes, work=evaluation_work).prediction
    target = solve(truth, holdout_k, args.contrast, holdout, args.data_nodes, work=evaluation_work).prediction
    # A sampled Hausdorff metric with its discretization bound explicitly saved.
    # This is not the paper's symmetric-area score.
    boundary_error, sampling_bound = boundary_distance(truth, final)
    radius = np.sqrt(truth.nodes(8192).signed_area / np.pi)
    summary.update(endpoint_resolution=resolutions, holdout_relative_error=relative(prediction, target),
        sampled_boundary_hausdorff=float(boundary_error),
        boundary_sampling_bound=float(sampling_bound),
        relative_boundary_error=float(boundary_error / radius),
        relative_area_difference=float(abs(final.nodes(8192).signed_area / truth.nodes(8192).signed_area - 1)),
        evaluation_work=evaluation_work.summary(), holdout_wavenumber=holdout_k,
        elapsed_seconds=perf_counter() - started)
    phase_seconds["endpoint_scoring"] = perf_counter() - evaluation_started
    summary["phase_seconds"] = phase_seconds
    summary["qualification"] = dict(
        all_stages_completed=len(result) == len(waves) and all(r.stop_reason != "budget_exhausted" for r in result),
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
