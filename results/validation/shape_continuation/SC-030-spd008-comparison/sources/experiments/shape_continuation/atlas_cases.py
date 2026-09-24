"""SC-022: fixed-schedule trajectories and the dense atlas on three single-object cases.

Cases (user-chosen): wrong circle, circle to five-lobe star, circle to a
non-star C shape. Acquisition, materials, training frequencies, LM settings
and stage quotas are SPD's (via `spd_cases`). Observations cover a dense
catalog; the fixed schedule sees only its four training frequencies, the
atlas uses all of them. Truth enters observation generation and the
evaluation-only true-error layer, never the trajectory or the step layers.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from . import spd_cases as sc
from .atlas_survey import cell, gn_step, lm_step, true_error
from .forward import PointSourceAcquisition, solve
from .geometry import FourierCurve
from .inverse import Observation
from .lm_backend import FitStage, FixedSchedule, Ledger, run_policy, stage_record
from .metrics import area_error, boundary_distance
from .run import provenance
from .updates import BorgesUpdate

CASES = ("wrong_circle", "circle_to_star", "circle_to_c")
CATALOG_HZ = tuple(float(f) for f in np.round(np.arange(0.25e9, 2.5e9 + 1, 0.125e9)))
UPDATE_MODES, CURVE_MODES, NODES, REFINED, ATLAS_BAND = 32, 192, 512, 1024, 48
START = dict(center=(0.48, 0.52), radius=0.065)  # legacy default initial circle
C_SHAPE = dict(centreline_m=0.040, half_thickness_m=0.018, half_angle_deg=110.0, rotation=0.3, band=10)
# Update-band rules for the trajectory generator. `fixed32` is SC-021's mapping;
# `borges` is the manuscript's §4 rule M = floor(3 max(k, ki)) in the package's
# dimensionless units (length 5 cm), evaluated at each stage's highest frequency.
BAND_RULES = dict(fixed32=lambda k, ki: UPDATE_MODES, borges=lambda k, ki: int(np.floor(3 * max(k, ki))))


def write(path, value):
    sc.write(Path(path), value)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def c_shape_curve():
    """Thick arc with semicircular caps, sampled by arclength, smoothed to its natural band."""
    R, w = C_SHAPE["centreline_m"], C_SHAPE["half_thickness_m"]
    alpha = np.radians(C_SHAPE["half_angle_deg"])
    cap = np.linspace(0, np.pi, 600)
    pieces = [(R + w) * np.exp(1j * np.linspace(-alpha, alpha, 2000)),
              R * np.exp(1j * alpha) + w * np.exp(1j * (alpha + cap)),
              (R - w) * np.exp(1j * np.linspace(alpha, -alpha, 2000)),
              R * np.exp(-1j * alpha) + w * np.exp(1j * (-alpha + np.pi + cap))]
    p = np.concatenate(pieces)
    segment = np.abs(np.diff(np.r_[p, p[0]]))
    s = np.r_[0, np.cumsum(segment)]
    u = np.linspace(0, s[-1], 8192, endpoint=False)
    q = np.interp(u, s, np.r_[p.real, p[0].real]) + 1j * np.interp(u, s, np.r_[p.imag, p[0].imag])
    return FourierCurve.from_samples(q * np.exp(1j * C_SHAPE["rotation"]) / sc.LENGTH, C_SHAPE["band"])


def truth_curve(case):
    """Package units (length 5 cm about the scene centre)."""
    if case == "wrong_circle":
        return FourierCurve.circle(0.05 / sc.LENGTH)
    if case == "circle_to_star":
        t = 2 * np.pi * np.arange(8192) / 8192
        return FourierCurve.from_samples(0.05 * (1 + 0.25 * np.cos(5 * t)) * np.exp(1j * t) / sc.LENGTH, 6)
    if case == "circle_to_c":
        return c_shape_curve()
    raise ValueError(case)


def start_curve():
    center = complex(*START["center"]) - sc.CENTER
    return FourierCurve.circle(START["radius"] / sc.LENGTH, center / sc.LENGTH)


def spd():
    """SPD modules and settings; imported lazily (observation oracle and constants)."""
    top025, _ = sc.spd_modules()
    import config.two_circle_config as cfg
    import run_radial_fourier_topology_inverse as base
    return top025, cfg, base


def kress_predictions(curve, frequencies, nodes):
    top025, cfg, base = spd()
    import sdf_bem_multicomponent.forward as physical
    from sdf_inverse.radial_topology import MultiRadialFourierState
    state = MultiRadialFourierState((sc.to_cartesian(curve, "truth"),))
    return physical.predict_multicomponent_kress_paired_boundary_response(
        state.boundary(top025.p.driver.baseline._geometry_config(nodes)),
        base._problem(np.asarray(frequencies)),
        solve_config=top025.p.driver.baseline.iteration01_solve_config()).scattered_response


def relative(a, b):
    return np.linalg.norm(a - b, axis=0) / np.linalg.norm(b, axis=0)


def observations(values, frequencies=CATALOG_HZ):
    _, cfg, base = spd()
    return sc.package_observations(list(frequencies), np.asarray(values), cfg, base)


def contrast():
    _, cfg, _ = spd()
    return cfg.PLASTIC_EPSR / cfg.SAND_EPSR


def prepare(output):
    (output / "inputs").mkdir(parents=True, exist_ok=False)
    top025, cfg, base = spd()
    freqs = np.asarray(CATALOG_HZ)
    for case in CASES:
        truth = truth_curve(case)
        folder = output / "inputs" / case
        folder.mkdir(parents=True)
        check = {}
        if case == "wrong_circle":
            values = base._oracle_response(np.array([[0.5, 0.5]]), np.array([0.05]), freqs,
                                           component_ids=("truth",))
            check.update(oracle="analytic multi-cylinder series",
                         cross_kress_1024_vs_oracle=relative(kress_predictions(truth, freqs, 1024), values).tolist())
        else:
            values = kress_predictions(truth, freqs, 1024)
            check.update(oracle="SPD nodal Kress, 1024 nodes",
                         refinement_kress_2048_vs_1024=relative(kress_predictions(truth, freqs, 2048), values).tolist())
        obs = observations(values)
        muller = np.column_stack([solve(truth, o.wavenumber, contrast(), o.acquisition, 1024).prediction
                                  for o in obs])
        check["cross_package_muller_1024_vs_oracle"] = relative(muller, values).tolist()
        limits = dict(refinement=1e-9, cross=1e-8)
        worst = {kind: max([max(v) for k, v in check.items() if k.startswith(kind)], default=0.0) for kind in limits}
        check.update(limits=limits, passed=bool(all(worst[k] <= limits[k] for k in limits)))
        write(folder / "observations.json", dict(frequencies_hz=list(CATALOG_HZ),
              observed_real=values.real, observed_imag=values.imag))
        write(folder / "truth.json", dict(case=case, real=truth.coefficients.real, imag=truth.coefficients.imag,
              definition=C_SHAPE if case == "circle_to_c" else None))
        write(folder / "oracle_check.json", check)
        print(json.dumps(dict(case=case, oracle_passed=check["passed"], worst=worst)), flush=True)
        if not check["passed"]:
            raise RuntimeError(f"{case}: oracle checks failed ({worst}).")
    write(output / "manifest.json", dict(experiment="SC-022", cases=list(CASES), catalog_hz=list(CATALOG_HZ),
        training_hz=list(top025.p.TRAIN), start=START, c_shape=C_SHAPE, update_modes=UPDATE_MODES,
        curve_modes=CURVE_MODES, nodes=NODES, refined_nodes=REFINED, atlas_band=ATLAS_BAND,
        length_unit_m=sc.LENGTH, origin_m=[sc.CENTER.real, sc.CENTER.imag], provenance=provenance(),
        source_sha256=sc.source_hashes(),
        inputs={str(p.relative_to(output)): digest(p) for p in sorted((output / "inputs").rglob("*.json"))}))


def load_case(output, case):
    data = sc.read(output / "inputs" / case / "observations.json")
    values = np.array(data["observed_real"]) + 1j * np.array(data["observed_imag"])
    truth = sc.read(output / "inputs" / case / "truth.json")
    return observations(values), FourierCurve(np.array(truth["real"]) + 1j * np.array(truth["imag"]))


def policy(catalog, arm="fixed32"):
    """SPD-matching cumulative schedule; only the update band M follows `arm`."""
    top025, _, _ = spd()
    optimizer = sc.load()["optimizer"]
    train = list(top025.p.TRAIN)
    index = {f: i for i, f in enumerate(CATALOG_HZ)}
    stages = []
    for number, quota in top025.follow.FULL_PLAN:
        active = train[:number]
        k = max(catalog[index[f]].wavenumber for f in active)
        modes = BAND_RULES[arm](k, k * np.sqrt(contrast()))
        stages.append(FitStage(f"stage_{number}", tuple(catalog[index[f]] for f in active),
            tuple(np.ones(number) / number),
            tuple(float(t) for t in np.where(np.array(active) > .5e9 + 1., 1e-7, 1e-5)),
            modes, CURVE_MODES, NODES, REFINED, optimizer.max_iterations, quota))
    config = sc.backend_config(optimizer, top025.p.driver.baseline._geometry_config(256).bounds)
    return FixedSchedule(stages, f"SPD-matching cumulative schedule, band rule {arm}"), config


def verify_sources(output):
    manifest = sc.read(output / "manifest.json")
    expected = manifest["amendments"][-1]["source_sha256"] if manifest.get("amendments") else manifest["source_sha256"]
    if sc.source_hashes() != expected:
        raise RuntimeError("Numerical sources changed after preparation.")
    for name, value in manifest["inputs"].items():
        if digest(output / name) != value:
            raise RuntimeError(f"Input changed: {name}")


def amend(output, reason):
    """Record a source change after preparation; earlier runs keep their verified hashes."""
    manifest = sc.read(output / "manifest.json")
    previous = manifest["amendments"][-1]["source_sha256"] if manifest.get("amendments") else manifest["source_sha256"]
    current = sc.source_hashes()
    changed = sorted(k for k in set(previous) | set(current) if previous.get(k) != current.get(k))
    manifest.setdefault("amendments", []).append(dict(reason=reason, changed=changed, source_sha256=current,
        recorded=time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    write(output / "manifest.json", manifest)
    print(json.dumps(dict(amended=changed)), flush=True)


def run_trajectory(output, case, arm="fixed32"):
    verify_sources(output)
    catalog, truth = load_case(output, case)
    schedule, config = policy(catalog, arm)
    update = BorgesUpdate(sc.LENGTH)
    ledger = Ledger(cap=8012, seconds=7200.0)
    folder = output / "runs" / arm / case
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / "configuration.json", dict(arm=arm, update=update.settings(), backend=asdict(config),
          policy=schedule.name, stages=[stage_record(s) for s in schedule.stages]))
    scores = []

    def geometry(curve):
        error, bound = boundary_distance(truth, curve)
        return dict(hausdorff_m=error * sc.LENGTH, hausdorff_upper_m=(error + bound) * sc.LENGTH,
                    area=area_error(truth, curve))

    def endpoint(stage, result):
        scores.append(dict(stage=stage.label, geometry=geometry(result.curve), outcome=result.outcome,
                           stop=result.stop_reason, accepted=result.accepted_steps, loss=result.final_loss))
        write(folder / "stage_scores.json", scores)

    started = time.perf_counter()
    result = run_policy(start_curve(), schedule, contrast(), update, config, ledger, on_stage=endpoint)
    for record in result.stages:
        write(folder / f"{record.stage_label}_history.json", dict(history=record.history, trials=record.trials,
              acceptance_checks=record.acceptance_checks))
    summary = dict(case=case, arm=arm, status=result.status, reason=result.reason, detail=result.detail,
                   elapsed_seconds=time.perf_counter() - started, work=ledger.snapshot(),
                   initial_geometry=geometry(start_curve()), final_geometry=geometry(result.curve),
                   stages=[{k: v for k, v in asdict(r).items() if k not in ("curve", "history", "trials",
                            "acceptance_checks")} for r in result.stages], stage_scores=scores)
    write(folder / "result.json", summary)
    print(json.dumps({k: summary[k] for k in ("case", "status", "elapsed_seconds", "final_geometry")}), flush=True)


# --- atlas -------------------------------------------------------------------

_WORKER = {}


def _init(output, case):
    catalog, _ = load_case(output, case)
    _WORKER.update(catalog=catalog, contrast=contrast())


def _cells(coefficients):
    curve = FourierCurve(np.asarray(coefficients))
    rows = []
    for observation in _WORKER["catalog"]:
        c = cell(curve, observation, _WORKER["contrast"], NODES, ATLAS_BAND, sc.LENGTH)
        rows.append((c.loss, c.relative_residual, c.system_residual, c.gradient, c.gauss_newton))
    return rows


def atlas_states(folder):
    states = []
    for number in (1, 2, 3, 4):
        path = folder / f"stage_{number}_history.json"
        if not path.exists():
            break
        for row in sc.read(path)["history"]:
            states.append(dict(stage=number, iteration=row["iteration"], loss=row["loss"],
                               next_damping=row["next_damping"], step_m=row["step_m"],
                               coefficients=np.array(row["coefficients"]["real"]) + 1j * np.array(row["coefficients"]["imag"])))
    return states


def run_atlas(output, case, workers, arm="fixed32"):
    verify_sources(output)
    folder = output / "runs" / arm / case
    states = atlas_states(folder)
    keys = [s["coefficients"].tobytes() for s in states]
    unique = list(dict.fromkeys(keys))
    started = time.perf_counter()
    with ProcessPoolExecutor(workers, initializer=_init, initargs=(output, case)) as pool:
        computed = dict(zip(unique, pool.map(_cells, [states[keys.index(k)]["coefficients"] for k in unique])))
    catalog, truth = load_case(output, case)
    top025, _, _ = spd()
    train = list(top025.p.TRAIN)
    index = {f: i for i, f in enumerate(CATALOG_HZ)}
    dim = 2 * ATLAS_BAND + 1
    S, F = len(states), len(CATALOG_HZ)
    arrays = {name: np.zeros(shape) for name, shape in dict(
        loss=(S, F), relative_residual=(S, F), system_residual=(S, F), gradient=(S, F, dim),
        gauss_newton=(S, F, dim, dim), eigenvalues=(S, F, dim), lm_step=(S, F, dim), gn_step=(S, F, dim),
        gn_predicted_decrease=(S, F), stage_lm_step=(S, dim), stage_gn_step=(S, dim)).items()}
    truth_arrays = dict(coefficients=np.zeros((S, dim)), rms_m=np.zeros(S), beyond_band_rms_m=np.zeros(S),
                        maximum_m=np.zeros(S))
    truth_points = truth.values(16384)
    for i, (state, key) in enumerate(zip(states, keys)):
        for j, (loss, rel, sysres, gradient, gram) in enumerate(computed[key]):
            arrays["loss"][i, j], arrays["relative_residual"][i, j], arrays["system_residual"][i, j] = loss, rel, sysres
            arrays["gradient"][i, j], arrays["gauss_newton"][i, j] = gradient, gram
            arrays["eigenvalues"][i, j] = np.sort(np.clip(np.linalg.eigvalsh(gram), 0, None))[::-1]
            arrays["lm_step"][i, j] = lm_step(gram, gradient, state["next_damping"])
            arrays["gn_step"][i, j], arrays["gn_predicted_decrease"][i, j] = gn_step(gram, gradient)
        active = [index[f] for f in train[:state["stage"]]]
        weights = np.ones(len(active)) / len(active)
        gram = sum(w * arrays["gauss_newton"][i, j] for j, w in zip(active, weights))
        gradient = sum(w * arrays["gradient"][i, j] for j, w in zip(active, weights))
        arrays["stage_lm_step"][i] = lm_step(gram, gradient, state["next_damping"])
        arrays["stage_gn_step"][i] = gn_step(gram, gradient)[0]
        coefficients, summary = true_error(FourierCurve(state["coefficients"]), truth_points, ATLAS_BAND, sc.LENGTH)
        truth_arrays["coefficients"][i] = coefficients
        for name in ("rms_m", "beyond_band_rms_m", "maximum_m"):
            truth_arrays[name][i] = summary[name]
    meta = dict(stage=np.array([s["stage"] for s in states]), iteration=np.array([s["iteration"] for s in states]),
                trajectory_loss=np.array([s["loss"] for s in states]),
                next_damping=np.array([s["next_damping"] for s in states]),
                frequencies_hz=np.array(CATALOG_HZ), atlas_band=ATLAS_BAND, nodes=NODES)
    np.savez_compressed(folder / "atlas.npz", **arrays, **meta)
    np.savez_compressed(folder / "true_error_EVALUATION_ONLY.npz", **truth_arrays, **meta)
    summary = dict(case=case, arm=arm, states=S, unique_curves=len(unique), cells=len(unique) * F,
                   seconds=time.perf_counter() - started, workers=workers,
                   atlas_sha256=digest(folder / "atlas.npz"),
                   true_error_sha256=digest(folder / "true_error_EVALUATION_ONLY.npz"),
                   max_system_residual=float(arrays["system_residual"].max()),
                   convention=("backend coordinates: a0, a1..aP, b1..bP (m) of normal distance in normalized "
                               "arclength; per-frequency SPD normalization with weight 1; lm_step at the "
                               "state's live damping, before clipping; gn_step truncated at 1e-10"))
    write(folder / "atlas_summary.json", summary)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--trajectory", choices=CASES)
    parser.add_argument("--atlas", choices=CASES)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--arm", choices=tuple(BAND_RULES), default="fixed32")
    parser.add_argument("--amend", help="Record a post-preparation source change and its reason.")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.output)
    if args.amend:
        amend(args.output, args.amend)
    if args.trajectory:
        run_trajectory(args.output, args.trajectory, args.arm)
    if args.atlas:
        run_atlas(args.output, args.atlas, args.workers, args.arm)


if __name__ == "__main__":
    main()
