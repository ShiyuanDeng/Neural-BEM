"""Gated SC-048 comparison of normal bandwidth and exact global directions."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "SC-047-coupled-continuation"))
from qualify import (ROOT, LENGTH, BAND, FREQUENCIES, ProjectedUpdate, setup, scene,
                     write, record_scene, load_scene, manifest, verify, relative)
from strategies import stage, CONFIG, score
from global_update import GlobalUpdate
from experiments.shape_continuation.forward import solve, shape_jacobian, Work
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import (Ledger, Objective, fit_stage, Stop, NORMAL_RETURN, STAGE_QUOTA)
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate

PLAN = ROOT / "docs/iterations/shape_frequency_continuation/iteration_27/03_plan.md"
ARMS = ("normal_m5", "normal_m9", "global_m5")


def initial_state(separation):
    initial = scene(separation, initial=True)
    ellipse = initial.components[0].coefficients.copy()
    ellipse[BAND - 1] *= 1.12
    update = ProjectedUpdate(LENGTH)
    local = update.prepare(initial.components[1], 3, BAND)
    perturbation = np.zeros(7)
    perturbation[2], perturbation[6] = .0015, .0010
    c_shape, _ = update.trial(local, perturbation)
    return MultiCurve((FourierCurve(ellipse), c_shape), initial.ids)


def frozen_manifest():
    frozen = manifest(dict(study="SC-048", config=asdict(CONFIG), arms=ARMS,
        fixed_modes={"normal_m5": 5, "normal_m9": 9, "global_m5": 5},
        dispatches=6, cap=200, per_arm_seconds=900, qualification_seconds=600,
        qualification_solve_cap=200, extra_direction_cutoff=.05, seed=4801,
        perturbations=dict(ellipse_negative_first_factor=1.12, c_a2_m=.0015, c_b3_m=.001)))
    for path in (PLAN, Path(__file__), HERE / "global_update.py", HERE.parent / "SC-047-coupled-continuation/strategies.py"):
        frozen["source_sha256"][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return frozen


def qualify(catalog, contrast):
    current = initial_state(.14)
    base = ProjectedUpdate(LENGTH)
    update = MultiUpdate(GlobalUpdate(base))
    space = update.prepare(current, 5, BAND)
    trial, _ = update.trial(space, np.zeros(len(space.orders)))
    np.testing.assert_array_equal(trial.coefficients, current.coefficients)
    checks = []
    for local in space.local_spaces:
        nodes = local.curve.nodes(256)
        dim = len(local.local.orders)
        original = base.velocities(local.local, nodes)
        np.testing.assert_allclose(update.base.velocities(local, nodes)[:, :dim], original, rtol=0, atol=0)
        metric = update.base.metric(local, "mass")
        np.linalg.cholesky(metric)
        checks.append(dict(dimension=len(local.orders), labels=local.labels,
                           metric_min_eigenvalue=float(np.linalg.eigvalsh(metric).min())))
    work = Work(max_forwards=200, max_seconds=600)
    rows = []
    rng = np.random.default_rng(48)
    for o in catalog:
        state = solve(current, o.wavenumber, contrast, o.acquisition, 256, work=work)
        jac = shape_jacobian(state, update.velocities(space, state.curve), work=work)
        for active in ((0,), (1,), (0, 1)):
            direction = np.zeros(len(space.orders))
            for i in active:
                direction[space.slices[i]] = rng.normal(size=space.slices[i].stop - space.slices[i].start)
            direction /= np.linalg.norm(direction)
            errors = []
            for eps in (1e-6, 5e-7):
                values = [solve(update.trial(space, sign * eps * direction)[0],
                    o.wavenumber, contrast, o.acquisition, 256, work=work).prediction for sign in (1, -1)]
                errors.append(relative((values[0] - values[1]) / (2 * eps), jac @ direction))
            rows.append(dict(wavenumber=o.wavenumber, active=active, errors=errors))
            write(HERE / "qualification.json", dict(status="RUNNING", checks=checks, rows=rows, work=work.summary()))
    passed = bool(all(max(row["errors"]) <= 1e-3 for row in rows))
    result = dict(status="PASS" if passed else "FAIL", passed=passed, checks=checks, rows=rows,
                   work=work.summary(), seconds=time.perf_counter() - work.started)
    write(HERE / "qualification.json", result)
    return passed


def fit(initial, catalog, contrast, arm, folder):
    ledger = Ledger(cap=200, seconds=900, endpoint_reserve=16)
    ledger.begin_stage(arm, None)
    base = ProjectedUpdate(LENGTH)
    update = MultiUpdate(GlobalUpdate(base) if arm == "global_m5" else base)
    modes = 9 if arm == "normal_m9" else 5
    current, records, states = initial, [], []
    outcome = "COMPLETED_DISPATCHES"
    try:
        for i in range(6):
            result = fit_stage(current, stage(catalog, modes, f"dispatch_{i}"), contrast, update, CONFIG, ledger)
            current = result.curve
            records.append(dict(dispatch=i, outcome=result.outcome, stop=result.stop_reason,
                accepted=result.accepted_steps, initial_loss=result.initial_loss, final_loss=result.final_loss,
                history=result.history, trials=result.trials, checks=result.acceptance_checks,
                dimensions=[len(row["step_m"]) for row in result.history], units=ledger.units))
            states.append(dict(state=record_scene(current), units=ledger.units))
            write(folder / "checkpoint.json", dict(records=records, states=states, work=ledger.snapshot()))
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                outcome = result.outcome
                break
            if result.converged:
                outcome = "CONVERGED_" + result.stop_reason
                break
    except Stop as exc:
        outcome = exc.code
    audit = {}
    try:
        with ledger.endpoint_scope():
            obj = Objective(stage(catalog, modes), contrast, CONFIG, ledger)
            low, high = obj.production(current, "endpoint"), obj.refined(current)
            if low is None or high is None:
                raise RuntimeError("Unqualified endpoint.")
            discrepancy = np.linalg.norm(low.prediction - high.prediction, axis=0) / np.linalg.norm(high.prediction, axis=0)
            audit = dict(passed=bool(np.all(discrepancy <= 1e-6)), discrepancy=discrepancy,
                         loss=low.loss, refined_loss=high.loss)
    except Exception as exc:
        audit = dict(passed=False, error=repr(exc))
    result = dict(arm=arm, outcome=outcome, records=records, states=states, work=ledger.snapshot(),
        final_state=record_scene(current), audit=audit, update_counts=base.counts,
        maximum_dimension=max((max(r["dimensions"], default=0) for r in records), default=0))
    write(folder / "unscored.json", result)
    return current, result


def gate(arms):
    five, nine, enriched = [arms[a] for a in ARMS]
    return bool(all(r["audit"]["passed"] and r["score"]["valid"] for r in arms.values())
        and enriched["score"]["worst_rms_mm"] <= .75 * five["score"]["worst_rms_mm"]
        and enriched["score"]["worst_rms_mm"] <= 1.05 * nine["score"]["worst_rms_mm"]
        and all(enriched["score"]["objects"][j]["rms_mm"] <= 1.10 * nine["score"]["objects"][j]["rms_mm"]
                for j in (0, 1))
        and enriched["work"]["work_units"] <= nine["work"]["work_units"]
        and enriched["maximum_dimension"] < nine["maximum_dimension"])


def run():
    prior = HERE.parent / "SC-047-coupled-continuation"
    if len(json.loads((prior / "strategy_summary.json").read_text())) != 12:
        raise RuntimeError("SC-047 strategy campaign must finish first.")
    if json.loads((prior / "topology.json").read_text())["status"] == "RUNNING":
        raise RuntimeError("SC-047 topology must finish before this study.")
    if (HERE / "summary.json").exists():
        raise FileExistsError("Preserve the existing study.")
    frozen = frozen_manifest()
    write(HERE / "manifest.json", frozen)
    catalog, contrast, _ = setup()
    if not qualify(catalog, contrast):
        write(HERE / "summary.json", dict(status="QUALIFICATION_FAILED", cases=[]))
        return
    verify(frozen)
    results = []
    # Input generation is interleaved with fits; its timer must include the
    # declared intervening arm ceilings, while its solve cap stays sixteen.
    generation = Work(max_forwards=16, max_seconds=12 * 900 + 600)
    for separation, noisy in ((.14, False), (.14, True), (.20, False), (.20, True)):
        current, truth = initial_state(separation), scene(separation)
        clean = np.column_stack([solve(truth, o.wavenumber, contrast, o.acquisition, 512, work=generation).prediction
                                 for o in catalog])
        rng = np.random.default_rng(4801)
        noise = rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape)
        noise *= .01 * np.linalg.norm(clean, axis=0) / np.linalg.norm(noise, axis=0)
        observed = clean + noise if noisy else clean
        observations = tuple(Observation(o.wavenumber, o.acquisition, observed[:, k]) for k, o in enumerate(catalog))
        case = f"sep{separation:.2f}_{'noise' if noisy else 'clean'}"
        write(HERE / "inputs" / f"{case}.json", dict(initial=record_scene(current), truth=record_scene(truth),
            observed_real=observed.real, observed_imag=observed.imag, noise_real=noise.real, noise_imag=noise.imag))
        arms = {}
        for arm in ARMS:
            endpoint, result = fit(current, observations, contrast, arm, HERE / "runs" / case / arm)
            result.update(case=case, score=score(endpoint, truth), initial_score=score(current, truth))
            write(HERE / "runs" / case / arm / "result.json", result)
            arms[arm] = result
            print(json.dumps(dict(case=case, arm=arm, rms_mm=result["score"]["worst_rms_mm"],
                units=result["work"]["work_units"], dimension=result["maximum_dimension"],
                qualified=result["audit"]["passed"])), flush=True)
            verify(frozen)
        passed = gate(arms)
        results.append(dict(case=case, gate=passed, arms={a: {k: r[k] for k in
            ("score", "initial_score", "audit", "work", "outcome", "maximum_dimension")} for a, r in arms.items()}))
        write(HERE / "summary.json", dict(status="RUNNING", cases=results, input_work=generation.summary()))
        if len(results) == 1 and not passed:
            write(HERE / "summary.json", dict(status="PRIMARY_GATE_FAILED", cases=results,
                input_work=generation.summary(), decision="STOP_NO_TRANSFER_OR_PROMOTION"))
            return
    write(HERE / "summary.json", dict(status="COMPLETE", cases=results, input_work=generation.summary(),
        transfer_passed=all(r["gate"] for r in results)))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        import traceback
        write(HERE / "error.json", dict(error=repr(exc), traceback=traceback.format_exc()))
        raise
