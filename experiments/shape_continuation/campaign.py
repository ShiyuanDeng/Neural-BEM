"""Head-to-head continuation arms at a matched forward-solve budget.

Four arms share one optimizer, one solver, one data set and one budget, and
differ only in where their continuation decisions come from:

* `fixed`     - the established baseline: a uniform frequency ladder and a
                prescribed update band;
* `band`      - the same ladder, with the band measured from the atlas;
* `frequency` - the prescribed band, with the frequency chosen by probing;
* `full`      - both measured.

Atlas probes are charged to the same `Work` object as the inversion, so an
arm that measures more has fewer forward solves left for optimizing. Truth
generates observations and scores endpoints; it never enters a policy or an
optimizer, and scoring runs on its own separate budget.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .atlas import Whitening
from .continuation import run_adaptive
from .forward import Acquisition, BudgetExceeded, Work, solve
from .geometry import FourierCurve, grid_size
from .inverse import FitConfig, Observation
from .metrics import area_error, boundary_distance
from .policy import AtlasPolicy
from .run import fixture, provenance, relative
from .survey import even_at_least, node_count

ARMS = ("fixed", "band", "frequency", "full")


def start_shape(name):
    """Initial curves; all are circles, none is informed by the truth."""
    if name == "unit":
        return FourierCurve.circle(1.0)
    if name == "small":
        return FourierCurve.circle(0.7)
    if name == "large":
        return FourierCurve.circle(1.3)
    if name == "offset":
        return FourierCurve.circle(0.9, 0.15 - 0.1j)
    raise ValueError(f"Unknown start {name}.")


def generate(truth, wavenumbers, contrast, points_per_wavelength, minimum_nodes,
             tolerance, work):
    perimeter = float(truth.nodes(grid_size(truth.band)).perimeter)
    observations, checks = [], []
    for wavenumber in wavenumbers:
        acquisition = Acquisition.ring(max(4, int(10 * wavenumber)), max(4, int(10 * wavenumber)))
        nodes = node_count(wavenumber, contrast, perimeter, points_per_wavelength,
                           truth.band, minimum=minimum_nodes)
        half = even_at_least(nodes / 2)
        coarse = solve(truth, wavenumber, contrast, acquisition, half, work=work).prediction
        fine = solve(truth, wavenumber, contrast, acquisition, nodes, work=work).prediction
        difference = relative(coarse, fine)
        checks.append(dict(wavenumber=float(wavenumber), nodes=[half, nodes],
                           relative_difference=difference))
        if difference > tolerance:
            raise RuntimeError(f"Observation gate failed at k={wavenumber:g}: {difference:.3g}.")
        observations.append(Observation(float(wavenumber), acquisition, fine))
    return tuple(observations), checks


def score(truth, shape, observations, contrast, nodes, work):
    """Evaluation only: shape error, area error and a held-out prediction."""
    radius = float(np.sqrt(truth.nodes(8192).signed_area / np.pi))
    error, bound = boundary_distance(truth, shape)
    result = dict(sampled_boundary_hausdorff=error, boundary_sampling_bound=bound,
                  relative_boundary_error=error / radius,
                  relative_boundary_error_upper_bound=(error + bound) / radius)
    try:
        result["area"] = area_error(truth, shape)
    except Exception as exc:  # a self-intersecting endpoint is a result, not a crash
        result["area"] = dict(failure=str(exc))
    angle = 0.071
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    base = Acquisition.ring(23, 29)
    holdout = Acquisition(base.directions @ rotation.T, base.receivers @ rotation.T)
    wavenumber = float(np.median([o.wavenumber for o in observations])) + 0.111
    try:
        prediction = solve(shape, wavenumber, contrast, holdout, nodes, work=work).prediction
        target = solve(truth, wavenumber, contrast, holdout, 2 * nodes, work=work).prediction
        coarse = solve(shape, wavenumber, contrast, holdout, nodes // 2 * 2, work=work).prediction
        result.update(holdout_wavenumber=wavenumber,
                      holdout_relative_error=relative(prediction, target),
                      holdout_self_convergence=relative(coarse, prediction))
    except Exception as exc:
        result["holdout"] = dict(failure=str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scene", choices=("circle", "ellipse", "glider"), default="glider")
    parser.add_argument("--contrast", type=float, default=0.33)
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    parser.add_argument("--starts", nargs="+", default=["unit"])
    parser.add_argument("--k-start", type=float, default=1.0)
    parser.add_argument("--k-stop", type=float, default=8.0)
    parser.add_argument("--k-step", type=float, default=0.25)
    parser.add_argument("--band-rule", default="paper", choices=("paper", "driver", "scaled"))
    parser.add_argument("--safety", type=float, default=1.0,
                        help="Fraction of the measured horizon used as the band admission radius.")
    parser.add_argument("--ratio-floor", type=float, default=0.25)
    parser.add_argument("--horizon-anchor", type=float, default=0.12,
                        help="Centre of the horizon bracket, as anchor/k.")
    parser.add_argument("--maximum-jump", type=float, default=2.0)
    parser.add_argument("--maximum-probes", type=int, default=3)
    parser.add_argument("--probe-band-cap", type=int, default=80)
    parser.add_argument("--max-forwards", type=int, default=1200)
    parser.add_argument("--max-seconds", type=float, default=2400.0)
    parser.add_argument("--max-decisions", type=int, default=120)
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--backtracks", type=int, default=0)
    parser.add_argument("--curvature-tail-tolerance", type=float, default=1e-2)
    parser.add_argument("--points-per-wavelength", type=float, default=30.0)
    parser.add_argument("--data-points-per-wavelength", type=float, default=60.0)
    parser.add_argument("--minimum-data-nodes", type=int, default=256)
    parser.add_argument("--noise-level", type=float, default=1e-3)
    parser.add_argument("--observation-tolerance", type=float, default=1e-7)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        run(args)
    except Exception as exc:
        (args.output / "failure.json").write_text(
            json.dumps(dict(type=type(exc).__name__, message=str(exc)), indent=2) + "\n")
        raise


def run(args):
    started = perf_counter()
    (args.output / "manifest.json").write_text(json.dumps(
        dict(provenance(), arguments={k: str(v) for k, v in vars(args).items()}), indent=2) + "\n")
    truth = fixture(args.scene)
    steps = round((args.k_stop - args.k_start) / args.k_step)
    waves = args.k_start + args.k_step * np.arange(steps + 1)
    data_work = Work(max_forwards=4 * len(waves) + 8, max_seconds=args.max_seconds)
    observations, checks = generate(truth, waves, args.contrast,
                                    args.data_points_per_wavelength,
                                    args.minimum_data_nodes, args.observation_tolerance,
                                    data_work)
    config = FitConfig(max_iterations=args.max_iterations, backtracks=args.backtracks,
                       curvature_tail_tolerance=args.curvature_tail_tolerance)
    results = []
    for start in args.starts:
        for arm in args.arms:
            label = f"{arm}-{start}"
            directory = args.output / label
            directory.mkdir()
            work = Work(max_forwards=args.max_forwards, max_seconds=args.max_seconds)
            policy = AtlasPolicy(
                observations=observations, contrast=args.contrast, work=work, mode=arm,
                safety=args.safety, ratio_floor=args.ratio_floor,
                horizon_anchor=args.horizon_anchor, maximum_jump=args.maximum_jump,
                maximum_probes=args.maximum_probes, probe_band_cap=args.probe_band_cap,
                points_per_wavelength=args.points_per_wavelength,
                band_rule=args.band_rule, config=config, k_stop=args.k_stop,
                whitening=Whitening("relative", args.noise_level))
            trace = []

            def checkpoint(record, directory=directory, trace=trace, work=work):
                np.savez_compressed(directory / f"decision_{record.index:03d}.npz",
                                    shape=record.result.shape.coefficients)
                entry = dict(index=record.index, stage=asdict(record.decision.stage),
                             reason=record.decision.reason, committed=record.committed,
                             stop_reason=record.result.stop_reason,
                             relative_residual=record.result.relative_residual,
                             history=record.result.history,
                             work_after=record.work_after)
                trace.append(entry)
                (directory / f"decision_{record.index:03d}.json").write_text(
                    json.dumps(entry, indent=2) + "\n")

            arm_started = perf_counter()
            failure = None
            try:
                outcome = run_adaptive(start_shape(start), observations, args.contrast,
                                       policy, work=work, max_decisions=args.max_decisions,
                                       on_decision=checkpoint)
                final, stop_reason = outcome.shape, outcome.stop_reason
            except BudgetExceeded:
                final = FourierCurve(np.load(sorted(directory.glob("decision_*.npz"))[-1])["shape"]) \
                    if list(directory.glob("decision_*.npz")) else start_shape(start)
                stop_reason = "budget_exhausted"
            except Exception as exc:
                failure = f"{type(exc).__name__}: {exc}"
                shots = sorted(directory.glob("decision_*.npz"))
                final = FourierCurve(np.load(shots[-1])["shape"]) if shots else start_shape(start)
                stop_reason = "failed"
            elapsed = perf_counter() - arm_started
            evaluation = Work(max_forwards=40, max_seconds=args.max_seconds)
            endpoint_nodes = even_at_least(max(256, 2 * (final.band + 1) + 2,
                args.points_per_wavelength * final.nodes(grid_size(final.band)).perimeter
                * args.k_stop * max(1.0, np.sqrt(args.contrast)) / (2 * np.pi)))
            scores = score(truth, final, observations, args.contrast, endpoint_nodes, evaluation)
            record = dict(arm=arm, start=start, label=label, failure=failure,
                          stop_reason=stop_reason, decisions=len(trace),
                          highest_wavenumber=max([t["stage"]["wavenumber"] for t in trace],
                                                 default=None),
                          final_band=final.band, elapsed_seconds=elapsed,
                          work=work.summary(), scores=scores,
                          probes=policy.probes, policy_decisions=policy.decisions)
            np.savez_compressed(directory / "endpoint.npz", shape=final.coefficients,
                                truth=truth.coefficients, initial=start_shape(start).coefficients)
            (directory / "summary.json").write_text(json.dumps(
                dict(record, trace=trace, observation_checks=checks), indent=2) + "\n")
            results.append(record)
            print(json.dumps({k: record[k] for k in
                              ("label", "stop_reason", "highest_wavenumber", "elapsed_seconds")}
                             | {"boundary": scores["relative_boundary_error"],
                                "forwards": work.attempted}), flush=True)
    summary = dict(scene=args.scene, contrast=args.contrast, arms=args.arms,
                   starts=args.starts, wavenumbers=waves.tolist(),
                   budget=dict(max_forwards=args.max_forwards, max_seconds=args.max_seconds),
                   band_rule=args.band_rule, safety=args.safety,
                   ratio_floor=args.ratio_floor, horizon_anchor=args.horizon_anchor,
                   results=results,
                   observation_checks=checks, data_work=data_work.summary(),
                   elapsed_seconds=perf_counter() - started)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(dict(elapsed_seconds=summary["elapsed_seconds"],
                          arms=len(results)), indent=2))


if __name__ == "__main__":
    main()
