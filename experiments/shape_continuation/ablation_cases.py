"""SC-024(a): shared-backend ablations of SC-022's fixed-schedule trajectories.

Only the backend variant changes: physical step control and/or a relaxed
arclength-refit gate. Band rules, schedule, caps, start, observations and
truths are SC-022's (inputs are copied and hash-checked against SC-022's
manifest). Truth enters only the endpoint scoring hook, whose return value
the policy loop ignores.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import time

import numpy as np

from . import atlas_cases as ac
from . import spd_cases as sc
from .atlas_survey import symmetric_rms_distance
from .lm_backend import FixedSchedule, Ledger, run_policy, stage_record
from .metrics import area_error, boundary_distance
from .updates import BorgesUpdate

ROOT = Path(__file__).resolve().parents[2]
SC022 = ROOT / "results/validation/shape_continuation/SC-022-atlas-survey"
PHYSICAL_BOUND_M = 0.006
# V0 (coefficient clip, 1e-7 gate) is SC-022 itself and is not rerun.
VARIANTS = dict(V1=dict(step_control="physical", projection_tolerance=1e-7),
                V2=dict(step_control="coefficient", projection_tolerance=1e-5),
                V3=dict(step_control="physical", projection_tolerance=1e-5),
                # Amendment 2026-09-24: every C stage under V1-V3 ended at SPD's 22-iteration cap
                # while still improving. One diagnostic run lifts only that cap (x4).
                V2x4=dict(step_control="coefficient", projection_tolerance=1e-5, iterations_factor=4))
ARMS = ("borges", "fixed32")


def tightest_radius_m(curve):
    return float(sc.LENGTH / np.max(np.abs(curve.nodes(8192).curvatures)))


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    reference = sc.read(SC022 / "manifest.json")
    inputs = {}
    for case in ac.CASES:
        for name in ("observations.json", "truth.json", "oracle_check.json"):
            relative = f"inputs/{case}/{name}"
            (output / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SC022 / relative, output / relative)
            inputs[relative] = ac.digest(output / relative)
            if relative in reference["inputs"] and reference["inputs"][relative] != inputs[relative]:
                raise RuntimeError(f"SC-022 input changed: {relative}")
    sc.write(output / "manifest.json", dict(
        experiment="SC-024", plan="docs/iterations/shape_frequency_continuation/iteration_08/03_plan.md",
        inputs=inputs, inputs_from="SC-022-atlas-survey (copied, hashes equal)",
        variants=VARIANTS, physical_step_bound_m=PHYSICAL_BOUND_M, arms=ARMS, cases=ac.CASES,
        source_sha256=sc.source_hashes(), prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def run(output, case, arm, variant):
    ac.verify_sources(output)
    catalog, truth = ac.load_case(output, case)
    schedule, config = ac.policy(catalog, arm)
    settings = VARIANTS[variant]
    if "iterations_factor" in settings:
        schedule = FixedSchedule([replace(s, iterations=s.iterations * settings["iterations_factor"])
                                  for s in schedule.stages], schedule.name + f", iterations x{settings['iterations_factor']}")
    config = replace(config, step_control=settings["step_control"], physical_step_bound_m=PHYSICAL_BOUND_M)
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=settings["projection_tolerance"])
    ledger = Ledger(cap=8012, seconds=7200.0)
    folder = output / "runs" / variant / arm / case
    folder.mkdir(parents=True, exist_ok=False)
    sc.write(folder / "configuration.json", dict(arm=arm, variant=variant, update=update.settings(),
             backend=asdict(config), policy=schedule.name, stages=[stage_record(s) for s in schedule.stages]))
    truth_points = truth.values(16384)
    scores, radii = [], []

    def geometry(curve):
        error, bound = boundary_distance(truth, curve)
        return dict(hausdorff_m=error * sc.LENGTH, hausdorff_upper_m=(error + bound) * sc.LENGTH,
                    symmetric_rms_m=symmetric_rms_distance(curve, truth_points, sc.LENGTH),
                    area=area_error(truth, curve), tightest_radius_m=tightest_radius_m(curve))

    def accepted(stage, iteration, evaluation):
        radii.append(dict(stage=stage.label, iteration=iteration, loss=evaluation.loss,
                          tightest_radius_m=tightest_radius_m(evaluation.curve)))

    def endpoint(stage, result):
        scores.append(dict(stage=stage.label, geometry=geometry(result.curve), outcome=result.outcome,
                           stop=result.stop_reason, accepted=result.accepted_steps, loss=result.final_loss))
        sc.write(folder / "stage_scores.json", scores)

    started = time.perf_counter()
    result = run_policy(ac.start_curve(), schedule, ac.contrast(), update, config, ledger,
                        on_stage=endpoint, on_accept=accepted)
    refusals = {}
    for record in result.stages:
        sc.write(folder / f"{record.stage_label}_history.json", dict(history=record.history, trials=record.trials,
                 acceptance_checks=record.acceptance_checks))
        for trial in record.trials:
            key = trial.get("reason") or trial.get("status")
            refusals[key] = refusals.get(key, 0) + 1
    summary = dict(case=case, arm=arm, variant=variant, status=result.status, reason=result.reason,
                   detail=result.detail, elapsed_seconds=time.perf_counter() - started, work=ledger.snapshot(),
                   initial_geometry=geometry(ac.start_curve()), final_geometry=geometry(result.curve),
                   trial_outcomes=refusals, accepted_state_radii=radii,
                   stages=[{k: v for k, v in asdict(r).items() if k not in ("curve", "history", "trials",
                            "acceptance_checks")} for r in result.stages], stage_scores=scores,
                   final_curve=dict(real=result.curve.coefficients.real.tolist(),
                                    imag=result.curve.coefficients.imag.tolist()))
    sc.write(folder / "result.json", summary)
    return dict(case=case, arm=arm, variant=variant, status=result.status,
                final_symmetric_rms_mm=summary["final_geometry"]["symmetric_rms_m"] * 1e3,
                final_hausdorff_mm=summary["final_geometry"]["hausdorff_m"] * 1e3,
                units=ledger.units, seconds=summary["elapsed_seconds"])


def _run(job):
    try:
        return run(*job)
    except Exception as exc:  # recorded, never hidden
        return dict(job=[str(j) for j in job], error=repr(exc))


def run_all(output, workers):
    jobs = [(output, case, arm, variant) for variant in ("V1", "V2", "V3") for arm in ARMS for case in ac.CASES]
    with ProcessPoolExecutor(workers) as pool:
        for row in pool.map(_run, jobs):
            print(json.dumps(row), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--one", nargs=3, metavar=("CASE", "ARM", "VARIANT"))
    parser.add_argument("--amend")
    args = parser.parse_args()
    if args.amend:
        ac.amend(args.output, args.amend)
    if args.one:
        print(json.dumps(run(args.output, *args.one)), flush=True)
    if args.prepare:
        prepare(args.output)
    if args.all:
        run_all(args.output, args.workers)


if __name__ == "__main__":
    main()
