"""SC-031: curvature-aware regularizing LM against the stage-1 collapse.

Frozen contract: docs/iterations/shape_frequency_continuation/iteration_13/03_plan.md.
Phases: prepare -> qualify -> stage-a -> gate -> (stage-b | score-a) -> report.
SC-032 (iteration_14/03_plan.md) continues SC-031's stage-A checkpoints in a
fresh bundle: prepare-continuation -> continue.
Run with the EMNerf interpreter, PYTHONPATH=solvers:. and one BLAS thread per
worker. The fitting path receives observations, its start and settings only;
truth enters `ast.score` after a path returns.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

from ordered_boundary.validation_cache import geometry_validation
from . import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from .lm_backend import Ledger, NORMAL_RETURN, STAGE_QUOTA, Stop, fit_stage, stage_record
from .updates import BorgesUpdate

CASES = ast.CASES
ARMS = dict(R1=dict(damping_rule="hanke", metric="mass", log_model=True),
            R2=dict(damping_rule="hanke", metric="curvature", log_model=True))
PREFIX_CAP, PREFIX_SECONDS = 8012, 2700.
CAMPAIGN_UNITS, QUALIFY_UNITS, MAX_WORKERS = 25000, 1000, 6
GATE_MM, COLLAPSE_MM = 7.0, 5.0
OUTPUT = sc.ROOT / "results/validation/shape_continuation/SC-031-regularizing-metric"
PLAN = sc.ROOT / "docs/iterations/shape_frequency_continuation/iteration_13/03_plan.md"
TEST = sc.ROOT / "pytest/shape_continuation/test_regularizing_metric.py"
R0 = sc.ROOT / "results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline"
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
CONTINUATION_PLAN = sc.ROOT / "docs/iterations/shape_frequency_continuation/iteration_14/03_plan.md"
CONTINUATION_OUTPUT = sc.ROOT / "results/validation/shape_continuation/SC-032-regularizing-metric-prefix"
CONTINUATION_UNITS = 10000
DRIVER = "experiments/shape_continuation/regularity_cases.py"
HEAVY_FIRST = ("circle_to_c", "peanut", "kite", "hook", "circle_to_star", "wrong_circle")


def sources():
    return {**sc.source_hashes(), str(TEST.relative_to(sc.ROOT)): sc.digest(TEST)}


def radius_mm(curve):
    return float(1e3 * sc.LENGTH / np.max(np.abs(curve.nodes(8192).curvatures)))


def untimed(value):
    if isinstance(value, dict):
        return {k: untimed(v) for k, v in value.items() if k != "seconds"}
    if isinstance(value, list):
        return [untimed(v) for v in value]
    return value


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = {str(p.relative_to(sc.ROOT)): sc.digest(p) for case in CASES for p in
              (ast.source_folder(case) / n for n in ("observations.json", "truth.json", "oracle_check.json"))}
    assert all(sc.read(ast.source_folder(c) / "oracle_check.json")["passed"] for c in CASES)
    sc.write(output / "manifest.json", dict(experiment="SC-031", source_sha256=sources(), input_sha256=inputs,
        plan_sha256=sc.digest(PLAN), cases=CASES, arms=ARMS, prefix_cap=PREFIX_CAP, prefix_seconds=PREFIX_SECONDS,
        campaign_units=CAMPAIGN_UNITS, qualify_units=QUALIFY_UNITS, workers=MAX_WORKERS, gate_mm=GATE_MM,
        collapse_mm=COLLAPSE_MM, reference=str(R0.relative_to(sc.ROOT)),
        parent_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        command=sys.argv, prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def verify(output):
    manifest = sc.read(output / "manifest.json")
    if sources() != manifest["source_sha256"]:
        raise RuntimeError("Frozen numerical sources changed")
    if any(sc.digest(sc.ROOT / p) != h for p, h in manifest["input_sha256"].items()):
        raise RuntimeError("Frozen input changed")
    if sc.digest(sc.ROOT / manifest.get("plan", str(PLAN.relative_to(sc.ROOT)))) != manifest["plan_sha256"]:
        raise RuntimeError("Frozen plan changed")


def settings(case, arm):
    catalog = ast.catalog_only(case)
    stages, config = ast.schedules(catalog, "baseline")
    return catalog, stages, (config if arm == "R0" else replace(config, **ARMS[arm]))


def fit(folder, stages, config, curve, ledger):
    """Fit stages under the qualified exact cache, checkpointing every return."""
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5)
    rows, status, reason, snapshots = [], "COMPLETED_SCHEDULE", None, []
    with geometry_validation("cache", on_fit=snapshots.append):
        for stage in stages:
            try:
                ledger.begin_stage(stage.label, stage.quota)
                record = fit_stage(curve, stage, ac.contrast(), update, config, ledger)
            except Stop as exc:
                status, reason = "HARD_STOP", exc.code
                break
            curve = record.curve
            rows.append(dict(stage=stage.label, outcome=record.outcome, stop=record.stop_reason,
                             accepted=record.accepted_steps, initial_loss=record.initial_loss,
                             final_loss=record.final_loss, units=record.work["stage_units"],
                             end_radius_mm=radius_mm(curve)))
            sc.write(folder / f"{stage.label}_history.json", dict(history=record.history, trials=record.trials,
                     acceptance_checks=record.acceptance_checks))
            if record.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                status, reason = "HARD_STOP", record.outcome
                break
    return curve, rows, status, reason, [s for s in snapshots if isinstance(s, dict)]


def restored(snapshot, cap, seconds):
    ledger = Ledger(cap=cap, seconds=seconds)
    ledger.units = snapshot["work_units"]
    ledger.solves, ledger.reciprocal, ledger.failed = (dict(snapshot[k]) for k in
                                                       ("solves", "reciprocal_batches", "failed"))
    return ledger


def prepare_continuation(output, source):
    """SC-032: a fresh bundle seeded with hashed copies of SC-031's stage-A records."""
    parent = sc.read(source / "manifest.json")
    current = sources()
    changed = sorted(k for k in set(parent["source_sha256"]) | set(current)
                     if parent["source_sha256"].get(k) != current.get(k))
    if changed != [DRIVER]:
        raise RuntimeError(f"Numerical sources differ from the resumed experiment: {changed}")
    if sc.read(source / "gate.json")["released"]:
        raise RuntimeError("SC-031 already released its own stage B")
    output.mkdir(parents=True, exist_ok=False)
    copied = {}
    for arm in ARMS:
        for case in CASES:
            for name in ("configuration.json", "stage_1_history.json", "stage_a.json"):
                origin, target = source / "runs" / arm / case / name, output / "runs" / arm / case / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, target)
                copied[str(origin.relative_to(sc.ROOT))] = sc.digest(origin)
    sc.write(output / "manifest.json", dict(experiment="SC-032", parent_experiment="SC-031",
        parent_manifest_sha256=sc.digest(source / "manifest.json"), source_sha256=current,
        input_sha256=parent["input_sha256"], plan=str(CONTINUATION_PLAN.relative_to(sc.ROOT)),
        plan_sha256=sc.digest(CONTINUATION_PLAN), copied_stage_a_sha256=copied, cases=CASES, arms=ARMS,
        prefix_cap=PREFIX_CAP, prefix_seconds=PREFIX_SECONDS, campaign_units=CONTINUATION_UNITS,
        stage_b_allocation_per_path=CONTINUATION_UNITS // (len(ARMS) * len(CASES)), workers=MAX_WORKERS,
        reference=str(R0.relative_to(sc.ROOT)),
        parent_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        command=sys.argv, prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


# --- qualification ---------------------------------------------------------

def replay(job):
    output, case = job
    folder = output / "qualification" / case
    folder.mkdir(parents=True, exist_ok=True)
    catalog, stages, config = settings(case, "R0")
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5)
    start = update.regauge(ac.start_curve(), stages[0].curve_modes)[0]
    ledger = Ledger(cap=PREFIX_CAP, seconds=PREFIX_SECONDS)
    curve, rows, status, reason, _ = fit(folder, stages, config, start, ledger)
    old = sc.read(R0 / case / "none" / "result.json")
    same = status == old["status"] and [(r["stage"], r["stop"], r["accepted"]) for r in rows] == [
        (s["stage"], s["stop"], s["accepted"]) for s in old["stages"]]
    for row in rows:
        new = untimed(sc.read(folder / f"{row['stage']}_history.json"))
        previous = untimed(sc.read(R0 / case / "none" / f"{row['stage']}_history.json"))
        same &= new == previous
    same &= ast.curve_record(curve)["real"].tolist() == old["final_curve"]["real"] and \
        ast.curve_record(curve)["imag"].tolist() == old["final_curve"]["imag"]
    return dict(case=case, identical=bool(same), work_units=ledger.units, reference_units=old["work"]["work_units"])


def qualify(output):
    verify(output)
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", str(TEST),
                            str(sc.ROOT / "experiments/shape_continuation/test_lm_backend.py"),
                            str(sc.ROOT / "pytest/shape_continuation")], cwd=sc.ROOT, capture_output=True, text=True)
    with ProcessPoolExecutor(2) as pool:
        replays = list(pool.map(replay, [(output, "wrong_circle"), (output, "circle_to_c")]))
    units = sum(r["work_units"] for r in replays)
    record = dict(tests_passed=tests.returncode == 0, tests_tail=tests.stdout.strip().splitlines()[-1:],
                  replays=replays, units=units, within_budget=units <= QUALIFY_UNITS)
    record["passed"] = bool(record["tests_passed"] and all(r["identical"] for r in replays) and record["within_budget"])
    sc.write(output / "qualification.json", record)
    print(record, flush=True)
    if not record["passed"]:
        raise RuntimeError("SC-031 qualification failed")


