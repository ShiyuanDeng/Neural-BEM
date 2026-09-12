"""TOP-010 stage A: is the saved K=9 state stationary, or merely stopped?

Diagnostic only. No source change, no controller default, no new arm, and no
state is advanced or saved as a reconstruction. Truth and holdout are not read
at all here -- nothing in this script can select a direction.

Three questions, in order:

1. Is the terminal gradient small, and is it *stable* across FD step scales? An
   unstable gradient would mean the number is finite-difference noise rather
   than a property of the objective.
2. Is the reduced Jacobian well conditioned there? Singular values say whether
   the local model can even represent a descent direction.
3. Does a step along the negative gradient or the LM direction actually reduce
   the objective at *both* resolutions, at the trust bounds and backtracking
   scales the optimizer itself would use?

Budgets are the plan's, declared before execution, and enforced at solver-call
boundaries in separate ledger categories.
"""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import (
    component_radius_floor, evaluate_multiradial_objective, multiradial_geometry_admissible,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, _optimizer_config, chart_contour_modes,
)
from sdf_inverse.geometry import OrderedSDFGeometryError

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
SOURCE = ROOT / 'results/validation/topology/TOP-009-20260912-bandwidth-capacity'
SCENE = 'far-two-stars'
# Declared in the plan before execution.
FD_STEPS = (1.0e-4, 5.0e-5, 2.5e-5)
AUDIT_SOLVE_CAP = 500  # per audited state
SECONDS_CEILING = 600.0
# A gradient counts as stable if its relative change between adjacent FD scales
# stays within this. Same tolerance the TOP-008 stage-1 stencil audit declared.
STABILITY_TOLERANCE = 0.25
# Two states, audited identically: the ladder's endpoint, and the plateau that
# repeated plain restarts reach. Auditing the second is what keeps a "now it is
# stationary" claim from repeating the error this experiment exists to correct.
STATES = (('stage4_ladder_endpoint', SOURCE / 'stage4_uncapped_ladder.json'),
          ('stageB_restart_plateau', HERE / 'stageB_restart_continuation.json'))


class Budget(Exception):
    """Raised at a solver-call boundary when a declared limit is reached."""


class Ledger:
    """Counts forward solves by category so no call escapes the budget."""

    def __init__(self, cap, seconds):
        self.cap, self.seconds, self.started = cap, seconds, perf_counter()
        self.counts = {}

    @property
    def total(self):
        return sum(self.counts.values())

    def charge(self, category):
        if self.total >= self.cap:
            raise Budget(f'solve cap {self.cap} reached at {self.counts}')
        if perf_counter() - self.started >= self.seconds:
            raise Budget(f'{self.seconds:g} s ceiling reached at {self.counts}')
        self.counts[category] = self.counts.get(category, 0) + 1


def main():
    audits = []
    for label, path in STATES:
        if not path.exists():
            print(f'skipping {label}: {path.name} not present yet', flush=True)
            continue
        print(f'\n########## {label} ##########', flush=True)
        audits.append(audit(label, benchmark.read(path)['final_state']))
    driver.write_json(HERE / 'stageA_terminal_audit.json', dict(
        fd_steps=list(FD_STEPS), solve_cap=AUDIT_SOLVE_CAP,
        seconds_ceiling=SECONDS_CEILING, stability_tolerance=STABILITY_TOLERANCE,
        audits=audits))


