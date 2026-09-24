"""SC-026: one consolidated atlas dataset over every recorded trajectory state.

Sources: the accepted states of SC-022 (6 runs), SC-024 (19 runs) and SC-025
(24 runs), deduplicated per case by curve. For each unique state and each of
the 19 catalog frequencies (0.25-2.5 GHz) it stores the normalized residual
Jacobian J (48 real measurement rows x 97 normal-harmonic coordinates, P=48,
backend coordinates and units) and the residual r, so the Gauss-Newton block
is J^T J and the gradient J^T r exactly. Evaluation-only layers (normal-ray
error, the closest-distance proxy, distances and curvature) go in separate
files and must never be read by fitting, step or policy code.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from . import atlas_cases as ac
from . import spd_cases as sc
from .atlas_survey import normal_ray_error, symmetric_rms_distance, true_error
from .forward import shape_jacobian, solve
from .geometry import FourierCurve, _refit_samples, grid_size, normal_basis
from .lm_backend import normalize
from .metrics import boundary_distance
from .updates import speed_ratio

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "results/validation/shape_continuation"
SOURCES = dict(SC022="SC-022-atlas-survey/runs/*/*", SC024="SC-024-backend-ablations/runs/*/*/*",
               SC025="SC-025-band-policies/runs/*/*")
INPUTS = dict(wrong_circle="SC-022-atlas-survey", circle_to_star="SC-022-atlas-survey",
              circle_to_c="SC-022-atlas-survey", kite="SC-025-band-policies", peanut="SC-025-band-policies",
              hook="SC-025-band-policies")
P, NODES = ac.ATLAS_BAND, ac.NODES


def curve_key(coefficients):
    return hashlib.sha1(np.ascontiguousarray(coefficients, complex).tobytes()).hexdigest()[:16]


def collect():
    """Every accepted state record, grouped by unique (case, curve)."""
    states = {}
    for source, pattern in SOURCES.items():
        for folder in sorted(BASE.glob(pattern)):
            case = folder.name
            run = str(folder.relative_to(BASE))
            config = sc.read(folder / "configuration.json")
            result = sc.read(folder / "result.json")
            bands = {d["stage"]: d["band"] for d in result.get("decisions", [])}
            for stage in config.get("stages", config.get("template_stages", [])):
                bands.setdefault(stage["label"], stage["update_modes"])
            for number in (1, 2, 3, 4):
                path = folder / f"stage_{number}_history.json"
                if not path.exists():
                    continue
                for row in sc.read(path)["history"]:
                    c = np.array(row["coefficients"]["real"]) + 1j * np.array(row["coefficients"]["imag"])
                    key = (case, curve_key(c))
                    entry = states.setdefault(key, dict(case=case, key=key[1], coefficients=c, occurrences=[]))
                    entry["occurrences"].append(dict(source=source, run=run, stage=number, iteration=row["iteration"],
                                                     band=bands.get(f"stage_{number}"), loss=row["loss"],
                                                     damping=row["damping"], next_damping=row.get("next_damping")))
    return states


_W = {}


def _init():
    _W["catalogs"], _W["truths"] = {}, {}
    for case, bundle in INPUTS.items():
        catalog, truth = ac.load_case(BASE / bundle, case)
        _W["catalogs"][case], _W["truths"][case] = catalog, truth
    _W["contrast"] = ac.contrast()


def compute(job):
    """All 19 frequencies and the evaluation layers at one unique state; written to `work/`."""
    case, key, coefficients, work = job
    target = Path(work) / f"{case}__{key}.npz"
    if target.exists():
        return str(target)
    curve = FourierCurve(coefficients)
    catalog, truth = _W["catalogs"][case], _W["truths"][case]
    F, rows = len(catalog), 2 * len(catalog[0].scattered)  # real then imaginary parts of the paired responses
    J = np.zeros((F, rows, 2 * P + 1))
    r = np.zeros((F, rows))
    loss, relative, system = np.zeros(F), np.zeros(F), np.zeros(F)
    for j, observation in enumerate(catalog):
        state = solve(curve, observation.wavenumber, _W["contrast"], observation.acquisition, NODES)
        basis = normal_basis(state.curve, P) / sc.LENGTH
        derivative = shape_jacobian(state, basis)
        observed = np.asarray(observation.scattered)[:, None]
        J[j] = normalize(derivative[:, None, :], observed, (1.0,), 1e-12)
        r[j] = normalize((state.prediction - observation.scattered)[:, None], observed, (1.0,), 1e-12)
        loss[j] = 0.5 * float(r[j] @ r[j])
        relative[j] = np.linalg.norm(state.prediction - observation.scattered) / np.linalg.norm(observation.scattered)
        system[j] = state.system_residual
    points = truth.values(16384)
    ray, ray_summary = normal_ray_error(curve, points, P, sc.LENGTH)
    proxy, proxy_summary = true_error(curve, points, P, sc.LENGTH)
    hausdorff, bound = boundary_distance(truth, curve)
    count = grid_size(curve.band)
    _, refit = _refit_samples(curve, curve.band, count, 1.0)
    nodes = curve.nodes(8192)
    np.savez(target, jacobian=J, residual=r, loss=loss, relative_residual=relative, system_residual=system,
             normal_ray=ray, normal_ray_rms_m=ray_summary["rms_m"], normal_ray_beyond_m=ray_summary["beyond_band_rms_m"],
             normal_ray_max_m=ray_summary["maximum_m"], normal_ray_coverage=ray_summary["coverage"],
             normal_ray_misaligned=ray_summary["misaligned_fraction"], proxy=proxy,
             proxy_beyond_m=proxy_summary["beyond_band_rms_m"],
             symmetric_rms_m=symmetric_rms_distance(curve, points, sc.LENGTH),
             hausdorff_m=hausdorff * sc.LENGTH, hausdorff_upper_m=(hausdorff + bound) * sc.LENGTH,
             tightest_radius_m=sc.LENGTH / np.max(np.abs(nodes.curvatures)),
             refit_relative_K192=refit / (curve.nodes(count).perimeter / (2 * np.pi)),
             speed_ratio=speed_ratio(curve), perimeter_m=nodes.perimeter * sc.LENGTH)
    return str(target)


CELL_FIELDS = ("jacobian", "residual", "loss", "relative_residual", "system_residual")
EVALUATION_FIELDS = ("normal_ray", "normal_ray_rms_m", "normal_ray_beyond_m", "normal_ray_max_m",
                     "normal_ray_coverage", "normal_ray_misaligned", "proxy", "proxy_beyond_m", "symmetric_rms_m",
                     "hausdorff_m", "hausdorff_upper_m", "tightest_radius_m", "refit_relative_K192",
                     "speed_ratio", "perimeter_m")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output, workers):
    output.mkdir(parents=True, exist_ok=True)
    work = output / "work"
    work.mkdir(exist_ok=True)
    states = collect()
    inputs = {}
    for case, bundle in INPUTS.items():
        manifest = sc.read(BASE / bundle / "manifest.json")
        recorded = manifest["amendments"][-1]["inputs"] if bundle.startswith("SC-025") else manifest["inputs"]
        for name in ("observations.json", "truth.json"):
            relative = f"inputs/{case}/{name}"
            actual = digest(BASE / bundle / relative)
            if recorded[relative] != actual:
                raise RuntimeError(f"{bundle}/{relative} changed")
            inputs[f"{bundle}/{relative}"] = actual
    sc.write(output / "manifest.json", dict(
        experiment="SC-026", plan="docs/iterations/shape_frequency_continuation/iteration_09/03_plan.md",
        sources=SOURCES, inputs=inputs, atlas_band=P, nodes=NODES, frequencies_hz=list(ac.CATALOG_HZ),
        unique_states=len(states), state_records=sum(len(s["occurrences"]) for s in states.values()),
        convention=("jacobian: d(normalized residual)/d(coefficient), rows = real parts then imaginary parts of "
                    "24 paired responses, each frequency normalized as a single-frequency stage (weight 1); "
                    "columns a0, a1..a48, b1..b48 (m) of normal distance in the state's normalized arclength"),
        source_sha256=sc.source_hashes(), started=time.strftime("%Y-%m-%dT%H:%M:%S%z")))
    jobs = [(s["case"], s["key"], s["coefficients"], str(work))
            for s in sorted(states.values(), key=lambda s: -len(s["coefficients"]))]
    started = time.perf_counter()
    with ProcessPoolExecutor(workers, initializer=_init) as pool:
        for done, _ in enumerate(pool.map(compute, jobs, chunksize=1), 1):
            if done % 50 == 0 or done == len(jobs):
                print(json.dumps(dict(done=done, of=len(jobs), seconds=time.perf_counter() - started)), flush=True)
    assemble(output, states)


def assemble(output, states):
    work = output / "work"
    (output / "cells").mkdir(exist_ok=True)
    (output / "evaluation").mkdir(exist_ok=True)
    index, hashes = [], {}
    for case in INPUTS:
        members = sorted((s for s in states.values() if s["case"] == case), key=lambda s: s["key"])
        parts = [np.load(work / f"{case}__{s['key']}.npz") for s in members]
        cells = {f: np.stack([p[f] for p in parts]) for f in CELL_FIELDS}
        evaluation = {f: np.stack([p[f] for p in parts]) for f in EVALUATION_FIELDS}
        keys = np.array([s["key"] for s in members])
        coefficients = np.stack([s["coefficients"] for s in members])
        np.savez_compressed(output / "cells" / f"{case}.npz", state_key=keys, coefficients=coefficients,
                            frequencies_hz=np.array(ac.CATALOG_HZ), **cells)
        np.savez_compressed(output / "evaluation" / f"{case}_EVALUATION_ONLY.npz", state_key=keys, **evaluation)
        for name in (f"cells/{case}.npz", f"evaluation/{case}_EVALUATION_ONLY.npz"):
            hashes[name] = digest(output / name)
        for i, s in enumerate(members):
            index.append(dict(case=case, state_key=s["key"], row=i, occurrences=s["occurrences"],
                              symmetric_rms_mm=float(evaluation["symmetric_rms_m"][i] * 1e3),
                              tightest_radius_mm=float(evaluation["tightest_radius_m"][i] * 1e3)))
    sc.write(output / "index.json", index)
    sc.write(output / "summary.json", dict(files_sha256=hashes, unique_states=len(index),
             max_system_residual=float(max(np.load(output / "cells" / f"{c}.npz")["system_residual"].max()
                                           for c in INPUTS)),
             assembled=time.strftime("%Y-%m-%dT%H:%M:%S%z")))


def load(output, case):
    """Cells for one case, with G = J^T J and g = J^T r per state and frequency."""
    data = dict(np.load(Path(output) / "cells" / f"{case}.npz"))
    data["gauss_newton"] = np.einsum("sfri,sfrj->sfij", data["jacobian"], data["jacobian"])
    data["gradient"] = np.einsum("sfri,sfr->sfi", data["jacobian"], data["residual"])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=22)
    args = parser.parse_args()
    build(args.output, args.workers)


if __name__ == "__main__":
    main()
