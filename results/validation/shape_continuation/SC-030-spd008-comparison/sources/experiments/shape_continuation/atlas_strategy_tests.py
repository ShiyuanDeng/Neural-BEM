"""SC-028's frozen development comparison; core solver and defaults unchanged.

The fitting segment receives only observations, its start and numerical
settings. Truth and unused catalog observations enter post-run scoring only.
See iteration_10/03_plan.md for interventions, gates and hard budgets.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import time
import traceback

import numpy as np

from . import atlas_cases as ac
from . import atlas_dataset as ad
from . import spd_cases as sc
from .atlas_survey import symmetric_rms_distance
from .forward import solve, shape_jacobian
from .geometry import FourierCurve, normal_basis
from .lm_backend import Ledger, NORMAL_RETURN, STAGE_QUOTA, Stop, fit_stage, stage_record
from .metrics import boundary_distance
from .updates import BorgesUpdate

CASES = tuple(ad.INPUTS)
PREFIXES = ("baseline", "protect")
SUFFIXES = ("repeat", "extend")
EXTRA_HZ = (1.5e9, 1.75e9, 2e9, 2.25e9, 2.5e9)
PREFIX_CAP, PATH_CAP, PATH_SECONDS = 8012, 15512, 3600.
PLAN = sc.ROOT / "docs/iterations/shape_frequency_continuation/iteration_10/03_plan.md"


def source_folder(case):
    return ad.BASE / ad.INPUTS[case] / "inputs" / case


def catalog_only(case):
    """No truth is loaded through this fitting-data entry point."""
    data = sc.read(source_folder(case) / "observations.json")
    return ac.observations(np.array(data["observed_real"]) + 1j*np.array(data["observed_imag"]))


def curve_from(record):
    return FourierCurve(np.array(record["real"]) + 1j*np.array(record["imag"]))


def curve_record(curve):
    return dict(real=curve.coefficients.real, imag=curve.coefficients.imag)


def schedules(catalog, prefix, suffix=None):
    if prefix not in PREFIXES or suffix not in (None, *SUFFIXES):
        raise ValueError("Unknown frozen comparison arm")
    policy, config = ac.policy(catalog, "borges")
    stages = list(policy.stages)
    if prefix == "protect":
        stages[0] = replace(stages[0], update_modes=2)
    if suffix is None:
        return stages, config
    original = list(stages[-1].observations)
    lookup = dict(zip(ac.CATALOG_HZ, catalog))
    tail = []
    for n, frequency in enumerate(EXTRA_HZ, 5):
        highest = lookup[frequency]
        active = original + [lookup[f] for f in EXTRA_HZ if f <= frequency] if suffix == "extend" else original
        band = ac.BAND_RULES["borges"](highest.wavenumber, highest.wavenumber*np.sqrt(ac.contrast()))
        tail.append(replace(stages[-1], label=f"stage_{n}", observations=tuple(active),
            weights=tuple(np.ones(len(active))/len(active)), update_modes=band, quota=1500,
            discrepancy_tolerances=(1e-5, *([1e-7]*(len(active)-1)))))
    return tail, config


def restored_ledger(parent=None):
    ledger = Ledger(cap=PREFIX_CAP if parent is None else PATH_CAP,
                    seconds=PATH_SECONDS if parent is None else max(0., PATH_SECONDS-parent["inverse_seconds"]))
    if parent is not None:
        work = parent["work"]
        ledger.units = work["work_units"]
        ledger.solves, ledger.reciprocal, ledger.failed = (dict(work[k]) for k in ("solves", "reciprocal_batches", "failed"))
    return ledger


def optimize_segment(initial, stages, contrast, config, update, ledger, folder):
    """Fit fixed stages, checkpointing every return, including numerical failures."""
    curve, records, status, reason = initial, [], "COMPLETED_SCHEDULE", None
    for stage in stages:
        try:
            ledger.begin_stage(stage.label, stage.quota)
            record = fit_stage(curve, stage, contrast, update, config, ledger)
        except Stop as exc:
            status, reason = "HARD_STOP", exc.code
            break
        records.append(record)
        curve = record.curve
        sc.write(folder / f"{stage.label}_history.json", dict(history=record.history, trials=record.trials,
            acceptance_checks=record.acceptance_checks))
        sc.write(folder / "checkpoint.json", dict(final_curve=curve_record(curve), stage=stage.label,
            work=ledger.snapshot(), outcome=record.outcome, stop=record.stop_reason))
        if record.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
            status, reason = "HARD_STOP", record.outcome
            break
    return curve, records, status, reason


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = {str(p.relative_to(sc.ROOT)): ad.digest(p) for case in CASES
              for p in (source_folder(case)/name for name in ("observations.json", "truth.json", "oracle_check.json"))}
    assert all(sc.read(source_folder(c)/"oracle_check.json")["passed"] for c in CASES)
    sc.write(output / "manifest.json", dict(experiment="SC-028", source_sha256=sc.source_hashes(), inputs=inputs,
        plan=str(PLAN.relative_to(sc.ROOT)), plan_sha256=ad.digest(PLAN),
        parent_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        cases=CASES, prefixes=PREFIXES, suffixes=SUFFIXES, extra_frequencies_hz=EXTRA_HZ,
        prefix_cap=PREFIX_CAP, path_cap=PATH_CAP, path_seconds=PATH_SECONDS,
        prepared=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def verify(output):
    manifest = sc.read(output / "manifest.json")
    if manifest["source_sha256"] != sc.source_hashes():
        raise RuntimeError("Frozen numerical sources changed")
    if any(ad.digest(sc.ROOT/p) != h for p,h in manifest["inputs"].items()):
        raise RuntimeError("Frozen input changed")


def qualification_cell(job):
    case, frequency = job
    old = sc.read(ad.BASE / "SC-025-band-policies/runs/ladder" / case / "result.json")
    curve = curve_from(old["final_curve"])
    obs = catalog_only(case)[ac.CATALOG_HZ.index(frequency)]
    values, jacobians = [], []
    for nodes in (512, 1024):
        state = solve(curve, obs.wavenumber, ac.contrast(), obs.acquisition, nodes)
        values.append(state.prediction)
        jacobians.append(shape_jacobian(state, normal_basis(state.curve, 48)/sc.LENGTH))
    field = np.linalg.norm(values[0]-values[1])/np.linalg.norm(values[1])
    jac = np.max(np.linalg.norm(jacobians[0]-jacobians[1], axis=0)/np.maximum(np.linalg.norm(jacobians[1], axis=0), 1e-300))
    return dict(case=case, frequency_hz=frequency, field_relative=float(field), jacobian_column_relative=float(jac),
                passed=bool(field <= 1e-6 and jac <= 1e-6), work_units=4)


def qualify(output, workers):
    verify(output)
    started = time.perf_counter()
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(qualification_cell, [(c, f) for c in CASES for f in (1.5e9, 2.5e9)]))
    seconds = time.perf_counter()-started
    report = dict(rows=rows, work_units=sum(r["work_units"] for r in rows), seconds=seconds,
                  passed=all(r["passed"] for r in rows) and seconds <= 600)
    sc.write(output / "qualification.json", report)
    print(json.dumps(report), flush=True)
    if not report["passed"]:
        raise RuntimeError("Numerical qualification failed; full campaign is gated off")


def score(case, curve, catalog):
    """Evaluation only, after fitting returns. Nothing here selects an iterate."""
    truth = curve_from(sc.read(source_folder(case) / "truth.json"))
    error, bound = boundary_distance(truth, curve)
    residuals = []
    for obs in catalog:
        prediction = solve(curve, obs.wavenumber, ac.contrast(), obs.acquisition, 1024).prediction
        residuals.append(float(np.linalg.norm(prediction-obs.scattered)/np.linalg.norm(obs.scattered)))
    return dict(symmetric_rms_mm=1e3*symmetric_rms_distance(curve, truth.values(16384), sc.LENGTH),
        hausdorff_mm=1e3*sc.LENGTH*error, hausdorff_upper_mm=1e3*sc.LENGTH*(error+bound),
        tightest_radius_mm=float(1e3*sc.LENGTH/np.max(np.abs(curve.nodes(8192).curvatures))),
        catalog_relative_residual=residuals, evaluation_field_solves=len(catalog))


def mechanism(records):
    radii = []
    for r in records:
        for row in r.history:
            radii.append(float(1e3*sc.LENGTH/np.max(np.abs(curve_from(row["coefficients"]).nodes(8192).curvatures))))
    return dict(min_radius_mm=min(radii, default=None),
        unresolved_projection_refusals=sum(t.get("reason") == "unresolved_projection" for r in records for t in r.trials),
        stage_1_max_rms_step_mm=max((1e3*h.get("rms_normal_m", 0.) for r in records if r.stage_label == "stage_1"
                                    for h in r.history), default=None))


def replay_check(folder, result):
    old_folder = ad.BASE / "SC-025-band-policies/runs/ladder/wrong_circle"
    old = sc.read(old_folder / "result.json")
    reference = curve_from(old["final_curve"]).coefficients
    error = np.linalg.norm(curve_from(result["final_curve"]).coefficients-reference)/np.linalg.norm(reference)
    same_history = True
    for stage in result["stages"]:
        previous = sc.read(old_folder / f"{stage['stage']}_history.json")["history"]
        current = sc.read(folder / f"{stage['stage']}_history.json")["history"]
        same_history &= len(previous) == len(current)
        if len(previous) == len(current):
            same_history &= all(np.allclose(curve_from(a["coefficients"]).coefficients,
                                           curve_from(b["coefficients"]).coefficients, rtol=1e-10, atol=1e-12)
                                and a["work"]["work_units"] == b["work"]["work_units"] for a,b in zip(previous,current))
    same_stops = [(s["stage"],s["stop"],s["accepted"]) for s in result["stages"]] == [
                  (s["stage"],s["stop"],s["accepted"]) for s in old["stage_scores"]]
    return dict(coefficient_relative=float(error), same_history=bool(same_history), same_stops=same_stops,
        same_work=result["work"]["work_units"] == old["work"]["work_units"],
        passed=bool(error <= 1e-10 and same_history and same_stops and result["work"]["work_units"] == old["work"]["work_units"]))


def run_path(output, case, prefix, suffix=None):
    verify(output)
    if not sc.read(output / "qualification.json")["passed"]:
        raise RuntimeError("Preflight gate failed")
    if (case, prefix, suffix) != ("wrong_circle", "baseline", None):
        if not sc.read(output / "replay.json")["passed"]:
            raise RuntimeError("Baseline replay gate failed")
    folder = output / "runs" / prefix / case / (suffix or "none")
    if (folder / "result.json").exists():
        return sc.read(folder / "result.json")
    folder.mkdir(parents=True, exist_ok=False)
    catalog = catalog_only(case)
    stages, config = schedules(catalog, prefix, suffix)
    update = BorgesUpdate(sc.LENGTH, projection_tolerance=1e-5)
    parent, parent_hash = None, None
    if suffix is not None:
        path = folder.parent / "none" / "result.json"
        parent = sc.read(path)
        if parent["status"] != "COMPLETED_SCHEDULE":
            raise RuntimeError("Prefix did not complete; suffix not released")
        initial, parent_hash = curve_from(parent["final_curve"]), ad.digest(path)
    else:
        initial = update.regauge(ac.start_curve(), stages[0].curve_modes)[0]
    ledger = restored_ledger(parent)
    from dataclasses import asdict
    sc.write(folder / "configuration.json", dict(case=case, prefix=prefix, suffix=suffix,
        backend=asdict(config), update=update.settings(), stages=[stage_record(s) for s in stages],
        parent_result_sha256=parent_hash, parent_work_units=0 if parent is None else parent["work"]["work_units"]))
    curve, records, status, reason = optimize_segment(initial, stages, ac.contrast(), config, update, ledger, folder)
    work = ledger.snapshot()
    result = dict(case=case, prefix=prefix, suffix=suffix or "none", status=status, reason=reason,
        final_curve=curve_record(curve), work=work, inverse_seconds=work["seconds"]+(0 if parent is None else parent["inverse_seconds"]),
        parent_result_sha256=parent_hash, stages=[dict(stage=r.stage_label, outcome=r.outcome, stop=r.stop_reason,
            accepted=r.accepted_steps, initial_loss=r.initial_loss, final_loss=r.final_loss, units=r.work["stage_units"])
            for r in records], mechanism=mechanism(records))
    sc.write(folder / "unscored_result.json", result)
    result["score"] = score(case, curve, catalog)
    sc.write(folder / "result.json", result)
    if (case, prefix, suffix) == ("wrong_circle", "baseline", None):
        replay = replay_check(folder, result)
        sc.write(output / "replay.json", replay)
        if not replay["passed"]:
            raise RuntimeError("Baseline replay failed")
    return result


def worker(job):
    try:
        result = run_path(*job)
        return {k:result[k] for k in ("case", "prefix", "suffix", "status", "score", "inverse_seconds")}
    except Exception:
        return dict(job=[str(x) for x in job], error=traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "qualify", "prefix", "suffix"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    parser.add_argument("--prefixes", nargs="+", choices=PREFIXES, default=list(PREFIXES))
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("The frozen plan allows 1-12 workers")
    if args.phase == "prepare":
        prepare(args.output)
    elif args.phase == "qualify":
        qualify(args.output, args.workers)
    else:
        if args.phase == "prefix" and not (args.output / "replay.json").exists():
            print(json.dumps(worker((args.output, "wrong_circle", "baseline", None))), flush=True)
            if not sc.read(args.output / "replay.json")["passed"]:
                raise RuntimeError("Baseline replay gate failed")
        suffixes = (None,) if args.phase == "prefix" else SUFFIXES
        jobs = [(args.output, c, p, s) for c in args.cases for p in args.prefixes for s in suffixes]
        with ProcessPoolExecutor(args.workers) as pool:
            errors = 0
            for row in pool.map(worker, jobs):
                print(json.dumps(row), flush=True)
                errors += "error" in row
        if errors:
            raise RuntimeError(f"{errors} paths failed; inspect the retained logs")


if __name__ == "__main__":
    main()
