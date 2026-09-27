"""SC-047 diagnostic-only current-scene insertion and deletion counterfactuals."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from shapely.geometry import Point, Polygon

from qualify import (HERE, ROOT, LENGTH, FREQUENCIES, BAND, ProjectedUpdate, resize,
                     setup, scene, shifted, write, record_scene, manifest, verify, relative)
from strategies import fit, stage, CONFIG
from experiments.shape_continuation.forward import solve, Work, BudgetExceeded
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import normalize
from experiments.shape_continuation.multi_object import MultiCurve, insertion_response


def with_disk(current, point, radius):
    disk = resize(FourierCurve.circle(radius, complex(*point)), BAND)
    return MultiCurve((*current.components, disk), (*current.ids, "probe"))


def predictions(current, catalog, contrast, work, nodes=256):
    if work.attempted + len(catalog) > work.max_forwards:
        raise BudgetExceeded("Cannot reserve the complete topology frequency batch.")
    states = [solve(current, o.wavenumber, contrast, o.acquisition, nodes, work=work) for o in catalog]
    return np.column_stack([s.prediction for s in states]), states


def objective(prediction, observed):
    r = normalize(prediction - observed, observed, (.25,) * 4)
    return .5 * float(r @ r), r


def grid(current):
    polygons = [Polygon(c.nodes(2048).points) for c in current.components]
    points = np.array([(x, y) for y in np.linspace(-2.5, 2.5, 21)
                       for x in np.linspace(-3.5, 3.5, 29)])
    keep = [all(p.distance(Point(*x)) > .15 for p in polygons) for x in points]
    return points[keep]


def map_and_probes(current, catalog, contrast, work):
    observed = np.column_stack([o.scattered for o in catalog])
    data, states = predictions(current, catalog, contrast, work)
    loss, residual = objective(data, observed)
    points = grid(current)
    raw = np.stack([insertion_response(s, points, work=work) for s in states], axis=1)
    response = normalize(raw, observed, (.25,) * 4)
    derivative = residual @ response
    index = int(np.argmin(derivative))
    chosen = points[index]
    candidate = with_disk(current, chosen, .06)  # declared finite 3 mm radius
    values, _ = predictions(candidate, catalog, contrast, work)
    birth_loss, _ = objective(values, observed)
    refined, _ = predictions(candidate, catalog, contrast, work, nodes=512)
    refined_base, _ = predictions(current, catalog, contrast, work, nodes=512)
    refined_loss, _ = objective(refined, observed)
    refined_base_loss, _ = objective(refined_base, observed)
    deletes = []
    for j, name in enumerate(current.ids):
        if len(current.components) == 1:
            deletion = np.zeros_like(observed)
        else:
            candidate_delete = MultiCurve(tuple(c for i, c in enumerate(current.components) if i != j),
                                           tuple(x for i, x in enumerate(current.ids) if i != j))
            deletion, _ = predictions(candidate_delete, catalog, contrast, work, nodes=512)
        value, _ = objective(deletion, observed)
        deletes.append(dict(component_id=name, loss=value, decrease=refined_base_loss - value))
    return dict(state=record_scene(current), loss=loss, refined_base_loss=refined_base_loss,
                points=points, derivative_per_package_area=derivative,
                selected_point=chosen, minimum=float(derivative[index]),
                finite_birth_radius_m=.003, finite_birth_loss=birth_loss,
                finite_birth_refined_loss=refined_loss,
                finite_birth_refined_decrease=refined_base_loss - refined_loss,
                finite_birth_refinement=relative(values, refined), deletions=deletes,
                reciprocal_batches=4, grid_field_point_rhs_products=len(points) * len(catalog[0].scattered) * 2 * 4)


def run():
    if (HERE / "topology.json").exists():
        raise FileExistsError("Preserve the existing diagnostic record.")
    if not json.loads((HERE / "qualification.json").read_text())["passed"]:
        raise RuntimeError("Coupled qualification failed.")
    catalog, contrast, _ = setup()
    frozen = manifest(dict(study="diagnostic_only", grid=[29, 21], clearance_package=.15,
        finite_radius_m=.003, eps_package=[.004, .002, .001, .0005], shape_work_cap_per_case=100,
        shape_dispatches=4, noise_seed=4701, maximum_frequency_solves=600, maximum_seconds=1200,
        formula="(ki^2-k^2) u_source u_reciprocal in current coupled scene",
        literature="https://arxiv.org/html/2501.15327v1#S4.SS2", configuration=asdict(CONFIG)))
    for source in (Path(__file__), HERE / "strategies.py"):
        frozen["source_sha256"][str(source.relative_to(ROOT))] = hashlib.sha256(source.read_bytes()).hexdigest()
    write(HERE / "topology_manifest.json", frozen)
    work = Work(max_forwards=600, max_seconds=1200)
    result = dict(status="RUNNING", insertion_qualification=[], cases={}, topology_actions_enabled=False)
    try:
        truth = scene(.14)
        clean, _ = predictions(truth, catalog, contrast, work, nodes=512)
        rng = np.random.default_rng(4701)
        noise = rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape)
        noise *= .01 * np.linalg.norm(clean, axis=0) / np.linalg.norm(noise, axis=0)
        current = scene(.14, initial=True)
        observed = clean
        data, states = predictions(current, catalog, contrast, work)
        base_loss, residual = objective(data, observed)
        points = np.array([[0., 1.9], [0., -1.9]])
        raw = np.stack([insertion_response(s, points, work=work) for s in states], axis=1)
        q = normalize(raw, observed, (.25,) * 4)
        for j, point in enumerate(points):
            rows = []
            for eps in (.004, .002, .001, .0005):
                values, _ = predictions(with_disk(current, point, eps), catalog, contrast, work)
                area = np.pi * eps**2
                response = normalize((values - data) / area, observed, (.25,) * 4)
                loss, _ = objective(values, observed)
                rows.append(dict(radius_package=eps, response_error=relative(response, q[:, j]),
                    derivative=float(residual @ q[:, j]), finite_derivative=(loss - base_loss) / area,
                    sign_agrees=bool(np.sign(loss - base_loss) == np.sign(residual @ q[:, j]))))
            result["insertion_qualification"].append(dict(point=point, rows=rows,
                passed=bool(max(x["response_error"] for x in rows[-2:]) <= .02
                            and rows[-1]["response_error"] < rows[0]["response_error"]
                            and all(x["sign_agrees"] for x in rows[-2:]))))
        write(HERE / "topology.json", dict(result, work=work.summary()))
        if not all(x["passed"] for x in result["insertion_qualification"]):
            raise RuntimeError("Small-inclusion gate failed.")
        extra = shifted(FourierCurve.circle(.35), 1.7j)
        cases = dict(wrong_boundary=(current, clean),
            missing=(MultiCurve((truth.components[0],), (truth.ids[0],)), clean),
            extra=(MultiCurve((*truth.components, extra), (*truth.ids, "extra")), clean),
            noisy_correct=(truth, clean + noise))
        write(HERE / "topology_inputs.json", dict(truth=record_scene(truth), clean_real=clean.real,
            clean_imag=clean.imag, noise_real=noise.real, noise_imag=noise.imag,
            initial_states={name: record_scene(value[0]) for name, value in cases.items()}))
        for name, (initial, data) in cases.items():
            observations = tuple(Observation(o.wavenumber, o.acquisition, data[:, k]) for k, o in enumerate(catalog))
            before = map_and_probes(initial, observations, contrast, work)
            remaining = 1200 - (time.perf_counter() - work.started)
            work.check()
            if work.attempted + 100 + 40 > 600 or remaining < 1:
                raise RuntimeError("Topology budget cannot reserve shape refinement and after-map.")
            endpoint, fit_record = fit(initial, observations, contrast, "joint",
                HERE / "topology_refinements" / name, dispatches=4, cap=100, seconds=remaining)
            # Charge actual shape forward calls against this study's solve ceiling;
            # reciprocal batches remain separately explicit in fit_record.work.
            shape_solves = sum(fit_record["work"]["solves"].values())
            work.attempted += shape_solves
            work.completed += shape_solves - sum(fit_record["work"]["failed"].values())
            work.failed += sum(fit_record["work"]["failed"].values())
            work.factorizations += shape_solves - sum(fit_record["work"]["failed"].values())
            work.rhs_columns += (shape_solves + sum(fit_record["work"]["reciprocal_batches"].values())) * len(data)
            after = map_and_probes(endpoint, observations, contrast, work)
            result["cases"][name] = dict(before=before, after=after, refinement=fit_record)
            write(HERE / "topology.json", dict(result, work=work.summary()))
            print(json.dumps(dict(case=name, before_min=before["minimum"], after_min=after["minimum"],
                birth_decrease=after["finite_birth_refined_decrease"], forwards=work.completed)), flush=True)
        result["status"] = "COMPLETE"
        result["false_birth_controls"] = {name: result["cases"][name]["after"]["finite_birth_refined_decrease"] > 0
                                          for name in ("wrong_boundary", "noisy_correct")}
        result["decision"] = "NO_ACTION_PROMOTION_DIAGNOSTIC_SCREEN_ONLY"
    except Exception as exc:
        import traceback
        result.update(status="STOPPED", error=repr(exc), traceback=traceback.format_exc())
    verify(frozen)
    result.update(work=work.summary(), seconds=time.perf_counter() - work.started)
    write(HERE / "topology.json", result)
    print(json.dumps(dict(status=result["status"], seconds=result["seconds"], error=result.get("error"))), flush=True)


if __name__ == "__main__":
    run()
