"""Training-only continuation testing the archived TOP-010 stopping claim.

Uses the existing feasible-FD optimizer; no optimizer or production defaults are
modified. A chunk boundary saves evidence and carries damping, never terminates
a progressing fit. Truth/holdout scoring is a separate --score invocation.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]
import run_fourier_topology_controller as driver
import run_topology_scene_benchmark as benchmark
from sdf_inverse import ComplexScatteredData
from sdf_inverse import radial_topology as rt
from sdf_inverse.runtime import inverse_runtime
from sdf_inverse.topology_controller import TopologyControllerConfig, _optimizer_config
from sdf_inverse.work_accounting import collect_work, accounted_call
from gpr_bem_kress.execution import execution, current_execution
from ordered_boundary.validation_cache import geometry_validation, intersection_validation

DATA = ROOT / "results/validation/topology/TOP-008-20260912-feasible-fd"
SOURCE = ROOT / "results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage4_uncapped_ladder.json"


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    driver.write_json(temporary, value)
    os.replace(temporary, path)


def append(path, value):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(value, default=lambda x: x.tolist() if hasattr(x, "tolist") else float(x)) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def training_data():
    saved = benchmark.read(DATA / "scenes/far-two-stars/observations.json")
    if saved["frequencies_hz"][0] != 500000000:
        raise ValueError("Expected archived 0.5 GHz training column")
    problem = driver.baseline._problem(np.array([500000000.]))
    for name in ("source_points", "receiver_points"):
        np.testing.assert_array_equal(getattr(problem, name), saved[name])
    np.testing.assert_array_equal(problem.source_strengths,
        np.array(saved["source_strengths_real"][:1]) + 1j * np.array(saved["source_strengths_imag"][:1]))
    if (asdict(problem.exterior) != saved["exterior"] or asdict(problem.interior) != saved["interior"]
            or problem.eps0 != saved["eps0"] or problem.mu0 != saved["mu0"]):
        raise ValueError("Archived material or source constants differ")
    # Construct only the training column. No held-out problem or truth geometry
    # enters the fit interface; the JSON container also holds unused columns.
    observed = np.array([[r[0]] for r in saved["observed_real"]]) + 1j * np.array([[r[0]] for r in saved["observed_imag"]])
    return ComplexScatteredData(problem, observed)


def evaluate(state, data, nodes, solve, category="audit"):
    return accounted_call(category, rt.evaluate_multiradial_objective, state, data,
        driver.baseline._geometry_config(nodes), solve_config=solve)


def audit(state, data, nodes, solve, steps, output):
    """Central differences of the actual gauge-fixed retraction, not a surrogate."""
    basis = state.gauge_tangent_basis()
    values = {n: evaluate(state, data, n, solve) for n in nodes}
    matrices, gradients, rows = {}, {}, []
    for n in nodes[:2]:
        for h in steps:
            columns = []
            for direction in basis:
                plus = state.incremented(h * direction).polar_angle_gauge_fixed()[0]
                minus = state.incremented(-h * direction).polar_angle_gauge_fixed()[0]
                ep = evaluate(plus, data, n, solve)
                em = evaluate(minus, data, n, solve)
                columns.append((ep.residual - em.residual) / (2 * h))
            matrix = np.array(columns).T
            gradient = matrix.T @ values[n].residual
            singular = np.linalg.svd(matrix, compute_uv=False)
            matrices[n, h], gradients[n, h] = matrix, gradient
            row = dict(nodes=n, h=h, gradient_inf=float(np.max(np.abs(gradient))),
                gradient=gradient, singular_values=singular,
                condition=float(singular[0] / singular[-1]))
            if (n, h * 4) in matrices:
                delta = matrix - matrices[n, h * 4]
                row.update(relative_jacobian_change=float(np.linalg.norm(delta) / np.linalg.norm(matrix)),
                    gradient_change_inf=float(np.max(np.abs(gradient - gradients[n, h * 4]))),
                    derivative_error_gradient_bound=float(np.linalg.norm(delta, 2) * np.linalg.norm(values[n].residual)))
            rows.append(row)
    comparisons = []
    for low, high in zip(nodes[:-1], nodes[1:]):
        a, b = values[low], values[high]
        delta = np.linalg.norm(a.residual - b.residual)
        comparisons.append(dict(low=low, high=high, residual_discrepancy=delta,
            objective_difference=abs(a.loss - b.loss),
            objective_perturbation_bound=np.linalg.norm(b.residual) * delta + .5 * delta**2))
    record = dict(state=driver.serialize_state(state), rows=rows,
        losses={n: e.loss for n, e in values.items()}, comparisons=comparisons)
    write(output, record)
    print("AUDIT", output.name, json.dumps(dict(losses=record["losses"], comparisons=comparisons)), flush=True)
    return record


def gain_check(base, candidate, refined_base, refined_candidate):
    dp, dr = base.loss - candidate.loss, refined_base.loss - refined_candidate.loss
    # Cauchy--Schwarz first-order objective sensitivity to floating residual
    # perturbations, with 64 eps allowance. The measured resolution discrepancy
    # in the *gain* provides an independent, usually larger requirement.
    residual_scale = max(np.linalg.norm(e.residual) for e in (base, candidate, refined_base, refined_candidate))
    roundoff = 64 * np.finfo(float).eps * max(residual_scale, np.finfo(float).eps)
    resolution = 5 * abs(dp - dr)
    return dict(production_gain=dp, refined_gain=dr, roundoff_allowance=roundoff,
        resolution_allowance=resolution, accepted=bool(min(dp, dr) > roundoff + resolution))


def fit(initial, data, solve, template, output, nodes, h, initial_damping, chunk_size, resume=False, jacobian_mode="fd"):
    """Only state, training data, numerical settings, and optimizer config enter."""
    output.mkdir(parents=True, exist_ok=resume)
    if resume:
        if (output / "closure.json").exists():
            raise ValueError("This study is closed; a later continuation needs a new output and explicit --source final.json")
        old = benchmark.read(output / "terminal.json")
        current = driver.deserialize_state(old["final_state"])
        if old["stop_reason"] != "maximum_iterations":
            raise ValueError("Only an interrupted chunk continuation can be resumed")
        chunk = old["chunks"]
        total_steps = old["accepted_steps"]
        damping = old["next_damping"]
    else:
        current, chunk, total_steps, damping = initial, 0, 0, initial_damping
    optimizer = replace(template, max_iterations=chunk_size, finite_difference_steps=h,
        loss_tolerance=0., gradient_tolerance=0., relative_step_tolerance=0.,
        max_damping_trials=12, max_backtracks=14)
    write(output / "config.json", dict(optimizer=asdict(optimizer), nodes=nodes,
        loss_change_stopping=False, active_frequency_hz=500000000,
        acceptance="min(gain64,gain128)>64 eps max(norm residual,eps)+5 abs(gain64-gain128)",
        chunk_boundary_is_stop=False, runtime="reciprocal" if jacobian_mode == "analytic" else "reference",
        execution=asdict(current_execution()), jacobian_mode=jacobian_mode))
    ref_cache = {}
    started = perf_counter()
    checks = 0
    with collect_work() as ledger:
        def refined(e):
            key = e.state.parameter_vector().tobytes()
            if key not in ref_cache:
                ref_cache[key] = evaluate(e.state, data, nodes[1], solve, "acceptance_validation")
            return ref_cache[key]

        def validate(base, candidate):
            nonlocal checks
            row = gain_check(base, candidate, refined(base), refined(candidate))
            checks += 1
            append(output / "acceptance.jsonl", dict(chunk=chunk, check=checks, **row))
            return row["accepted"]

        def checkpoint(iteration, ev):
            write(output / "accepted_state.json", dict(chunk=chunk, iteration=iteration,
                global_iteration=total_steps + iteration, state=driver.serialize_state(ev.state),
                loss=ev.loss, work=ledger.snapshot()))

        def progress(frame):
            row = dict(chunk=chunk, iteration=frame.iteration, global_iteration=total_steps + frame.iteration,
                state=driver.serialize_state(frame.state), loss=frame.loss,
                gradient_inf=float(np.max(np.abs(frame.state.gauge_tangent_basis() @ frame.gradient))),
                step_norm=float(np.linalg.norm(frame.step)), damping=frame.damping,
                maximum_system_residual=frame.maximum_system_residual,
                work=ledger.snapshot(), seconds=perf_counter() - started)
            append(output / "trajectory.jsonl", row)
            if frame.iteration % 10 == 0:
                print("FIT", output.name, total_steps + frame.iteration, "loss", frame.loss,
                    "gradient", row["gradient_inf"], "seconds", row["seconds"], flush=True)

        while True:
            result = accounted_call("optimizer", rt.run_multiradial_fd_inverse,
                current, data, driver.baseline._geometry_config(nodes[0]), solve_config=solve,
                config=replace(optimizer, initial_damping=damping), cartesian_gauge=True,
                minimum_component_radius_m=.008, feasibility_geometry_configs=(driver.baseline._geometry_config(nodes[1]),),
                feasible_fd_jacobian=True, loss_change_stopping=False, jacobian_mode=jacobian_mode,
                candidate_acceptance_callback=validate, accepted_state_callback=checkpoint,
                progress_callback=progress)
            current = result.final_state
            total_steps += len(result.iterations) - 1
            damping = max(result.iterations[-1].damping * optimizer.damping_decrease, np.finfo(float).tiny)
            chunk += 1
            terminal = dict(final_state=driver.serialize_state(current), accepted_steps=total_steps,
                chunks=chunk, stop_reason=result.stop_reason, next_damping=damping,
                final_loss=result.iterations[-1].loss, final_gradient_inf=float(np.max(np.abs(current.gauge_tangent_basis() @ result.iterations[-1].gradient))),
                one_sided_columns=result.one_sided_jacobian_column_count,
                unresolved_columns=result.unresolved_jacobian_column_count,
                work=ledger.snapshot(), seconds=perf_counter() - started)
            write(output / "terminal.json", terminal)
            if result.stop_reason != "maximum_iterations":
                print("TERMINAL", output.name, result.stop_reason, total_steps, result.iterations[-1].loss, flush=True)
                return current, terminal


def score(output):
    # This entry point is called only once training continuation decisions are
    # frozen; fitting cannot read this file or use these metrics.
    final = benchmark.read(output / "final.json")
    spec = benchmark.read(DATA / "scene_spec.json")
    scene = next(s for s in spec["scenes"] if s["id"] == "far-two-stars")
    train, holdout = benchmark.shared_data(DATA, scene, spec)
    solve = driver.baseline.iteration01_solve_config()
    scores = {}
    with collect_work() as ledger:
        for label, record in (("initial", benchmark.read(SOURCE)), ("final", final)):
            state = driver.deserialize_state(record["final_state"])
            scores[label] = dict(geometry=benchmark.geometry_metrics(state, scene, spec),
                train={n: evaluate(state, train, n, solve, "score").relative_l2_error for n in (128, 256)},
                holdout={n: np.linalg.norm(evaluate(state, holdout, n, solve, "score").prediction - holdout.observed_scattered_response, axis=0)
                    / np.linalg.norm(holdout.observed_scattered_response, axis=0) for n in (128, 256)})
        scores["work"] = ledger.snapshot()
    scores["fitting_decisions_frozen_before_score"] = True
    write(output / "postfit_scores.json", scores)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/stopping-floor-20261002")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--nodes", type=int, default=64)
    parser.add_argument("--fd-step", type=float, default=1e-4)
    parser.add_argument("--damping", type=float, default=1e-3)
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--kernels", choices=("reference", "real_bessel"), default="reference")
    parser.add_argument("--jacobian", choices=("fd", "analytic"), default="fd")
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--geometry-mode", choices=("reference", "certified"), default="reference")
    parser.add_argument("--reuse-initial-audit", type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if (args.nodes < 64 or args.nodes % 2 or args.fd_step <= 0 or not np.isfinite(args.fd_step)
            or args.chunk_size <= 0 or args.stage < 0 or args.damping <= 0 or not np.isfinite(args.damping)):
        parser.error("Need even nodes >=64, positive finite FD step and chunk size")
    if any(os.environ.get(v) != "1" for v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")):
        parser.error("Set OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1")
    with (inverse_runtime("reciprocal" if args.jacobian == "analytic" else "reference"),
            execution(kernels=args.kernels, device="cpu"), geometry_validation(args.geometry_mode),
            intersection_validation("spatial" if args.geometry_mode == "certified" else "reference")):
        if args.score:
            score(args.output)
            return
        args.output.mkdir(parents=True, exist_ok=True)
        data = training_data()
        solve = driver.baseline.iteration01_solve_config()
        source = args.source.resolve() if args.stage == 0 else args.output / f"stage_{args.stage - 1}" / "terminal.json"
        saved = benchmark.read(source)
        initial = driver.deserialize_state(saved.get("final_state", saved.get("state")))
        if args.jacobian == "analytic" and args.stage == 0:
            if args.qualification is None:
                parser.error("Analytic arm requires --qualification from the same frozen start")
            qualification = benchmark.read(args.qualification)
            if not qualification["passed"] or qualification["nodes"] != args.nodes:
                raise ValueError("Analytic release requires passing qualification at the selected nodes")
            np.testing.assert_array_equal(initial.parameter_vector(), driver.deserialize_state(qualification["state"]).parameter_vector())
            if args.geometry_mode == "certified" and not all(qualification.get("geometry_acceleration", {}).get(k, False)
                    for k in ("matrix_bitwise_equal", "proposal_bitwise_equal", "stencil_decisions_equal")):
                raise ValueError("Accelerated geometry requires its own equivalence qualification")
        template = _optimizer_config(initial, TopologyControllerConfig(chart="cartesian"))
        nodes = (args.nodes, args.nodes * 2, args.nodes * 4)
        stage = args.output / f"stage_{args.stage}"
        if not args.resume:
            write(args.output / f"stage_{args.stage}_manifest.json", dict(source=str(source.relative_to(ROOT)),
                source_sha256=digest(source), code_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                    (Path(__file__), ROOT / "solvers/sdf_inverse/radial_topology.py", ROOT / "solvers/sdf_inverse/optimization.py")},
                observations_sha256=digest(DATA / "scenes/far-two-stars/observations.json"),
                initial_state=driver.serialize_state(initial), truth_available_to_fit=False, holdout_available_to_fit=False,
                active_frequency_hz=500000000, command=sys.argv))
            if args.kernels != "reference":
                comparisons = []
                with collect_work() as ledger:
                    for n in nodes:
                        predictions = {}
                        for kernels in ("reference", args.kernels):
                            with execution(kernels=kernels, device="cpu"):
                                started = perf_counter()
                                ev = evaluate(initial, data, n, solve, "kernel_calibration")
                                predictions[kernels] = (ev, perf_counter() - started)
                        a, sa = predictions["reference"]
                        b, sb = predictions[args.kernels]
                        difference = float(np.linalg.norm(a.residual - b.residual))
                        if difference > 1e-11:
                            raise ValueError("Fast kernel disagrees with reference beyond calibration gate")
                        comparisons.append(dict(nodes=n, residual_discrepancy=difference,
                            loss_discrepancy=abs(a.loss-b.loss), reference_seconds=sa, selected_seconds=sb))
                    write(args.output / f"stage_{args.stage}_kernel_calibration.json", dict(comparisons=comparisons, work=ledger.snapshot()))
            if args.reuse_initial_audit:
                previous = benchmark.read(args.reuse_initial_audit)
                audit_manifest = args.reuse_initial_audit.with_name(
                    args.reuse_initial_audit.name.replace("_initial_audit.json", "_manifest.json"))
                if (not audit_manifest.exists() or benchmark.read(audit_manifest).get("observations_sha256")
                        != digest(DATA / "scenes/far-two-stars/observations.json")):
                    raise ValueError("Reused audit must have a matching training-observation provenance manifest")
                np.testing.assert_array_equal(initial.parameter_vector(), driver.deserialize_state(previous["state"]).parameter_vector())
                expected = {(n, h) for n in nodes[:2] for h in (args.fd_step, args.fd_step / 4)}
                if {(r["nodes"], r["h"]) for r in previous["rows"]} != expected:
                    raise ValueError("Reused audit has different nodes or FD scales")
                previous["reused_from"] = str(args.reuse_initial_audit.resolve())
                previous["reused_sha256"] = digest(args.reuse_initial_audit)
                write(args.output / f"stage_{args.stage}_initial_audit.json", previous)
                write(args.output / f"stage_{args.stage}_initial_audit_work.json", dict(reused=True, additional_solves=0))
            else:
                with collect_work() as ledger:
                    audit(initial, data, nodes, solve, [args.fd_step, args.fd_step / 4], args.output / f"stage_{args.stage}_initial_audit.json")
                    write(args.output / f"stage_{args.stage}_initial_audit_work.json", ledger.snapshot())
        current, terminal = fit(initial, data, solve, template, stage, nodes[:2], args.fd_step,
            args.damping, args.chunk_size, resume=args.resume, jacobian_mode=args.jacobian)
        with collect_work() as ledger:
            audit(current, data, nodes, solve, [args.fd_step, args.fd_step / 4, args.fd_step / 16], args.output / f"stage_{args.stage}_terminal_audit.json")
            write(args.output / f"stage_{args.stage}_terminal_audit_work.json", ledger.snapshot())
        write(args.output / "final.json", dict(stage=args.stage, **terminal))


if __name__ == "__main__":
    main()
