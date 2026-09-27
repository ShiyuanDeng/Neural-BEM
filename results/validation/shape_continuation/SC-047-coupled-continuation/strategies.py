"""Frozen SC-047 object-selection comparison; the optimizer receives no truth."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

from qualify import (HERE, ROOT, FREQUENCIES, LENGTH, BAND, ProjectedUpdate,
                     setup, scene, write, record_scene, load_scene, manifest, verify, relative)
from experiments.shape_continuation.forward import solve, Work
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import (
    BackendConfig, FitStage, Ledger, Objective, fit_stage, Stop, NORMAL_RETURN, STAGE_QUOTA)
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate, conditional_information
from experiments.shape_continuation.metrics import boundary_distance
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance

CONFIG = BackendConfig(step_control="physical", physical_step_bound_m=.002,
                       gradient_tolerance=1e-10, log_model=True)


def stage(catalog, modes, label="fit", iterations=1):
    return FitStage(label, tuple(catalog), (.25,) * 4, (1e-6,) * 4,
                    modes, BAND, 256, 512, iterations)


def score(current, truth):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rows = []
    for c, t in zip(current.components, truth.components):
        hausdorff, bound = boundary_distance(c, t, count=4096)
        nodes = c.nodes(4096)
        rows.append(dict(rms_mm=1e3 * symmetric_rms_distance(c, t.values(4096), LENGTH),
                         hausdorff_mm=hausdorff * LENGTH * 1e3, hausdorff_bound_mm=bound * LENGTH * 1e3,
                         min_radius_mm=LENGTH * 1e3 / np.max(np.abs(nodes.curvatures)),
                         speed_ratio=float(np.max(nodes.speeds) / np.min(nodes.speeds))))
    polygons = [Polygon(c.nodes(4096).points) for c in current.components]
    target = unary_union([Polygon(c.nodes(4096).points) for c in truth.components])
    recovered = unary_union(polygons)
    gap = min((a.distance(b) for i, a in enumerate(polygons) for b in polygons[i + 1:]), default=float("inf"))
    return dict(objects=rows, worst_rms_mm=max(r["rms_mm"] for r in rows),
                region_error=recovered.symmetric_difference(target).area / target.area,
                minimum_gap_mm=gap * LENGTH * 1e3, valid=all(p.is_valid for p in polygons))


def atlas(objective, current, update, modes):
    evaluation = objective.production(current, "atlas")
    if evaluation is None:
        raise RuntimeError("Unqualified atlas state.")
    space = update.prepare(current, modes, BAND)
    jac = objective.jacobian(evaluation, update, space)
    metrics = [update.base.metric(x, "mass") for x in space.local_spaces]
    rows = conditional_information(tuple(jac[:, s] for s in space.slices), metrics)
    scores = []
    for row in rows:
        u, s, _ = np.linalg.svd(row["conditional_jacobian"], full_matrices=False)
        keep = s > row["absolute_rank_threshold"]
        scores.append(float(np.linalg.norm(u[:, keep].T @ evaluation.residual)**2))
    report = [{k: v for k, v in row.items() if k not in ("conditional_jacobian", "conditional_gram")}
              for row in rows]
    return int(np.argmax(scores)), dict(object_scores=scores, blocks=report,
                                        objective_loss=evaluation.loss)


def fit(initial, catalog, contrast, arm, folder, *, dispatches=12, cap=400, seconds=1200.):
    """No truth, geometry scores, or held-out data enter this function."""
    ledger = Ledger(cap=cap, seconds=seconds, endpoint_reserve=16)
    ledger.begin_stage(arm, None)
    current, records, accepted = initial, [], []
    base = ProjectedUpdate(LENGTH)
    all_update = MultiUpdate(base)
    outcome = "COMPLETED_DISPATCHES"
    try:
        for i in range(dispatches):
            modes = 3 if i < 6 else 5
            fit_stage_config = stage(catalog, modes, f"dispatch_{i}")
            nomination = None
            if arm == "conditional":
                # Reserve nomination AND an initial optimizer model/step opportunity.
                ledger.reserve(8 + 20)
                chosen, nomination = atlas(Objective(fit_stage_config, contrast, CONFIG, ledger),
                                           current, all_update, modes)
                active = (chosen,)
            elif arm == "round_robin":
                active = (i % len(current.components),)
            else:
                active = None
            update = MultiUpdate(base, active=active)
            result = fit_stage(current, fit_stage_config, contrast, update, CONFIG, ledger)
            current = result.curve
            row = dict(dispatch=i, modes=modes, active=active, nomination=nomination,
                       outcome=result.outcome, stop=result.stop_reason, accepted=result.accepted_steps,
                       initial_loss=result.initial_loss, final_loss=result.final_loss,
                       trials=result.trials, checks=result.acceptance_checks,
                       history=result.history, units=ledger.units, seconds=result.seconds)
            records.append(row)
            accepted.append(dict(dispatch=i, state=record_scene(current), units=ledger.units))
            write(folder / "checkpoint.json", dict(state=record_scene(current), records=records,
                                                    accepted=accepted, work=ledger.snapshot()))
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                outcome = result.outcome
                break
            if result.converged:
                outcome = "CONVERGED_" + result.stop_reason
                break
    except Stop as exc:
        outcome = exc.code
    # Endpoint qualification is charged to the same cap, using its reserved budget.
    audit = {}
    try:
        with ledger.endpoint_scope():
            obj = Objective(stage(catalog, 5), contrast, CONFIG, ledger)
            low, high = obj.production(current, "endpoint"), obj.refined(current)
            if low is None or high is None:
                raise RuntimeError("Endpoint could not be evaluated.")
            discrepancy = np.linalg.norm(low.prediction - high.prediction, axis=0) / np.linalg.norm(high.prediction, axis=0)
            audit = dict(passed=bool(np.all(discrepancy <= 1e-6)), discrepancy=discrepancy,
                         loss=low.loss, refined_loss=high.loss)
    except Exception as exc:
        audit = dict(passed=False, error=repr(exc))
    row = dict(arm=arm, outcome=outcome, final_state=record_scene(current), records=records,
               accepted=accepted, audit=audit, work=ledger.snapshot(), update_counts=base.counts)
    write(folder / "unscored.json", row)
    return current, row


def prepare():
    if (HERE / "strategy_manifest.json").exists():
        return
    if not json.loads((HERE / "qualification.json").read_text())["passed"]:
        raise RuntimeError("Forward and derivative gate failed.")
    catalog, contrast, _ = setup()
    frozen = manifest(dict(config=asdict(CONFIG), arms=["joint", "round_robin", "conditional"],
                           cap=400, seconds=1200, dispatches=12, per_component_nodes=[256, 512],
                           noise=.01, noise_seed=4701, frequencies_hz=FREQUENCIES))
    frozen["source_sha256"][str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    write(HERE / "strategy_manifest.json", frozen)
    work = Work(max_forwards=32, max_seconds=1200)
    for sep in (.14, .20):
        truth, initial = scene(sep), scene(sep, initial=True)
        data = np.column_stack([solve(truth, o.wavenumber, contrast, o.acquisition, 512, work=work).prediction
                                for o in catalog])
        rng = np.random.default_rng(4701)
        noise = rng.normal(size=data.shape) + 1j * rng.normal(size=data.shape)
        noise *= .01 * np.linalg.norm(data, axis=0) / np.linalg.norm(noise, axis=0)
        folder = HERE / "inputs" / f"separation_{sep:.2f}"
        write(folder / "input.json", dict(truth=record_scene(truth), initial=record_scene(initial),
              clean_real=data.real, clean_imag=data.imag, noise_real=noise.real, noise_imag=noise.imag))
    write(HERE / "input_work.json", work.summary())
    frozen["input_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((HERE / "inputs").rglob("*.json"))}
    write(HERE / "strategy_manifest.json", frozen)
    verify(frozen)


def run():
    prepare()
    frozen = json.loads((HERE / "strategy_manifest.json").read_text())
    verify(frozen)
    for name, digest in frozen["input_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Frozen strategy input changed: " + name)
    catalog, contrast, _ = setup()
    summaries = []
    for sep in (.14, .20):
        inputs = json.loads((HERE / "inputs" / f"separation_{sep:.2f}" / "input.json").read_text())
        initial = load_scene(inputs["initial"])
        for noisy in (False, True):
            data = np.array(inputs["clean_real"]) + 1j * np.array(inputs["clean_imag"])
            if noisy:
                data += np.array(inputs["noise_real"]) + 1j * np.array(inputs["noise_imag"])
            observations = tuple(Observation(o.wavenumber, o.acquisition, data[:, j]) for j, o in enumerate(catalog))
            case = f"sep{sep:.2f}_{'noise' if noisy else 'clean'}"
            for arm in ("joint", "round_robin", "conditional"):
                folder = HERE / "runs" / case / arm
                if (folder / "result.json").exists():
                    row = json.loads((folder / "result.json").read_text())
                else:
                    endpoint, row = fit(initial, observations, contrast, arm, folder)
                    # The sole truth access after the optimizer returns.
                    truth = load_scene(inputs["truth"])
                    row.update(case=case, initial_score=score(initial, truth), score=score(endpoint, truth))
                    write(folder / "result.json", row)
                summary = {k: row[k] for k in ("case", "arm", "outcome", "audit", "score", "work")}
                summaries.append(summary)
                write(HERE / "strategy_summary.json", summaries)
                print(json.dumps(dict(case=case, arm=arm, outcome=row["outcome"],
                    rms_mm=row["score"]["worst_rms_mm"], work=row["work"], passed=row["audit"]["passed"])), flush=True)
                verify(frozen)


if __name__ == "__main__":
    run()
