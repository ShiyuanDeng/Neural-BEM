"""SC-020: the clean hybrid against the SPD default on SPD's single-object case.

The SPD reference is the default continuation (compiled runtime, which
routes one component to full Kress with reciprocal derivatives) rerun from
the saved TOP-025 merge handoff. The hybrid receives the same observations,
the same handoff boundary and an SPD-matching cumulative policy; it differs
in its update (Borges normal move + arclength refit), its derivative
coordinates and its physics implementation (package nodal Müller).

Only this harness imports SPD code. Both arms are scored by SPD's own endpoint
scorer (`experiments.top020.run.score_predictions`) with SPD's Kress predictor,
so the evaluator is independent of the hybrid backend.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

from .forward import PointSourceAcquisition
from .geometry import FourierCurve
from .inverse import Observation
from .lm_backend import (BackendConfig, FitStage, FixedSchedule, Ledger, NumericalFailure,
                         run_policy, stage_record)
from .run import provenance
from .updates import BorgesUpdate

ROOT = Path(__file__).resolve().parents[2]
SPD_BUNDLE = ROOT / "results/validation/topology/TOP-025-compiled-20260917-115641"
SCENE = "merge"
LENGTH = 0.05
CENTER = 0.5 + 0.5j
ARMS = ("spd", "hybrid")
# Declared mapping of SPD's 33 gauge-fixed directions (translation, radius and
# radial modes 2..16 of K17) onto normal harmonics 0..16 of h. Storage K is a
# numerical-representation choice: the arclength refit of the handoff and of
# the true ellipse needs K>=64 at the unchanged 1e-7 projection tolerance.
UPDATE_MODES = 16
CURVE_MODES = 96


def write(path, value):
    def portable(item):
        if isinstance(item, np.ndarray): return portable(item.tolist())
        if isinstance(item, np.generic): return portable(item.item())
        if isinstance(item, dict): return {str(k): portable(v) for k, v in item.items()}
        if isinstance(item, (tuple, list)): return [portable(v) for v in item]
        if isinstance(item, float) and not np.isfinite(item): return None
        return item
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False) + "\n")


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spd_modules():
    """Import the SPD stack lazily; the hybrid core never imports it."""
    sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]
    from experiments.top025 import run as top025
    from experiments.top020 import run as top020
    return top025, top020


def source_hashes():
    paths = [*ROOT.glob("run_*.py"), *ROOT.glob("config/*.py"), *ROOT.glob("solvers/**/*.py"),
             *ROOT.glob("experiments/top0*/*.py"), *Path(__file__).parent.glob("*.py")]
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


# --- coordinate bridge -----------------------------------------------------

def from_cartesian(component):
    cos = component.cosine_coefficients[:, 0] + 1j * component.cosine_coefficients[:, 1]
    sin = component.sine_coefficients[:, 0] + 1j * component.sine_coefficients[:, 1]
    band = len(cos) - 1
    c = np.zeros(2 * band + 1, complex)
    c[band] = cos[0]
    c[band + 1:] = (cos[1:] - 1j * sin[1:]) / 2
    c[:band] = ((cos[1:] + 1j * sin[1:]) / 2)[::-1]
    c /= LENGTH
    c[band] -= CENTER / LENGTH
    return FourierCurve(c)


def to_cartesian(curve, component_id):
    from sdf_inverse.explicit_fourier import CartesianFourierCurveState
    band = curve.band
    c = curve.coefficients * LENGTH
    c[band] += CENTER
    positive, negative = c[band + 1:], c[:band][::-1]
    C = np.r_[c[band], positive + negative]
    S = np.r_[0, 1j * (positive - negative)]
    return CartesianFourierCurveState(np.column_stack((C.real, C.imag)),
                                      np.column_stack((S.real, S.imag)), component_id)


def package_observations(frequencies_hz, values, cfg, base):
    sources, receivers = base._ring_scan()
    origin = np.array([CENTER.real, CENTER.imag])
    acquisition = PointSourceAcquisition((sources - origin) / LENGTH, (receivers - origin) / LENGTH,
                                         base.SOURCE_STRENGTH)
    waves = [2 * np.pi * f * np.sqrt(cfg.MU0 * cfg.EPS0 * cfg.SAND_EPSR) * LENGTH for f in frequencies_hz]
    return tuple(Observation(k, acquisition, values[:, j]) for j, k in enumerate(waves))


# --- inputs ----------------------------------------------------------------

def load(bundle_inputs=SPD_BUNDLE):
    top025, top020 = spd_modules()
    suite, m, p = top025.suite, top025.m, top025.p
    initial, observed, evaluation, scene, spec = suite.load_scene(bundle_inputs, SCENE)
    handoff = read(SPD_BUNDLE / "runs" / SCENE / "handoff.json")
    state = p.driver.deserialize_state(handoff["state"])
    if m.state_hash(state) != handoff["state_sha256"]:
        raise RuntimeError("SPD handoff hash changed.")
    control = p.benchmark.controller_config(spec, "H")
    solve = p.driver.baseline.iteration01_solve_config()
    optimizer = replace(p._optimizer_config(state, control), loss_tolerance=1e-14)
    recorded = handoff["optimizer"]
    rebuilt = json.loads(json.dumps(asdict(optimizer), default=lambda x: x.tolist()))
    if rebuilt != recorded:
        raise RuntimeError("Rebuilt SPD optimizer differs from the recorded handoff optimizer.")
    return dict(top025=top025, top020=top020, state=state, observed=observed, evaluation=evaluation,
                scene=scene, spec=spec, control=control, solve=solve, optimizer=optimizer, handoff=handoff)


def spd_matching_policy(observations, optimizer, top025):
    """Stage n fits the first n training frequencies with equal weights."""
    follow = top025.follow
    train = list(top025.p.TRAIN)
    stages = []
    for number, quota in follow.FULL_PLAN:
        active = train[:number]
        stages.append(FitStage(
            label=f"stage_{number}", observations=observations[:number],
            weights=tuple(np.ones(number) / number),
            discrepancy_tolerances=tuple(float(t) for t in np.where(np.array(active) > .5e9 + 1., 1e-7, 1e-5)),
            update_modes=UPDATE_MODES, curve_modes=CURVE_MODES, nodes=top025.NODES[0],
            refined_nodes=top025.NODES[1], iterations=optimizer.max_iterations, quota=quota))
    return FixedSchedule(stages, "SPD-matching cumulative schedule")


def backend_config(optimizer, geometry_bounds):
    (x0, y0), (x1, y1) = geometry_bounds
    box = (((x0 - CENTER.real) / LENGTH, (y0 - CENTER.imag) / LENGTH),
           ((x1 - CENTER.real) / LENGTH, (y1 - CENTER.imag) / LENGTH))
    return BackendConfig(
        initial_damping=optimizer.initial_damping, damping_increase=optimizer.damping_increase,
        damping_decrease=optimizer.damping_decrease, max_damping_trials=optimizer.max_damping_trials,
        max_backtracks=optimizer.max_backtracks, gradient_tolerance=optimizer.gradient_tolerance,
        loss_tolerance=optimizer.loss_tolerance, relative_step_tolerance=optimizer.relative_step_tolerance,
        step_bounds_m=(0.012, 0.018, 0.006), domain_box=box)


# --- arms ------------------------------------------------------------------

def run_spd(inputs, directory):
    top025 = inputs["top025"]
    started = time.perf_counter()
    result = top025.run_scheduled_continuation(directory / "F", inputs["state"], inputs["optimizer"],
        inputs["observed"], inputs["evaluation"], inputs["scene"], inputs["spec"], inputs["control"],
        inputs["solve"])
    return dict(status=result["status"], fresh_recovery_pass=result["fresh_recovery_pass"],
                elapsed_seconds=time.perf_counter() - started, work=result["work"],
                final_state_sha256=result.get("schedule", {}).get("final_state_sha256"),
                final=result.get("schedule", {}).get("final"))


def score_state(state, inputs, ledger=None):
    """SPD endpoint scorer on an SPD state; charges 12 units when given a ledger."""
    top020, top025 = inputs["top020"], inputs["top025"]
    p = top025.p
    import sdf_bem_multicomponent.forward as physical
    frequencies = top025.follow.FREQUENCIES
    predictions = {}
    for nodes in top025.NODES:
        if ledger is not None:
            with ledger.endpoint_scope():
                ledger.reserve(len(frequencies))
                for _ in frequencies:
                    ledger.charge("solve", "endpoint")
        predictions[nodes] = physical.predict_multicomponent_kress_paired_boundary_response(
            state.boundary(p.driver.baseline._geometry_config(nodes)),
            p.driver.baseline._problem(np.asarray(frequencies)), solve_config=inputs["solve"]).scattered_response
    score = top020.score_predictions(state, inputs["scene"], inputs["spec"], inputs["observed"],
                                     inputs["evaluation"], predictions)
    admissible = {str(n): bool(top025.p.feasible(state, (n,), inputs["solve"], 0.0)) for n in top025.NODES}
    return dict(score, spd_admissible_without_radius_floor=admissible)


def hybrid_state(curve):
    from sdf_inverse.radial_topology import MultiRadialFourierState
    return MultiRadialFourierState((to_cartesian(curve, "hybrid.merge"),))


def run_hybrid(inputs, directory):
    top025 = inputs["top025"]
    import config.two_circle_config as cfg
    import run_radial_fourier_topology_inverse as base
    frequencies = list(top025.p.TRAIN)
    observations = package_observations(frequencies, inputs["observed"], cfg, base)
    contrast = cfg.PLASTIC_EPSR / cfg.SAND_EPSR
    policy = spd_matching_policy(observations, inputs["optimizer"], top025)
    config = backend_config(inputs["optimizer"], top025.p.driver.baseline._geometry_config(256).bounds)
    update = BorgesUpdate(LENGTH)
    ledger = Ledger(cap=8012, seconds=7200.0)
    initial = from_cartesian(inputs["state"].components[0])
    write(directory / "configuration.json", dict(update=update.settings(), backend=asdict(config),
        policy=policy.name, stages=[stage_record(s) for s in policy.stages], contrast=contrast,
        length_unit_m=LENGTH, origin_m=[CENTER.real, CENTER.imag], training_frequencies_hz=frequencies,
        ledger=dict(cap=ledger.cap, seconds=ledger.seconds, endpoint_reserve=ledger.endpoint_reserve)))
    scores = []

    def endpoint(stage, result):
        score = score_state(hybrid_state(result.curve), inputs, ledger)
        scores.append(dict(stage=stage.label, score=score))
        write(directory / f"{stage.label}_endpoint.json", scores[-1])
        if not score["numerically_qualified"]:
            raise NumericalFailure("retained endpoint numerical qualification failed")

    trajectory = (directory / "trajectory.jsonl").open("w")

    def accepted(stage, iteration, evaluation):
        trajectory.write(json.dumps(dict(stage=stage.label, iteration=iteration, loss=evaluation.loss,
            relative_l2=evaluation.relative_l2, work=ledger.snapshot(),
            coefficients=dict(real=evaluation.curve.coefficients.real.tolist(),
                              imag=evaluation.curve.coefficients.imag.tolist()))) + "\n")
        trajectory.flush()

    started = time.perf_counter()
    initial_score = score_state(hybrid_state(update.regauge(initial, CURVE_MODES)[0]), inputs, ledger)
    result = run_policy(initial, policy, contrast, update, config, ledger, on_stage=endpoint, on_accept=accepted)
    elapsed = time.perf_counter() - started
    trajectory.close()
    stages = []
    for record in result.stages:
        row = {k: v for k, v in asdict(record).items() if k not in ("curve", "history", "trials", "acceptance_checks")}
        row["trial_status"] = {}
        for trial in record.trials:
            key = trial.get("status", "unknown") + (":" + trial["reason"] if "reason" in trial else "")
            row["trial_status"][key] = row["trial_status"].get(key, 0) + 1
        stages.append(row)
        write(directory / f"{record.stage_label}_history.json", dict(history=record.history, trials=record.trials,
              acceptance_checks=record.acceptance_checks))
    final = scores[-1]["score"] if scores and result.status == "COMPLETED_SCHEDULE" else None
    passed = bool(result.status == "COMPLETED_SCHEDULE" and final is not None and final["original_gates_pass"]
                  and final["numerically_qualified"] and all(s["score"]["numerically_qualified"] for s in scores))
    return dict(status=result.status, reason=result.reason, detail=result.detail, fresh_recovery_pass=passed,
                elapsed_seconds=elapsed, work=ledger.snapshot(), initial_regauge_error=result.regauge_error,
                initial_score=initial_score, stage_scores=scores, stages=stages, final=final,
                final_curve=dict(real=result.curve.coefficients.real.tolist(),
                                 imag=result.curve.coefficients.imag.tolist()))


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = load()
    names = {"inputs/merge/training_observations.json": "training_observations.json",
             "inputs/merge/observations.json": "observations.json",
             "inputs/merge/initial_state.json": "original_initial_state.json",
             "runs/merge/handoff.json": "handoff.json",
             "runs/merge/F/metrics.json": "spd_top025_continuation_metrics.json",
             "scene_spec.json": "scene_spec.json"}
    (output / "inputs").mkdir()
    copied = {}
    for name, local in names.items():
        target = output / "inputs" / local
        shutil.copyfile(SPD_BUNDLE / name, target)
        copied[str(target.relative_to(output))] = dict(source=str((SPD_BUNDLE / name).relative_to(ROOT)),
                                                       sha256=digest(target))
    from sdf_inverse.runtime import runtime_metadata
    manifest = dict(experiment="SC-020", scene=SCENE, arms=list(ARMS), provenance=provenance(),
        source_sha256=source_hashes(), inputs=copied, spd_runtime=runtime_metadata(),
        mapping=dict(update_modes=UPDATE_MODES, curve_modes=CURVE_MODES,
                     spd_reduced_directions=len(inputs["state"].gauge_tangent_basis()),
                     hybrid_directions=2 * UPDATE_MODES + 1,
                     step_bounds_m=dict(order0=0.012, order1=0.018, order_ge2=0.006)),
        gates="SPD original gates at the final stage plus numerical qualification of every stage endpoint")
    write(output / "manifest.json", manifest)
    print(json.dumps(dict(prepared=str(output))), flush=True)


def run_one(output, arm):
    manifest = read(output / "manifest.json")
    if source_hashes() != manifest["source_sha256"]:
        raise RuntimeError("Numerical sources changed after preparation; use a fresh bundle.")
    for name, record in manifest["inputs"].items():
        if digest(output / name) != record["sha256"] or digest(ROOT / record["source"]) != record["sha256"]:
            raise RuntimeError(f"Input changed: {name}")
    directory = output / "runs" / arm
    directory.mkdir(parents=True, exist_ok=False)
    inputs = load()
    record = run_spd(inputs, directory) if arm == "spd" else run_hybrid(inputs, directory)
    record.update(arm=arm)
    write(directory / "result.json", record)
    print(json.dumps({k: record.get(k) for k in ("arm", "status", "fresh_recovery_pass", "elapsed_seconds")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--one", choices=ARMS)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.output)
    if args.one:
        run_one(args.output, args.one)


if __name__ == "__main__":
    main()
