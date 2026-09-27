"""SC-047 bounded coupled-forward and complete-trial derivative qualification."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

from experiments.shape_continuation import spd_cases as sc
from experiments.shape_continuation.atlas_cases import c_shape_curve
from experiments.shape_continuation.forward import Work, solve, shape_jacobian
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "SC-035-state-band"))
from state_update import ProjectedUpdate, resize

FREQUENCIES = (.25e9, .5e9, 1e9, 1.5e9)
LENGTH, BAND = .05, 32
PLAN = ROOT / "docs/iterations/shape_frequency_continuation/iteration_26/03_plan.md"


def write(path, value):
    def complex_records(item):
        if isinstance(item, np.ndarray):
            return complex_records(item.tolist())
        if isinstance(item, complex):
            return dict(real=item.real, imag=item.imag)
        if isinstance(item, dict):
            return {k: complex_records(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [complex_records(v) for v in item]
        return item
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    sc.write(temporary, complex_records(value))
    temporary.replace(path)


def setup():
    import config.two_circle_config as cfg
    import run_radial_fourier_topology_inverse as legacy
    sources, _ = legacy._ring_scan()
    catalog = sc.package_observations(FREQUENCIES, np.ones((len(sources), 4), complex), cfg, legacy)
    return catalog, cfg.PLASTIC_EPSR / cfg.SAND_EPSR, legacy


def shifted(curve, center=0j, scale=1., rotation=0.):
    c = resize(curve, BAND).coefficients.copy() * scale * np.exp(1j * rotation)
    c[BAND] += center
    return FourierCurve(c)


def scene(separation, *, initial=False, circles=False):
    d = separation / LENGTH / 2
    if circles:
        return MultiCurve((shifted(FourierCurve.circle(.6), -d),
                           shifted(FourierCurve.circle(.8), d)), ("ellipse", "c"))
    ellipse = FourierCurve(np.array([.08, 0j, .52]))
    curves = (shifted(ellipse, -d), shifted(c_shape_curve(), d))
    if initial:
        curves = (shifted(ellipse, -d + .04 + .03j, 1.08, .10),
                  shifted(c_shape_curve(), d - .04 + .03j, .94, -.06))
    return MultiCurve(curves, ("ellipse", "c"))


def record_scene(curve):
    return dict(ids=curve.ids, band=curve.band,
                components=[dict(real=c.coefficients.real, imag=c.coefficients.imag) for c in curve.components])


def load_scene(row):
    return MultiCurve(tuple(FourierCurve(np.array(c["real"]) + 1j * np.array(c["imag"]))
                            for c in row["components"]), tuple(row["ids"]))


def source_hashes():
    paths = [PLAN, Path(__file__), HERE.parent / "SC-035-state-band/state_update.py"]
    for directory in ("experiments/shape_continuation", "solvers/gpr_bem_kress", "solvers/ordered_boundary"):
        paths.extend((ROOT / directory).rglob("*.py"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def manifest(extra=None):
    return dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                source_sha256=source_hashes(), command=sys.argv, python=sys.version,
                platform=platform.platform(), threads={k: os.getenv(k) for k in
                    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
                utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **(extra or {}))


def verify(record):
    for name, digest in record["source_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Measured source changed: " + name)


def relative(a, b):
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), 1e-30))


def qualify():
    if (HERE / "qualification.json").exists():
        raise FileExistsError("Preserve existing qualification; use its recorded outcome.")
    catalog, contrast, legacy = setup()
    frozen = manifest(dict(frequencies_hz=FREQUENCIES, contrast=contrast,
                           acquisition=asdict(catalog[0].acquisition), band=BAND,
                           eps_m=[2e-6, 1e-6, 5e-7], node_counts=[128, 256, 512]))
    write(HERE / "qualification_manifest.json", frozen)
    work = Work(max_forwards=1000, max_seconds=1200)
    result = dict(status="RUNNING", reference=[], derivatives=[], invariance=[], scenes=[])
    update = MultiUpdate(ProjectedUpdate(LENGTH))
    try:
        for separation in (.14, .20):
            circles = scene(separation, circles=True)
            centers = np.array([[.5 - separation / 2, .5], [.5 + separation / 2, .5]])
            oracle = legacy._oracle_response(centers, np.array([.03, .04]), np.array(FREQUENCIES),
                                             component_ids=circles.ids)
            # Independent multi-cylinder work is additional to Kress solve units.
            for k, observation in enumerate(catalog):
                coarse = solve(circles, observation.wavenumber, contrast, observation.acquisition, 128, work=work)
                fine = solve(circles, observation.wavenumber, contrast, observation.acquisition, 256, work=work)
                result["reference"].append(dict(separation_m=separation, frequency_hz=FREQUENCIES[k],
                    coarse_vs_oracle=relative(coarse.prediction, oracle[:, k]),
                    fine_vs_oracle=relative(fine.prediction, oracle[:, k])))
            current = scene(separation, initial=True)
            current.validate()
            result["scenes"].append(dict(separation_m=separation, state=record_scene(current),
                radial_normal_min=[float(np.min(np.sum((c.nodes(1024).points -
                    np.array([c.coefficients[BAND].real, c.coefficients[BAND].imag])) *
                    c.nodes(1024).normals, axis=1))) for c in current.components]))
            space = update.prepare(current, 3, BAND)
            rng = np.random.default_rng(47)
            directions = []
            for active in ((0,), (1,), (0, 1)):
                direction = np.zeros(len(space.orders))
                for j in active:
                    direction[space.slices[j]] = rng.normal(size=7)
                direction /= np.linalg.norm(direction)
                directions.append((active, direction))
            for k, observation in enumerate(catalog):
                states = [solve(current, observation.wavenumber, contrast, observation.acquisition, n, work=work)
                          for n in (128, 256, 512)]
                result["reference"].append(dict(separation_m=separation, frequency_hz=FREQUENCIES[k],
                    shape="ellipse_c", coarse_refinement=relative(states[0].prediction, states[1].prediction),
                    fine_refinement=relative(states[1].prediction, states[2].prediction)))
                for nodes, state in zip((128, 256), states):
                    jac = shape_jacobian(state, update.velocities(space, state.curve), work=work)
                    for active, direction in directions:
                        errors = []
                        for eps in (2e-6, 1e-6, 5e-7):
                            values = [solve(update.trial(space, sign * eps * direction)[0],
                                observation.wavenumber, contrast, observation.acquisition, nodes, work=work).prediction
                                for sign in (1, -1)]
                            errors.append(relative((values[0] - values[1]) / (2 * eps), jac @ direction))
                        result["derivatives"].append(dict(separation_m=separation, frequency_hz=FREQUENCIES[k],
                            nodes=nodes, active=active, errors=errors))
                reverse = MultiCurve(current.components[::-1], current.ids[::-1])
                other = solve(reverse, observation.wavenumber, contrast, observation.acquisition, 128, work=work)
                single = solve(current.components[1], observation.wavenumber, contrast, observation.acquisition, 256, work=work)
                wrapped = solve(MultiCurve((current.components[1],), ("c",)), observation.wavenumber,
                                contrast, observation.acquisition, 256, work=work)
                result["invariance"].append(dict(permutation=relative(other.prediction, states[0].prediction),
                                                 single=relative(single.prediction, wrapped.prediction)))
                write(HERE / "qualification.json", dict(result, work=work.summary()))
                print(json.dumps(dict(separation_m=separation, frequency_hz=FREQUENCIES[k],
                    forwards=work.completed, latest_derivative_max=max(result["derivatives"][-1]["errors"]))), flush=True)
        result["passed"] = bool(
            all(r.get("fine_vs_oracle", r.get("fine_refinement", 0)) <= 1e-6 for r in result["reference"])
            and all(max(r["errors"][-2:]) <= 1e-3 for r in result["derivatives"] if r["nodes"] == 256)
            and all(max(r.values()) <= 1e-11 for r in result["invariance"]))
        result["status"] = "PASS" if result["passed"] else "FAIL"
    except Exception as exc:
        import traceback
        result.update(status="ERROR", passed=False, error=repr(exc), traceback=traceback.format_exc())
    verify(frozen)
    result.update(work=work.summary(), seconds=time.perf_counter() - work.started,
                  independent_multicylinder_frequency_solves=8, update_counts=update.base.counts)
    write(HERE / "qualification.json", result)
    print(json.dumps(dict(status=result["status"], seconds=result["seconds"], work=result["work"])), flush=True)
    if not result.get("passed"):
        raise RuntimeError("SC-047 qualification did not pass.")


if __name__ == "__main__":
    assert all(os.getenv(k) == "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"))
    qualify()
