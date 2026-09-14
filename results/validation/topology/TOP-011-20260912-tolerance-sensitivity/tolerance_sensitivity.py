"""TOP-011: how many millimetres of boundary hide inside the 0.003 data tolerance?

Diagnostic only. No source change, no controller default, no new arm, and no
state is advanced or saved as a reconstruction. Truth is read only in a second
pass, after every step has been chosen and measured; nothing here can select a
direction.

Four cycles have now found and fixed four real defects -- the frozen-column
derivative, missing shape capacity, a truncated mode ladder and premature
stopping. Every one improved the training objective and not one improved the
reconstruction. The saved K=9 state satisfies the frozen controller's 0.003
relative-error tolerance many times over while sitting ~12 mm from the truth.

So the question is no longer which defect to fix. It is what that tolerance
actually certifies about geometry. For each right-singular direction of the
reduced Jacobian, and each sign, this measures:

  * the step the *linear* model says reaches relative L2 = 0.003;
  * the largest step the optimizer's own feasible set admits along that ray
    (radius floor, then production, then refined -- geometry checks, not BIE
    solves, so this search is free);
  * the *measured* relative L2 there, bisected down until the measurement
    itself is inside the tolerance, so the reported step is certified by the
    objective and never by the linear model;
  * the boundary displacement in millimetres that step buys, matched Hausdorff
    against the state it started from.

Every probe is also a predicted-versus-actual pair, so the same walk records
where the linear model stops describing the tolerance neighbourhood at all --
which the contract names as a finding in its own right.

Budgets are the plan's, declared before execution, enforced at solver-call
boundaries in separate ledger categories.
"""
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'solvers'))

import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.radial_topology import (
    _minimum_polygon_distance, component_radius_floor, evaluate_multiradial_objective,
    multiradial_geometry_admissible,
)
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, _optimizer_config, component_parameterization,
)
from sdf_inverse.geometry import OrderedSDFGeometryError

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
LADDER = ROOT / 'results/validation/topology/TOP-009-20260912-bandwidth-capacity'
PLATEAU = ROOT / 'results/validation/topology/TOP-010-20260912-stopping-vs-stationarity'
SCENE = 'far-two-stars'

# Declared in the plan before execution.
FD_STEPS = (1.0e-4, 5.0e-5, 2.5e-5)
REFERENCE_FD = FD_STEPS[0]
SOLVE_CAP = 1200
SECONDS_CEILING = 600.0
# The frozen controller tolerance, asserted against the spec below so a spec
# change cannot silently move the thing being measured.
DATA_TOLERANCE = 0.003
# Feasibility search along a ray: halve at most this many times before calling
# the direction refused, then refine the bracket. Geometry checks, not solves.
MAX_HALVINGS = 44
BRACKET_REFINEMENTS = 8
# Measured-tolerance bisection, in solves, once feasibility has been located.
MAX_TOLERANCE_SOLVES = 6
STATES = (('stage4_ladder_endpoint', LADDER / 'stage4_uncapped_ladder.json'),
          ('stageB_restart_plateau', PLATEAU / 'stageB_restart_continuation.json'))


class Budget(Exception):
    """Raised at a solver-call boundary when a declared limit is reached."""


class Ledger:
    """Counts forward solves by category so no call escapes the budget."""

    def __init__(self, cap, seconds):
        self.cap, self.seconds, self.started = cap, seconds, perf_counter()
        self.counts, self.geometry_checks = {}, 0

    @property
    def total(self):
        return sum(self.counts.values())

    @property
    def elapsed(self):
        return perf_counter() - self.started

    def charge(self, category):
        if self.total >= self.cap:
            raise Budget(f'solve cap {self.cap} reached at {self.counts}')
        if self.elapsed >= self.seconds:
            raise Budget(f'{self.seconds:g} s ceiling reached at {self.counts}')
        self.counts[category] = self.counts.get(category, 0) + 1


def polygons(state, spec):
    return [component_parameterization(c).discretize(spec['geometry_samples']).points
            for c in state.components]