# --- stages ----------------------------------------------------------------

def stage_a(job):
    output, arm, case = job
    try:
        verify(output)
        folder = output / "runs" / arm / case
        folder.mkdir(parents=True, exist_ok=False)
        catalog, stages, config = settings(case, arm)
        update = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5)
        start = update.regauge(ac.start_curve(), stages[0].curve_modes)[0]
        sc.write(folder / "configuration.json", dict(case=case, arm=arm, backend=asdict(config),
                 update=update.settings(), stages=[stage_record(s) for s in stages]))
        ledger = Ledger(cap=PREFIX_CAP, seconds=PREFIX_SECONDS)
        curve, rows, status, reason, cache = fit(folder, stages[:1], config, start, ledger)
        record = dict(case=case, arm=arm, status=status, reason=reason, final_curve=ast.curve_record(curve),
                      stages=rows, work=ledger.snapshot(), stage_1_end_radius_mm=radius_mm(curve), cache=cache)
        sc.write(folder / "stage_a.json", record)
        return {k: record[k] for k in ("case", "arm", "status", "reason", "stage_1_end_radius_mm")} | dict(
            units=record["work"]["work_units"])
    except Exception:
        return dict(job=[str(x) for x in job], error=traceback.format_exc())


def gate(output):
    rows = {(r["arm"], r["case"]): r for r in (sc.read(output / "runs" / a / c / "stage_a.json")
                                              for a in ARMS for c in CASES)}
    reference = {c: sc.read(R0 / c / "none" / "result.json") for c in CASES}
    r0_radius = {}
    for c in CASES:
        history = sc.read(R0 / c / "none" / "stage_1_history.json")["history"]
        r0_radius[c] = radius_mm(ast.curve_from(history[-1]["coefficients"]))
    added = [f"{a}/{c}" for (a, c), r in rows.items() if r["status"] != "COMPLETED_SCHEDULE"
             and reference[c]["stages"][0]["outcome"] == NORMAL_RETURN]
    targets = ("circle_to_c", "peanut")
    radii = {a: {c: rows[(a, c)]["stage_1_end_radius_mm"] for c in CASES} for a in ARMS}
    r2_hard = [x for x in added if x.startswith("R2/")]
    released = any(radii["R2"][c] >= GATE_MM for c in targets) and not r2_hard
    units = sum(r["work"]["work_units"] for r in rows.values())
    qualification = sc.read(output / "qualification.json")["units"]
    remaining = CAMPAIGN_UNITS - qualification - units
    record = dict(stage_1_end_radius_mm=dict(R0=r0_radius, **radii), gate_mm=GATE_MM, collapse_mm=COLLAPSE_MM,
                  added_hard_stops=added, released=bool(released), stage_a_units=units,
                  qualification_units=qualification, remaining_units=remaining,
                  stage_b_allocation_per_path=int(remaining // len(rows)) if released else 0,
                  hypothesis={c: dict(R2=radii["R2"][c], R1=radii["R1"][c], R0=r0_radius[c]) for c in targets})
    sc.write(output / "gate.json", record)
    print(record, flush=True)
    return record


def stage_b(job):
    output, arm, case, allocation = job
    try:
        verify(output)
        folder = output / "runs" / arm / case
        parent = sc.read(folder / "stage_a.json")
        catalog, stages, config = settings(case, arm)
        if parent["status"] != "COMPLETED_SCHEDULE":
            curve, rows, status, reason, cache = ast.curve_from(parent["final_curve"]), [], parent["status"], \
                parent["reason"], []
            ledger = restored(parent["work"], PREFIX_CAP, 0.)
            seconds = parent["work"]["seconds"]
        else:
            cap = min(PREFIX_CAP, parent["work"]["work_units"] + allocation)
            ledger = restored(parent["work"], cap, PREFIX_SECONDS - parent["work"]["seconds"])
            curve, rows, status, reason, cache = fit(folder, stages[1:], config,
                                                     ast.curve_from(parent["final_curve"]), ledger)
            seconds = parent["work"]["seconds"] + ledger.snapshot()["seconds"]
        return finish(folder, case, arm, catalog, curve, parent["stages"] + rows, status, reason,
                      ledger.snapshot(), seconds, dict(stage_b_unit_cap=ledger.cap, cache=cache))
    except Exception:
        return dict(job=[str(x) for x in job], error=traceback.format_exc())


def score_a(job):
    """Gate failed: score the stage-A endpoints; no further fitting."""
    output, arm, case, _ = job
    folder = output / "runs" / arm / case
    parent = sc.read(folder / "stage_a.json")
    catalog, _, _ = settings(case, arm)
    return finish(folder, case, arm, catalog, ast.curve_from(parent["final_curve"]), parent["stages"],
                  parent["status"], parent["reason"], parent["work"], parent["work"]["seconds"],
                  dict(stage_a_only=True))


def finish(folder, case, arm, catalog, curve, stages, status, reason, work, seconds, extra):
    result = dict(case=case, arm=arm, status=status, reason=reason, final_curve=ast.curve_record(curve),
                  stages=stages, work=work, inverse_seconds=seconds, **extra)
    sc.write(folder / "unscored_result.json", result)
    result["score"] = ast.score(case, curve, catalog)  # evaluation only, after fitting returned
    sc.write(folder / "result.json", result)
    return {k: result[k] for k in ("case", "arm", "status", "reason")} | dict(
        rms_mm=result["score"]["symmetric_rms_mm"], hausdorff_mm=result["score"]["hausdorff_mm"],
        units=work["work_units"])


def dispatch(function, jobs, workers):
    errors = 0
    with ProcessPoolExecutor(workers) as pool:
        for row in pool.map(function, jobs):
            print(row, flush=True)
            errors += "error" in row
    if errors:
        raise RuntimeError(f"{errors} jobs failed; see the log")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "qualify", "stage-a", "gate", "stage-b", "score-a",
                                          "prepare-continuation", "continue"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--source", type=Path, default=OUTPUT, help="SC-031 bundle to continue")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    args = parser.parse_args()
    if not 1 <= args.workers <= MAX_WORKERS:
        parser.error(f"The frozen plan allows 1-{MAX_WORKERS} workers")
    if args.output is None:
        args.output = CONTINUATION_OUTPUT if args.phase in ("prepare-continuation", "continue") else OUTPUT
    if args.phase == "prepare-continuation":
        return prepare_continuation(args.output, args.source)
    if args.phase == "continue":
        manifest = sc.read(args.output / "manifest.json")
        if not all(os.environ.get(k) == "1" for k in THREADS):
            parser.error("Set one BLAS thread per worker")
        return dispatch(stage_b, [(args.output, a, c, manifest["stage_b_allocation_per_path"])
                                  for c in HEAVY_FIRST for a in ARMS], args.workers)
    if args.phase != "prepare" and not all(os.environ.get(k) == "1" for k in THREADS):
        parser.error("Set one BLAS thread per worker")
    if args.phase == "prepare":
        prepare(args.output)
    elif args.phase == "qualify":
        qualify(args.output)
    elif args.phase == "stage-a":
        if not sc.read(args.output / "qualification.json")["passed"]:
            raise RuntimeError("Qualification has not passed")
        dispatch(stage_a, [(args.output, a, c) for a in ARMS for c in CASES], args.workers)
    elif args.phase == "gate":
        gate(args.output)
    else:
        record = sc.read(args.output / "gate.json")
        if (args.phase == "stage-b") != record["released"]:
            raise RuntimeError("Phase does not match the recorded gate decision")
        function = stage_b if args.phase == "stage-b" else score_a
        dispatch(function, [(args.output, a, c, record["stage_b_allocation_per_path"]) for a in ARMS for c in CASES],
                 args.workers)


if __name__ == "__main__":
    main()
