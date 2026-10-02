"""Qualify the existing analytic Jacobian and its first actual LM proposal.

The diagnostic callback interrupts before taking the proposed step. There is
no experimental optimizer here: both matrices and proposals come from the
existing optimizer, at the same frozen training-only state.
"""
from dataclasses import replace
from pathlib import Path
import argparse
import json
import sys
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "solvers")]
from experiments.stopping_floor import continue_top010 as c
from sdf_inverse.runtime import inverse_runtime
from sdf_inverse.work_accounting import collect_work, accounted_call
from gpr_bem_kress.execution import execution
from ordered_boundary.validation_cache import geometry_validation, intersection_validation


class Captured(Exception):
    pass


def probe(state, data, nodes, h, mode, solve, accelerated=False):
    result = {}
    def diagnostic(event, value):
        if event == "jacobian_complete":
            result.update(matrix=value["matrix"].copy(),
                one_sided=value["one_sided_columns"], unresolved=value["unresolved_columns"])
        elif event == "candidate_attempt":
            result["step"] = value["step"].copy()
            raise Captured()
    optimizer = replace(c._optimizer_config(state, c.TopologyControllerConfig(chart="cartesian")),
        finite_difference_steps=h, gradient_tolerance=0., loss_tolerance=0.,
        relative_step_tolerance=0., max_iterations=1, max_damping_trials=12, max_backtracks=14)
    started = perf_counter()
    with (inverse_runtime("reciprocal"), execution(kernels="real_bessel", device="cpu"), collect_work() as ledger,
            geometry_validation("certified" if accelerated else "reference"),
            intersection_validation("spatial" if accelerated else "reference")):
        try:
            accounted_call(mode, c.rt.run_multiradial_fd_inverse,
                state, data, c.driver.baseline._geometry_config(nodes), solve_config=solve,
                config=optimizer, minimum_component_radius_m=.008, cartesian_gauge=True,
                feasibility_geometry_configs=(c.driver.baseline._geometry_config(2*nodes),),
                feasible_fd_jacobian=True, loss_change_stopping=False,
                jacobian_mode=mode, analytic_constraint_policy="fd_compatible", diagnostic_callback=diagnostic)
        except Captured:
            pass
        else:
            raise RuntimeError("Optimizer did not reach a proposal")
        result["work"] = ledger.snapshot()
        result["seconds"] = perf_counter() - started
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/stopping-floor-20261002/analytic_qualification")
    parser.add_argument("--source", type=Path, default=c.SOURCE)
    parser.add_argument("--nodes", type=int, default=128)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    saved = c.benchmark.read(args.source)
    state = c.driver.deserialize_state(saved.get("final_state", saved.get("state")))
    data, solve = c.training_data(), c.driver.baseline.iteration01_solve_config()
    analytic = probe(state, data, args.nodes, 2.5e-5, "analytic", solve)
    accelerated = probe(state, data, args.nodes, 2.5e-5, "analytic", solve, accelerated=True)
    acceleration = dict(matrix_bitwise_equal=np.array_equal(analytic["matrix"], accelerated["matrix"]),
        proposal_bitwise_equal=np.array_equal(analytic["step"], accelerated["step"]),
        stencil_decisions_equal=analytic["one_sided"] == accelerated["one_sided"] and analytic["unresolved"] == accelerated["unresolved"],
        reference_seconds=analytic["seconds"], accelerated_seconds=accelerated["seconds"], work=accelerated["work"])
    arrays = dict(analytic_jacobian=analytic["matrix"], analytic_step=analytic["step"])
    rows = []
    singular = np.linalg.svd(analytic["matrix"], compute_uv=False)
    for h in (2.5e-5, 6.25e-6):
        fd = probe(state, data, args.nodes, h, "fd", solve)
        error = fd["matrix"] - analytic["matrix"]
        row = dict(h=h, relative_jacobian_error=np.linalg.norm(error)/np.linalg.norm(analytic["matrix"]),
            maximum_relative_column_error=float(np.max(np.linalg.norm(error, axis=0)/np.linalg.norm(analytic["matrix"], axis=0))),
            operator_error_over_smallest_singular=np.linalg.norm(error, 2)/singular[-1],
            relative_proposal_error=np.linalg.norm(fd["step"]-analytic["step"])/np.linalg.norm(analytic["step"]),
            one_sided=fd["one_sided"], unresolved=fd["unresolved"], work=fd["work"])
        arrays[f"fd_jacobian_{h}"] = fd["matrix"]
        arrays[f"fd_step_{h}"] = fd["step"]
        with inverse_runtime("reference"), execution(kernels="real_bessel", device="cpu"), collect_work() as ledger:
            base = [c.evaluate(state, data, n, solve) for n in (args.nodes, 2*args.nodes)]
            decisions = {}
            for label, item in (("analytic", analytic), ("fd", fd)):
                candidate = state.incremented(item["step"]).polar_angle_gauge_fixed()[0]
                proposed = [c.evaluate(candidate, data, n, solve) for n in (args.nodes, 2*args.nodes)]
                decisions[label] = c.gain_check(base[0], proposed[0], base[1], proposed[1])
            row.update(proposal_checks=decisions, proposal_validation_work=ledger.snapshot())
        rows.append(row)
    np.savez_compressed(args.output / "matrices.npz", **arrays)
    # This gate is deliberately substantially tighter than the old FD-gradient
    # stability gate. It qualifies a local derivative/proposal, not every future
    # state; terminal FD checks are still required.
    passed = bool(rows[-1]["relative_jacobian_error"] < 1e-6
        and rows[-1]["maximum_relative_column_error"] < 1e-5
        and rows[-1]["relative_proposal_error"] < 1e-4
        and all(r["proposal_checks"]["analytic"]["accepted"] == r["proposal_checks"]["fd"]["accepted"] for r in rows)
        and analytic["one_sided"] == analytic["unresolved"] == 0
        and all(r["one_sided"] == r["unresolved"] == 0 for r in rows))
    passed = passed and all(acceleration[k] for k in ("matrix_bitwise_equal", "proposal_bitwise_equal", "stencil_decisions_equal"))
    record = dict(passed=passed, source=str(args.source), source_sha256=c.digest(args.source),
        code_sha256=c.digest(Path(__file__)), state=c.driver.serialize_state(state), nodes=args.nodes,
        analytic_work=analytic["work"], analytic_singular_values=singular, rows=rows, geometry_acceleration=acceleration,
        training_frequency_hz=500000000, truth_available=False, holdout_available=False)
    c.write(args.output / "qualification.json", record)
    print(json.dumps(record, default=lambda x: x.tolist() if hasattr(x, "tolist") else float(x)))
    if not passed:
        raise SystemExit("Analytic qualification gate failed; inspect/refine before release")


if __name__ == "__main__":
    main()