def displacement(base_polygons, candidate, spec):
    """Matched two-sided Hausdorff between two states, in metres.

    Against the state the step started from, not against the truth. Components
    keep their stored order through ``incremented``, but the assignment is
    solved anyway so a direction that swaps two components is measured as the
    movement it is rather than as a relabelling.
    """
    other = polygons(candidate, spec)
    table = np.array([[max(_minimum_polygon_distance(a, b).max(),
                           _minimum_polygon_distance(b, a).max()) for b in other]
                      for a in base_polygons])
    rows, columns = linear_sum_assignment(table)
    per_component = [float(table[i, j]) for i, j in zip(rows, columns)]
    return max(per_component), per_component


def tolerance_step(sigma, residual, left_vector, tolerance, sign):
    """Closed-form step to the tolerance under the linear model.

    One training frequency means the normalized residual norm *is* the global
    relative L2 error, so ``|r0 + t*sigma*u|`` is the predicted relative L2
    exactly and the tolerance crossing is a quadratic root, not an estimate.
    """
    projection = float(residual @ left_vector)
    discriminant = projection ** 2 - float(residual @ residual) + tolerance ** 2
    if discriminant < 0.0 or sigma <= 0.0:
        return None
    return float((-projection + sign * np.sqrt(discriminant)) / sigma)


def predicted_relative_l2(residual, sigma, left_vector, t):
    return float(np.linalg.norm(residual + t * sigma * left_vector))


def main():
    spec = benchmark.read(DATA / 'scene_spec.json')
    if spec['controller']['relative_error_tolerance'] != DATA_TOLERANCE:
        raise ValueError('frozen data tolerance moved; this measures the frozen one')
    scene = {s['id']: s for s in spec['scenes']}[SCENE]
    solve = driver.baseline.iteration01_solve_config()
    production = driver.baseline._geometry_config(spec['production_nodes'])
    refined = driver.baseline._geometry_config(spec['refined_nodes'])
    training, _ = benchmark.shared_data(DATA, scene, spec)
    config = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True, bandwidth_promotion=True)
    ledger = Ledger(SOLVE_CAP, SECONDS_CEILING)

    records = []
    for label, path in STATES:
        if not path.exists():
            print(f'skipping {label}: {path.name} not present', flush=True)
            continue
        print(f'\n########## {label} ##########', flush=True)
        state = driver.deserialize_state(benchmark.read(path)['final_state'])
        records.append(Audit(label, state, scene, spec, training, solve, production,
                             refined, config, ledger).run())

    driver.write_json(HERE / 'tolerance_sensitivity.json', dict(
        experiment='TOP-011', scene=SCENE, data_tolerance=DATA_TOLERANCE,
        fd_steps=list(FD_STEPS), reference_fd_step=REFERENCE_FD, solve_cap=SOLVE_CAP,
        seconds_ceiling=SECONDS_CEILING, data_bundle=str(DATA.relative_to(ROOT)),
        solves_used=ledger.total, work=dict(ledger.counts),
        geometry_checks=ledger.geometry_checks, seconds=ledger.elapsed,
        within_solve_cap=ledger.total <= SOLVE_CAP, states=records))


