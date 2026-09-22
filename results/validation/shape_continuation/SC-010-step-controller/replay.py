"""Reproduce the controller qualification from archived observations.

Run from repository root with PYTHONPATH=solvers:. and one BLAS thread.
Pass a fresh --output directory; existing qualification bundles are never edited.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.shape_continuation.continuation import Decision, ResolutionGate, run_adaptive
from experiments.shape_continuation.forward import Acquisition, Work, solve
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.inverse import FitConfig, Observation, run_continuation
from experiments.shape_continuation.metrics import boundary_distance
from experiments.shape_continuation.run import provenance, relative
from experiments.shape_continuation.schedule import Stage


ROOT = Path(__file__).resolve().parents[4]
BUNDLES = ROOT / "results/validation/shape_continuation"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def load(name, count=5):
    bundle = BUNDLES / name
    saved = json.loads((bundle / "summary.json").read_text())
    stages = [Stage(**row["stage"]) for row in saved["stages"][:count]]
    with np.load(bundle / "inputs.npz") as arrays:
        initial = FourierCurve(arrays["initial"])
        observations = [Observation(stage.wavenumber,
            Acquisition(arrays[f"directions_{i}"], arrays[f"receivers_{i}"]), arrays[f"data_{i}"])
            for i, stage in enumerate(stages)]
    return bundle, saved, stages, initial, observations


def report(result):
    return dict(stage=asdict(result.stage), stop_reason=result.stop_reason,
                relative_residual=result.relative_residual,
                history=result.history, trials=result.trials)


def fixed_replay(name, output):
    bundle, saved, stages, initial, observations = load(name)
    work = Work(max_forwards=550, max_seconds=180)
    started = perf_counter()
    results = run_continuation(initial, observations, stages, saved["contrast"],
                              config=FitConfig(**saved["config"]), work=work)
    seconds = perf_counter() - started
    rows = [report(result) for result in results]
    states = {f"stage_{i}_iterate_{j}": state.coefficients
              for i, result in enumerate(results) for j, state in enumerate(result.states)}
    np.savez_compressed(output / f"{name}-states.npz", **states)
    with np.load(bundle / "accepted_states.npz") as reference:
        expected_keys = [key for key in reference.files if int(key.split("_")[1]) < len(stages)]
        identical = (set(states) == set(expected_keys)
                     and all(np.array_equal(value, reference[key]) for key, value in states.items()))
    expected = saved["stages"][:len(stages)]
    expected_forwards = len(stages) + sum("relative_residual" in trial
        for row in expected for trial in row["trials"])
    row = dict(baseline=name, stages=len(results), saved_states=len(states), seconds=seconds,
        work=work.summary(), state_arrays_bitwise_identical=identical,
        histories_trials_and_stops_identical=rows == expected,
        forward_count_identical=work.attempted == expected_forwards,
        stages_completed=len(results) == len(stages), stage_reports=rows,
        baseline_sha256={file: hashlib.sha256((bundle / file).read_bytes()).hexdigest()
                         for file in ("summary.json", "inputs.npz", "accepted_states.npz")})
    write(output / f"{name}-replay.json", row)
    print(json.dumps({key: value for key, value in row.items()
                      if key not in ("stage_reports", "baseline_sha256")}), flush=True)
    return row


def adaptive_demo(output):
    bundle, saved, stages, initial, observations = load("SC-009-conservative-scoring")
    config = replace(FitConfig(**saved["config"]), max_iterations=1)
    # Illustrative feedback rule only: try M=1 at the first frequency, enlarge M
    # on a local stop until the baseline band, then advance. Continue one update
    # at a time. A failed N/2N check doubles N and retries the rolled-back curve.
    def strategy(context):
        if not context.history:
            return Decision(replace(stages[0], update_modes=1), config, "start at M=1")
        last = context.history[-1]
        stage = last.decision.stage
        if not last.committed:
            return Decision(replace(stage, nodes=2 * stage.nodes), config, "refine N after failed qualification")
        index = context.available_wavenumbers.index(stage.wavenumber)
        if last.result.stop_reason == "iteration_limit":
            return Decision(stage, config, "continue one update at this k and M")
        if last.result.stop_reason != "data_fit" and stage.update_modes < stages[index].update_modes:
            return Decision(replace(stage, update_modes=stage.update_modes + 1), config,
                            "increase M after local stop")
        if index + 1 < len(stages):
            return Decision(stages[index + 1], config, "advance k after local stop")
        return None

    checkpoints = []
    def checkpoint(record):
        checkpoints.append(dict(index=record.index, decision=asdict(record.decision),
            result=report(record.result), committed=record.committed,
            qualification=asdict(record.qualification),
            work_before=record.work_before, work_after=record.work_after))
        write(output / "adaptive-decisions.json", checkpoints)
        np.savez_compressed(output / f"adaptive-decision-{record.index:03d}.npz",
            **{f"iterate_{i}": shape.coefficients for i, shape in enumerate(record.result.states)})

    work = Work(max_forwards=180, max_seconds=120)
    started = perf_counter()
    result = run_adaptive(initial, observations, saved["contrast"], strategy,
        work=work, max_decisions=60, qualify=ResolutionGate(), on_decision=checkpoint)
    seconds = perf_counter() - started
    # Evaluation starts here, after the controller has finished.
    with np.load(bundle / "inputs.npz") as arrays:
        truth = FourierCurve(arrays["truth"])
    acquisition = Acquisition.ring(23, 29)
    angle = .071
    rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    holdout = Acquisition(acquisition.directions @ rotation.T, acquisition.receivers @ rotation.T)
    evaluation_work = Work(max_forwards=2)
    k = saved["holdout_wavenumber"]
    prediction = solve(result.shape, k, saved["contrast"], holdout, 256, work=evaluation_work).prediction
    target = solve(truth, k, saved["contrast"], holdout, 512, work=evaluation_work).prediction
    error, bound = boundary_distance(truth, result.shape)
    radius = np.sqrt(truth.nodes(8192).signed_area / np.pi)
    np.savez_compressed(output / "adaptive-final.npz", shape=result.shape.coefficients,
                        heldout_prediction=prediction, heldout_target=target)
    row = dict(stop_reason=result.stop_reason, decisions=len(result.history), seconds=seconds,
        work=work.summary(), evaluation_work=evaluation_work.summary(),
        final_wavenumber=result.history[-1].result.stage.wavenumber,
        final_residual=result.history[-1].result.relative_residual,
        holdout_relative_error=relative(prediction, target),
        relative_boundary_error_upper_bound=float((error + bound) / radius),
        all_checks_pass=all(record.qualification.passed for record in result.history),
        harmonic_bands=sorted(set(record.result.stage.update_modes for record in result.history)),
        frequency_sequence=[record.result.stage.wavenumber for record in result.history])
    write(output / "adaptive-summary.json", row)
    print(json.dumps(row), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = provenance()
    manifest["qualification_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write(args.output / "manifest.json", manifest)
    replays = [fixed_replay(name, args.output) for name in
               ("SC-009-conservative-scoring", "SC-005-glider-filtered-step")]
    adaptive = adaptive_demo(args.output)
    flags = ("state_arrays_bitwise_identical", "histories_trials_and_stops_identical",
             "forward_count_identical", "stages_completed")
    assert all(row[flag] for row in replays for flag in flags), "Fixed-ladder regression differs; results retained."
    assert adaptive["stop_reason"] == "policy_stop" and adaptive["final_wavenumber"] == 2.
    assert adaptive["all_checks_pass"] and adaptive["final_residual"] <= 1e-5
    assert adaptive["holdout_relative_error"] <= 1e-3
    assert adaptive["relative_boundary_error_upper_bound"] <= 1e-2


if __name__ == "__main__":
    main()