def audit(label, serialized):
    spec = benchmark.read(DATA / 'scene_spec.json')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    training, _ = benchmark.shared_data(DATA, scene, spec)
    state = driver.deserialize_state(serialized)
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    optimizer = _optimizer_config(state, config)
    ledger = Ledger(AUDIT_SOLVE_CAP, SECONDS_CEILING)
    basis = state.gauge_tangent_basis()
    margin = None
    record = dict(
        state=label, scene=SCENE, data_bundle=str(DATA.relative_to(ROOT)),
        source_bundle=str(SOURCE.relative_to(ROOT)),
        modes=[c.maximum_mode for c in state.components],
        parameters=state.parameter_count, gauge_directions=len(basis),
        fd_steps=list(FD_STEPS), solve_cap=AUDIT_SOLVE_CAP,
        seconds_ceiling=SECONDS_CEILING, stability_tolerance=STABILITY_TOLERANCE)

    def evaluate(candidate, geometry, category):
        ledger.charge(category)
        return evaluate_multiradial_objective(candidate, training, geometry, solve_config=solve)

    def admissible(candidate):
        """The optimizer's own feasible set: floor, then both resolutions."""
        if any(component_radius_floor(c) < config.minimum_component_radius_m
               for c in candidate.components):
            return False
        return (multiradial_geometry_admissible(candidate, production, solve_config=solve)
                and multiradial_geometry_admissible(candidate, refined, solve_config=solve))

    def retract(step):
        return state.incremented(step).polar_angle_gauge_fixed()[0]

    def probe(step, category):
        try:
            candidate = retract(step)
        except (ValueError, OrderedSDFGeometryError):
            return None, 'retract_failed'
        if not admissible(candidate):
            return None, 'inadmissible'
        return candidate, 'ok'

    try:
        base_production = evaluate(state, production, 'base')
        base_refined = evaluate(state, refined, 'base')
        margin = (config.acceptance_absolute_margin
                  + config.acceptance_relative_margin * base_production.loss)
        record.update(production_loss=float(base_production.loss),
                      refined_loss=float(base_refined.loss),
                      relative_l2_error=float(base_production.relative_l2_error),
                      margin=float(margin))
        print(f'state modes {record["modes"]} · {len(basis)} gauge directions · '
              f'production {base_production.loss:.6e} · refined {base_refined.loss:.6e}',
              flush=True)

        # --- 1 and 2: gradient and conditioning at three FD scales ---------
        scales = {}
        for step_size in FD_STEPS:
            sizes = np.sqrt((basis * basis) @ np.full(state.parameter_count, step_size)**2)
            columns, one_sided, unresolved, stencils = [], 0, 0, []
            for direction, size in zip(basis, sizes):
                plus, _ = probe(size * direction, 'jacobian')
                minus, _ = probe(-size * direction, 'jacobian')
                plus = evaluate(plus, production, 'jacobian') if plus is not None else None
                minus = evaluate(minus, production, 'jacobian') if minus is not None else None
                if plus is not None and minus is not None:
                    columns.append((plus.residual - minus.residual) / (2.0 * size))
                    stencils.append('central')
                elif plus is not None:
                    columns.append((plus.residual - base_production.residual) / size)
                    one_sided += 1
                    stencils.append('forward')
                elif minus is not None:
                    columns.append((base_production.residual - minus.residual) / size)
                    one_sided += 1
                    stencils.append('backward')
                else:
                    columns.append(np.zeros_like(base_production.residual))
                    unresolved += 1
                    stencils.append('unresolved')
            matrix = np.column_stack(columns)
            gradient = matrix.T @ base_production.residual
            singular = np.linalg.svd(matrix, compute_uv=False)
            scales[step_size] = dict(
                gradient=gradient, matrix=matrix,
                report=dict(
                    fd_step=step_size, one_sided_columns=one_sided,
                    unresolved_columns=unresolved,
                    stencils={k: stencils.count(k) for k in set(stencils)},
                    gradient_infinity_norm=float(np.linalg.norm(gradient, ord=np.inf)),
                    gradient_two_norm=float(np.linalg.norm(gradient)),
                    singular_value_max=float(singular[0]),
                    singular_value_min=float(singular[-1]),
                    condition_number=float(singular[0] / singular[-1]) if singular[-1] > 0 else None,
                    numerical_rank=int(np.count_nonzero(singular > singular[0] * 1.0e-12))))
            print(json.dumps(scales[step_size]['report']), flush=True)

        reference = scales[FD_STEPS[0]]['gradient']
        record['gradient_stability'] = {}
        for step_size in FD_STEPS[1:]:
            other = scales[step_size]['gradient']
            scale = max(np.linalg.norm(reference), np.linalg.norm(other))
            record['gradient_stability'][f'{FD_STEPS[0]:g}_vs_{step_size:g}'] = (
                float(np.linalg.norm(reference - other) / scale) if scale > 0 else 0.0)
        record['scales'] = [scales[s]['report'] for s in FD_STEPS]
        record['gradient_tolerance'] = float(optimizer.gradient_tolerance)
        record['gradient_below_optimizer_tolerance'] = bool(
            scales[FD_STEPS[0]]['report']['gradient_infinity_norm']
            <= optimizer.gradient_tolerance)

        # --- 3: does anything actually go downhill? ------------------------
        max_steps = optimizer.resolved_max_steps(state.parameter_count)
        reduced_max = np.min(np.where(np.abs(basis) > 1.0e-12,
                                      max_steps / np.maximum(np.abs(basis), 1.0e-12),
                                      np.inf), axis=1)
        gradient = scales[FD_STEPS[0]]['gradient']
        matrix = scales[FD_STEPS[0]]['matrix']
        normal = matrix.T @ matrix
        scaling = np.maximum(np.diag(normal), 1.0)
        directions = {}
        # Negative gradient, normalised then taken out to the trust bound.
        norm = np.linalg.norm(gradient)
        if norm > 0:
            directions['negative_gradient'] = np.clip(
                -gradient / norm * reduced_max, -reduced_max, reduced_max)
        # LM directions across the damping ladder the optimizer would walk.
        damping = optimizer.initial_damping
        for attempt in range(optimizer.max_damping_trials):
            try:
                proposed = np.linalg.solve(normal + damping * np.diag(scaling), -gradient)
            except np.linalg.LinAlgError:
                damping *= optimizer.damping_increase
                continue
            directions[f'levenberg_marquardt_damping_{damping:g}'] = np.clip(
                proposed, -reduced_max, reduced_max)
            damping *= optimizer.damping_increase

        probes = []
        for name, reduced in directions.items():
            for backtrack in range(optimizer.max_backtracks + 1):
                reduced_step = (0.5 ** backtrack) * reduced
                step = basis.T @ reduced_step
                relative = float(np.linalg.norm(step)
                                 / max(np.linalg.norm(state.parameter_vector()), 1.0))
                row = dict(direction=name, backtrack=backtrack,
                           relative_step=relative,
                           below_relative_step_tolerance=bool(
                               relative <= optimizer.relative_step_tolerance))
                if row['below_relative_step_tolerance']:
                    row['verdict'] = 'step_below_tolerance'
                    probes.append(row)
                    continue
                candidate, verdict = probe(step, 'descent_probe')
                if candidate is None:
                    row['verdict'] = verdict
                    probes.append(row)
                    continue
                trial_production = evaluate(candidate, production, 'descent_probe')
                row['production_loss'] = float(trial_production.loss)
                row['production_delta'] = float(base_production.loss - trial_production.loss)
                # The refined evaluation is only spent where production improved.
                if row['production_delta'] > margin:
                    trial_refined = evaluate(candidate, refined, 'descent_probe')
                    row['refined_loss'] = float(trial_refined.loss)
                    row['refined_delta'] = float(base_refined.loss - trial_refined.loss)
                    row['verdict'] = ('descent_at_both_resolutions'
                                      if row['refined_delta'] > margin else 'production_only')
                elif row['production_delta'] > 0.0:
                    # Downhill, but by less than the controller would accept.
                    # Distinct from no descent at all, and the distinction is
                    # the whole question at a plateau.
                    row['verdict'] = 'decrease_below_margin'
                else:
                    row['verdict'] = 'no_decrease'
                probes.append(row)
                print(json.dumps(row), flush=True)
                if row['verdict'] == 'descent_at_both_resolutions':
                    break
        record['descent_probes'] = probes
    except Budget as exc:
        record['budget_stop'] = str(exc)
        print(f'BUDGET STOP: {exc}', flush=True)

    record['work'] = dict(ledger.counts)
    record['solves_used'] = ledger.total
    record['seconds'] = perf_counter() - ledger.started
    record['within_solve_cap'] = ledger.total <= AUDIT_SOLVE_CAP
    accepted = [p for p in record.get('descent_probes', ())
                if p.get('verdict') == 'descent_at_both_resolutions']
    record['feasible_descent_found'] = bool(accepted)
    record['best_descent'] = max((p['production_delta'] for p in accepted), default=None)

    print(f'\n=== stage A: {label} ===')
    print(f"work {record['work']} = {record['solves_used']} solves "
          f"(cap {AUDIT_SOLVE_CAP}), {record['seconds']:.0f} s")
    if 'scales' in record:
        for row in record['scales']:
            print(f"  fd {row['fd_step']:.2e}: |g|inf {row['gradient_infinity_norm']:.4e}  "
                  f"cond {row['condition_number']:.3e}  rank {row['numerical_rank']}"
                  f"/{record['gauge_directions']}  one-sided {row['one_sided_columns']}  "
                  f"unresolved {row['unresolved_columns']}")
        print(f"  gradient stability: {record['gradient_stability']}")
        print(f"  optimizer gradient tolerance {record['gradient_tolerance']:.1e} -> "
              f"terminal gradient below it: {record['gradient_below_optimizer_tolerance']}")
    print(f"  feasible descent found: {record['feasible_descent_found']}")
    if record['feasible_descent_found']:
        print(f"  best production decrease {record['best_descent']:.6e} "
              f"against margin {record['margin']:.3e}")
    return record


if __name__ == '__main__':
    main()