class Audit:
    """One saved state, audited end to end."""

    def __init__(self, label, state, scene, spec, training, solve, production, refined,
                 config, ledger):
        self.label, self.state, self.scene, self.spec = label, state, scene, spec
        self.training, self.solve = training, solve
        self.production, self.refined, self.config = production, refined, config
        self.ledger = ledger
        self.basis = state.gauge_tangent_basis()
        self.optimizer = _optimizer_config(state, config)
        self.base_polygons = polygons(state, spec)
        self.record = dict(state=label, scene=SCENE,
                           modes=[c.maximum_mode for c in state.components],
                           parameters=state.parameter_count,
                           gauge_directions=len(self.basis))

    # --- primitives ------------------------------------------------------
    def evaluate(self, candidate, geometry, category):
        self.ledger.charge(category)
        return evaluate_multiradial_objective(candidate, self.training, geometry,
                                              solve_config=self.solve)

    def feasible(self, candidate):
        """The optimizer's own feasible set, cheapest test first. No BIE solve."""
        self.ledger.geometry_checks += 1
        if any(component_radius_floor(c) < self.config.minimum_component_radius_m
               for c in candidate.components):
            return False, 'radius_floor'
        if not multiradial_geometry_admissible(candidate, self.production,
                                               solve_config=self.solve):
            return False, 'production_inadmissible'
        if not multiradial_geometry_admissible(candidate, self.refined,
                                               solve_config=self.solve):
            return False, 'refined_inadmissible'
        return True, 'ok'

    def at(self, direction, t):
        """Retract a reduced step onto the gauge and test feasibility there."""
        try:
            candidate = self.state.incremented(
                self.basis.T @ (t * direction)).polar_angle_gauge_fixed()[0]
        except (ValueError, OrderedSDFGeometryError):
            return None, 'retract_failed'
        ok, why = self.feasible(candidate)
        return (candidate, 'ok') if ok else (None, why)

    # --- stages ----------------------------------------------------------
    def run(self):
        try:
            self.base()
            self.spectrum()
            self.walks()
            self.breakdown()
        except Budget as exc:
            self.record['budget_stop'] = str(exc)
            print(f'BUDGET STOP: {exc}', flush=True)
        self.score_against_truth()
        self.summarize()
        return self.record

    def base(self):
        base = self.evaluate(self.state, self.production, 'base')
        base_refined = self.evaluate(self.state, self.refined, 'base')
        self.base_evaluation, self.residual = base, np.asarray(base.residual, float)
        self.record.update(
            production_loss=float(base.loss), refined_loss=float(base_refined.loss),
            relative_l2_error=float(base.relative_l2_error),
            residual_entries=int(self.residual.size), data_tolerance=DATA_TOLERANCE,
            tolerance_headroom=DATA_TOLERANCE / float(base.relative_l2_error))
        print(f'{self.label}: relative L2 {base.relative_l2_error:.4e} against tolerance '
              f'{DATA_TOLERANCE} ({self.record["tolerance_headroom"]:.1f}x inside) · '
              f'{len(self.basis)} gauge directions vs {self.residual.size} residual '
              f'entries', flush=True)

    def spectrum(self):
        spectra, matrices = {}, {}
        for step_size in FD_STEPS:
            matrix, report = self.jacobian(step_size)
            matrices[step_size], spectra[step_size] = matrix, report
            print(json.dumps({k: v for k, v in report.items()
                              if k != 'singular_values'}), flush=True)
        self.record['spectra'] = [spectra[s] for s in FD_STEPS]
        reference = np.asarray(spectra[REFERENCE_FD]['singular_values'])
        self.record['spectrum_stability'] = {
            f'{REFERENCE_FD:g}_vs_{s:g}': float(
                np.linalg.norm(reference - np.asarray(spectra[s]['singular_values']))
                / np.linalg.norm(reference)) for s in FD_STEPS[1:]}
        self.left, self.singular, self.right = np.linalg.svd(matrices[REFERENCE_FD],
                                                             full_matrices=False)
        max_steps = self.optimizer.resolved_max_steps(self.state.parameter_count)
        self.reduced_trust = np.min(
            np.where(np.abs(self.basis) > 1.0e-12,
                     max_steps / np.maximum(np.abs(self.basis), 1.0e-12), np.inf), axis=1)

    def jacobian(self, step_size):
        """Feasible-side stencil, identical in construction to the TOP-010 audit."""
        sizes = np.sqrt((self.basis * self.basis)
                        @ np.full(self.state.parameter_count, step_size) ** 2)
        # Columns are taken in the *reduced* gauge coordinates, so the probe
        # direction is the unit vector of that coordinate and ``at`` maps it
        # back through the basis exactly as every other step here does.
        identity = np.eye(len(self.basis))
        columns, one_sided, unresolved = [], 0, 0
        for direction, size in zip(identity, sizes):
            plus, _ = self.at(direction, size)
            minus, _ = self.at(direction, -size)
            plus = self.evaluate(plus, self.production, 'jacobian') if plus is not None else None
            minus = self.evaluate(minus, self.production, 'jacobian') if minus is not None else None
            if plus is not None and minus is not None:
                columns.append((plus.residual - minus.residual) / (2.0 * size))
            elif plus is not None:
                columns.append((plus.residual - self.residual) / size)
                one_sided += 1
            elif minus is not None:
                columns.append((self.residual - minus.residual) / size)
                one_sided += 1
            else:
                columns.append(np.zeros_like(self.residual))
                unresolved += 1
        matrix = np.column_stack(columns)
        singular = np.linalg.svd(matrix, compute_uv=False)
        return matrix, dict(
            fd_step=step_size, one_sided_columns=one_sided, unresolved_columns=unresolved,
            singular_values=[float(v) for v in singular],
            singular_value_max=float(singular[0]), singular_value_min=float(singular[-1]),
            condition_number=float(singular[0] / singular[-1]) if singular[-1] > 0 else None,
            numerical_rank=int(np.count_nonzero(singular > singular[0] * 1.0e-12)))

    def walks(self):
        rows = []
        for rank in range(len(self.singular)):
            for sign in (1.0, -1.0):
                rows.append(self.walk(rank, sign))
                print(json.dumps({k: v for k, v in rows[-1].items()
                                  if k not in ('probes', 'per_component_displacement_m')}),
                      flush=True)
        self.record['walks'] = rows

    def walk(self, rank, sign):
        sigma = float(self.singular[rank])
        direction = np.asarray(self.right[rank], dtype=np.float64)
        left_vector = np.asarray(self.left[:, rank], dtype=np.float64)
        row = dict(rank=rank, sign=int(sign), singular_value=sigma,
                   residual_projection=float(self.residual @ left_vector))
        target = tolerance_step(sigma, self.residual, left_vector, DATA_TOLERANCE, sign)
        if target is None:
            row['verdict'] = 'no_tolerance_crossing'
            return row
        row['linear_tolerance_step'] = target
        # The trust bound is recorded, never imposed: the question is what the
        # data permits, so the answer is reported in units of the bound instead.
        trust = float(np.min(self.reduced_trust / np.maximum(np.abs(direction), 1.0e-30)))
        row.update(trust_bound_step=trust,
                   linear_step_in_trust_bounds=abs(target) / trust if trust > 0 else None)

        candidate, scale, halvings, refusal = self.largest_feasible(direction, target)
        if candidate is None:
            row.update(verdict='refused', refused_by=refusal, halvings=halvings,
                       feasible_step=None)
            return row
        row.update(halvings=halvings, feasibility_binds=bool(halvings),
                   feasibility_refused_by=refusal,
                   feasible_step=float(np.sign(target) * scale),
                   feasible_fraction_of_linear=float(scale / abs(target)))

        probes, accepted, accepted_state = self.certify(direction, target, scale, sigma,
                                                        left_vector)
        row['probes'] = probes
        if accepted is None:
            row.update(verdict='tolerance_binds_below_resolution', permitted_step=None)
            return row

        at_feasible_end = abs(accepted['step']) >= scale * (1.0 - 1.0e-12)
        row.update(
            verdict='measured', permitted_step=accepted['step'],
            permitted_relative_l2=accepted['actual_relative_l2'],
            predicted_relative_l2=accepted['predicted_relative_l2'],
            linear_model_relative_error=accepted['linear_model_relative_error'],
            production_loss=accepted['production_loss'],
            production_loss_ratio=accepted['production_loss']
            / float(self.base_evaluation.loss),
            permitted_step_in_trust_bounds=abs(accepted['step']) / trust if trust > 0 else None,
            binding_constraint=('linear_tolerance_step' if at_feasible_end and not halvings
                                else 'feasible_set' if at_feasible_end else 'measured_tolerance'))
        moved, per_component = displacement(self.base_polygons, accepted_state, self.spec)
        row.update(boundary_displacement_mm=moved * 1.0e3,
                   per_component_displacement_m=per_component)
        return row

    def largest_feasible(self, direction, target):
        """Largest |t| <= |target| the feasible set admits. Geometry checks only."""
        scale, halvings, refusal, candidate = abs(target), 0, None, None
        while halvings <= MAX_HALVINGS:
            candidate, why = self.at(direction, np.sign(target) * scale)
            if candidate is not None:
                break
            refusal, scale, halvings = why, scale * 0.5, halvings + 1
        if candidate is None:
            return None, scale, halvings, refusal
        if halvings:
            low, high = scale, scale * 2.0
            for _ in range(BRACKET_REFINEMENTS):
                middle = 0.5 * (low + high)
                trial, _ = self.at(direction, np.sign(target) * middle)
                if trial is None:
                    high = middle
                else:
                    low, candidate = middle, trial
            scale = low
        return candidate, scale, halvings, refusal

    def certify(self, direction, target, scale, sigma, left_vector):
        """Bisect down until the *measured* relative L2 is inside the tolerance."""
        probes, accepted, accepted_state = [], None, None
        low, high = 0.0, scale
        for attempt in range(MAX_TOLERANCE_SOLVES):
            magnitude = high if attempt == 0 else 0.5 * (low + high)
            t = np.sign(target) * magnitude
            trial, why = self.at(direction, t)
            if trial is None:
                probes.append(dict(step=float(t), verdict=why))
                high = magnitude
                continue
            measured = self.evaluate(trial, self.production, 'tolerance_walk')
            predicted = predicted_relative_l2(self.residual, sigma, left_vector, float(t))
            probe = dict(step=float(t), predicted_relative_l2=predicted,
                         actual_relative_l2=float(measured.relative_l2_error),
                         production_loss=float(measured.loss),
                         linear_model_relative_error=abs(
                             float(measured.relative_l2_error) - predicted)
                         / max(predicted, 1.0e-300))
            probe['inside_tolerance'] = bool(probe['actual_relative_l2'] <= DATA_TOLERANCE)
            probes.append(probe)
            if probe['inside_tolerance']:
                accepted, accepted_state, low = probe, trial, magnitude
                if attempt == 0:
                    break  # the feasible end is already inside; nothing to bisect
            else:
                high = magnitude
        return probes, accepted, accepted_state

    def breakdown(self):
        """Where does the linear model stop describing this neighbourhood?

        Built from the probes the walks already paid for, not from fresh
        solves: every probe is a predicted/actual pair at a known step, which
        is exactly the comparison the contract asks for.
        """
        rows = []
        for walk in self.record.get('walks', ()):
            for probe in walk.get('probes', ()):
                if 'actual_relative_l2' not in probe:
                    continue
                rows.append(dict(
                    rank=walk['rank'], sign=walk['sign'],
                    singular_value=walk['singular_value'], step=probe['step'],
                    fraction_of_feasible_step=abs(probe['step'])
                    / max(abs(walk['feasible_step']), 1.0e-300),
                    predicted_relative_l2=probe['predicted_relative_l2'],
                    actual_relative_l2=probe['actual_relative_l2'],
                    linear_model_relative_error=probe['linear_model_relative_error']))
        self.record['linear_model_breakdown'] = rows
        if rows:
            errors = np.array([r['linear_model_relative_error'] for r in rows])
            ranks = np.array([r['rank'] for r in rows])
            self.record['linear_model_summary'] = dict(
                probes=len(rows),
                median_relative_error=float(np.median(errors)),
                median_relative_error_strong_half=float(np.median(errors[ranks < 17])),
                median_relative_error_weak_half=float(np.median(errors[ranks >= 17])),
                maximum_relative_error=float(errors.max()),
                probes_within_ten_percent=int(np.count_nonzero(errors <= 0.1)))

    def score_against_truth(self):
        """Second pass. Every step above was already chosen and measured."""
        scored = benchmark.geometry_metrics(self.state, self.scene, self.spec)
        rows = []
        for row in sorted((w for w in self.record.get('walks', ())
                           if w.get('boundary_displacement_mm') is not None),
                          key=lambda w: -w['boundary_displacement_mm']):
            direction = np.asarray(self.right[row['rank']], dtype=np.float64)
            candidate, _ = self.at(direction, row['permitted_step'])
            if candidate is None:
                continue
            metrics = benchmark.geometry_metrics(candidate, self.scene, self.spec)
            rows.append(dict(
                rank=row['rank'], sign=row['sign'],
                singular_value=row['singular_value'],
                boundary_displacement_mm=row['boundary_displacement_mm'],
                relative_l2=row['permitted_relative_l2'],
                matched_hausdorff_mm=metrics['maximum_matched_hausdorff_m'] * 1.0e3,
                union_iou=metrics['union_iou']))
        self.record['truth_scores'] = dict(
            state_matched_hausdorff_mm=scored['maximum_matched_hausdorff_m'] * 1.0e3,
            state_union_iou=scored['union_iou'], per_direction=rows,
            best_matched_hausdorff_mm=min((r['matched_hausdorff_mm'] for r in rows),
                                          default=None),
            best_union_iou=max((r['union_iou'] for r in rows), default=None))

    def summarize(self):
        walks = self.record.get('walks', ())
        moved = [w['boundary_displacement_mm'] for w in walks
                 if w.get('boundary_displacement_mm') is not None]
        weak = [w['boundary_displacement_mm'] for w in walks
                if w.get('boundary_displacement_mm') is not None and w['rank'] >= 17]
        strong = [w['boundary_displacement_mm'] for w in walks
                  if w.get('boundary_displacement_mm') is not None and w['rank'] < 17]
        gate_mm = self.spec['gates']['maximum_matched_hausdorff_m'] * 1.0e3
        self.record['summary'] = dict(
            boundary_gate_mm=gate_mm,
            directions_permitting_more_than_the_gate=sum(1 for v in moved if v > gate_mm),
            directions_walked=len(walks), directions_measured=len(moved),
            refused=sum(1 for w in walks if w.get('verdict') == 'refused'),
            maximum_permitted_displacement_mm=max(moved) if moved else None,
            median_permitted_displacement_mm=float(np.median(moved)) if moved else None,
            minimum_permitted_displacement_mm=min(moved) if moved else None,
            median_strong_half_displacement_mm=float(np.median(strong)) if strong else None,
            median_weak_half_displacement_mm=float(np.median(weak)) if weak else None,
            binding_constraints={c: sum(1 for w in walks if w.get('binding_constraint') == c)
                                 for c in ('linear_tolerance_step', 'feasible_set',
                                           'measured_tolerance')})
        self.record['work'] = dict(self.ledger.counts)
        self.record['solves_used'] = self.ledger.total
        self.record['seconds'] = self.ledger.elapsed
        summary, truth = self.record['summary'], self.record['truth_scores']
        print(f"\n=== {self.label} ===")
        print(f"  {summary['directions_measured']} directions measured, "
              f"{summary['refused']} refused, binding {summary['binding_constraints']}")
        if summary['maximum_permitted_displacement_mm'] is not None:
            print(f"  boundary movement permitted inside the 0.003 tolerance: max "
                  f"{summary['maximum_permitted_displacement_mm']:.3f} mm, median "
                  f"{summary['median_permitted_displacement_mm']:.3f} mm, min "
                  f"{summary['minimum_permitted_displacement_mm']:.3f} mm")
            print(f"  strong half median {summary['median_strong_half_displacement_mm']:.3f} mm"
                  f" · weak half median {summary['median_weak_half_displacement_mm']:.3f} mm")
            print(f"  {summary['directions_permitting_more_than_the_gate']} of "
                  f"{summary['directions_measured']} directions permit more movement "
                  f"than the {gate_mm:.3f} mm boundary gate itself")
        if 'linear_model_summary' in self.record:
            model = self.record['linear_model_summary']
            print(f"  linear model relative error: median "
                  f"{model['median_relative_error']:.3f}, strong half "
                  f"{model['median_relative_error_strong_half']:.3f}, weak half "
                  f"{model['median_relative_error_weak_half']:.3f}, worst "
                  f"{model['maximum_relative_error']:.1f}")
        print(f"  the state itself sits {truth['state_matched_hausdorff_mm']:.3f} mm from "
              f"the truth, IoU {truth['state_union_iou']:.4f}")
        print(f"  work {self.record['work']} = {self.record['solves_used']} solves, "
              f"{self.ledger.geometry_checks} geometry checks, {self.ledger.elapsed:.0f} s")


if __name__ == '__main__':
    main()
