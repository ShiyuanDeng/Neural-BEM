"""LAU-001-R1: qualified compression with independent physical references.

Original LAU-001 artifacts stay immutable. Each invocation uses a fresh output
folder. Gates are unchanged; their enforcement and experimental controls are fixed.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np

from . import masks as mask_rules
from . import structure
from .adapters import (BLOCK_NAMES, LaurentGeometry, NativeCase, inputs,
                       masked_data_derivative, moved_geometry, nodal_reference,
                       parameterization, relative, solve_masked)
from .evaluation import assess, full_solution, qualify_native, reference_bundle
from .metrics import (CONTROL_GATES, GATES, Ledger, cancellation_allowance,
                      lifted_residual, objective, objective_derivative,
                      objective_derivative_passes, paired)

ELECTRICAL_SIZES = (2., 5., 10.)
CUTOFF_LADDER = (16, 24, 32, 40, 48, 56)
BAND_WIDTHS = (4, 8, 16, 32)
FRACTIONS = (.10, .20, .30, .50)
SPLIT_LABELS = ('IDENTITY_ONLY', 'VERIFIED_SINGULAR_SPLIT')
SUPPORT_FLOOR, WEIGHT_FLOOR, SCORE_FLOOR = 1e-12, 1e-14, 1e-12
FD_STEPS = (1e-3, 5e-4, 2.5e-4)


def equivalent_radius(geometry):
    total = sum(j * abs(v)**2 for j, v in geometry.coefficients.items())
    if total <= 0:
        raise ValueError('Non-positive enclosed area.')
    return geometry.scale * float(np.sqrt(total))


def fixture_set():
    star = LaurentGeometry.star(.555 + .555j)
    return dict(circle=LaurentGeometry.circle(.5 + .5j, .05),
                ellipse=LaurentGeometry.ellipse(.445 + .445j), star=star,
                asymmetric_star=moved_geometry(star, {2: .025 + .015j, -2: -.018 + .012j}, 1.))


def directions_for(geometry, a_ref):
    raw = [('train_c2_re', {2: 1 + 0j}), ('train_c2_im', {2: 1j}),
           ('train_cm1_re', {-1: 1 + 0j}), ('train_c3_im', {3: 1j}),
           ('heldout_cm2_re', {-2: 1 + 0j}), ('heldout_c5_re', {5: 1 + 0j})]
    return [(name, {j: v * a_ref / (geometry.scale * np.sqrt(sum(abs(a)**2 for a in dz.values())))
                    for j, v in dz.items()}) for name, dz in raw]


def normal_fraction(geometry, dz, samples=512):
    theta = 2 * np.pi * np.arange(samples) / samples
    tangent = sum(1j * j * v * np.exp(1j * j * theta) for j, v in geometry.coefficients.items())
    delta = sum(v * np.exp(1j * j * theta) for j, v in dz.items())
    normal = np.real(delta * np.conj(-1j * tangent)) / np.abs(tangent)
    return float(np.linalg.norm(normal) / np.linalg.norm(delta))


def validation_acquisition(acq):
    """Half a transmitter-grid step, frozen before scoring; receivers stay fixed."""
    points = np.asarray(acq['source_points'])
    z = points[:, 0] + 1j * points[:, 1]
    moved = .5 + .5j + (z - (.5 + .5j)) * np.exp(1j * np.pi / 24)
    return dict(acq, source_points=np.column_stack((moved.real, moved.imag)).tolist())


def geometry_record(geometry):
    return dict(center=[geometry.center.real, geometry.center.imag], scale=geometry.scale,
                coefficients={str(j): [v.real, v.imag] for j, v in geometry.coefficients.items()})


def source_hashes():
    roots = ['experiments/modal_muller_research', 'experiments/laurent_compression',
             'experiments/bie002_modal_diagnostic', 'solvers/gpr_bem_kress',
             'solvers/ordered_boundary', 'solvers/periodic_kress']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in roots for p in sorted(Path(root).rglob('*.py'))}


def git_state():
    def command(*args):
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    return dict(commit=command('git', 'rev-parse', 'HEAD'),
                branch=command('git', 'branch', '--show-current'),
                dirty=command('git', 'status', '--short'))


def write_csv(path, rows):
    if rows:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=float, allow_nan=False) + '\n')


def native_case(geometry, acq, frequency, cutoff, bandwidth, terms, ledger):
    case = NativeCase(geometry, acq, frequency, cutoff, bandwidth, terms, ledger=ledger)
    if case.reconstruction_error > 1e-13:
        raise RuntimeError('Singular split reconstruction failed.')
    return case


def qualify_cutoff(geometry, acq, frequency, reference, directions, terms, ledger):
    """Fixed B: qualify physical derivatives before any mask can be scored."""
    trail = []
    for cutoff in CUTOFF_LADDER:
        case = native_case(geometry, acq, frequency, cutoff, 96, terms, ledger)
        data = relative(paired(case.y), paired(reference['fine']['y']))
        residual = lifted_residual(case.u, reference['fine'], cutoff)
        row = dict(cutoff=cutoff, bandwidth=96, terms=terms, data_error=data,
                   lifted_residual=residual, reconstruction_error=case.reconstruction_error,
                   derivatives_checked=False, qualified=False)
        if data <= CONTROL_GATES['receiver'] and residual <= CONTROL_GATES['lifted_residual']:
            derivatives = [case.derivative(dz) for dz in directions]
            checks, dy = qualify_native(case, reference, derivatives, ledger)
            row.update(checks, derivatives_checked=True)
            if checks['qualified']:
                trail.append(row)
                return case, derivatives, dy, trail
        trail.append(row)
    return None, None, None, trail


def finite_difference_checks(case, reference, directions, observed, ledger):
    """Independent nodal FD, block/acquisition jets, and frozen objective tangents.

    Save all three h values. Acceptance uses the predeclared smallest step.
    """
    rows = []
    analytic = [case.derivative(dz) for _, dz in directions]
    masks = [(label, arm,
              np.ones_like(case.a, bool) if arm == 'FULL' else mask_rules.derivative_aware(
                  case, label, .30, derivatives=analytic[:4], floor=SCORE_FLOOR))
             for label in SPLIT_LABELS for arm in ('FULL', 'DERIVATIVE_AWARE')]
    bases = {(label, arm): (full_solution(case, ledger) if arm == 'FULL' else
             solve_masked(*case.parts(label), mask, case.b, case.c, ledger))
             for label, arm, mask in masks}
    for index, ((name, dz), derivative) in enumerate(zip(directions, analytic)):
        for step in FD_STEPS:
            sides = [native_case(moved_geometry(case.geometry, dz, sign * step), case.acq,
                                 case.frequency, case.cutoff, case.bandwidth, case.terms, ledger)
                     for sign in (+1, -1)]
            fd_a = (sides[0].a - sides[1].a) / (2 * step)
            size = 2 * case.cutoff + 1
            slices = [(slice(0, size), slice(0, size)), (slice(0, size), slice(size, None)),
                      (slice(size, None), slice(0, size)), (slice(size, None), slice(size, None))]
            block_errors = [relative(derivative['total'][sl], fd_a[sl]) for sl in slices]
            acquisition_errors = [relative(derivative[key], (getattr(sides[0], field)
                                                            - getattr(sides[1], field)) / (2 * step))
                                  for key, field in (('db', 'b'), ('dc', 'c'))]
            rows.append(dict(direction=name, step=step, check='native_A_b_C_centered_difference',
                             error=max(block_errors + acquisition_errors),
                             **dict(zip(BLOCK_NAMES, block_errors)),
                             db_error=acquisition_errors[0], dc_error=acquisition_errors[1],
                             passes=max(block_errors + acquisition_errors) <= 1e-4))
            for label, arm, mask in masks:
                solved = bases[label, arm]
                tangent = objective_derivative(objective(paired(solved['y']), observed)[1],
                    paired(masked_data_derivative(solved, case, derivative, mask, label)))
                values = []
                for side in sides:
                    moved = (full_solution(side, ledger) if arm == 'FULL' else
                             solve_masked(*side.parts(label), mask, side.b, side.c, ledger))
                    values.append(objective(paired(moved['y']), observed)[0])
                finite = (values[0] - values[1]) / (2 * step)
                scale = cancellation_allowance(
                    objective(paired(reference['fine']['y']), observed)[1],
                    paired(reference['dy'][index]))
                check = objective_derivative_passes(tangent, finite, scale)
                rows.append(dict(direction=name, step=step, split=label, arm=arm,
                                 check='frozen_mask_objective_centered_difference', **check))
    # One held-out coordinate per fixture independently checks the nodal oracle.
    name, dz = directions[-1]
    fine_last = None
    for nodes, steps in ((384, FD_STEPS), (256, (FD_STEPS[-1],))):
        for step in steps:
            values = [nodal_reference([parameterization(moved_geometry(case.geometry, dz, sign * step))],
                                      case.frequency, case.acq, nodes, ledger)['y']
                      for sign in (+1, -1)]
            fd = paired((values[0] - values[1]) / (2 * step))
            error = relative(fd, paired(reference['dy'][-1]))
            row = dict(direction=name, step=step, nodes=nodes, check='independent_Kress_FD',
                       error=error, passes=error <= CONTROL_GATES['oracle_derivative'])
            if nodes == 384 and step == FD_STEPS[-1]:
                fine_last = fd
            if nodes == 256:
                row['fd_node_refinement_error'] = relative(fd, fine_last)
                row['passes'] &= row['fd_node_refinement_error'] <= CONTROL_GATES['oracle_derivative']
            rows.append(row)
    return rows, all(r['passes'] for r in rows if r['step'] == FD_STEPS[-1])


def run(output, stage, dry_run):
    started = perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    ledger = Ledger()
    acq, _ = inputs()
    validation_acq = validation_acquisition(acq)
    fixtures = fixture_set()
    a_ref = equivalent_radius(fixtures['star'])
    light = float(1 / np.sqrt(acq['eps0'] * acq['mu0']))
    frequencies = {ka: ka * light / (2 * np.pi * np.sqrt(acq['exterior']['epsr']) * a_ref)
                   for ka in ELECTRICAL_SIZES}
    sizes = [2.] if stage == 'pilot' else list(ELECTRICAL_SIZES)
    hashes = source_hashes()
    write_json(output / 'manifest.json', dict(experiment='LAU-001-R1', stage=stage, git=git_state(),
        source_sha256=hashes, environment=dict(python=platform.python_version(), numpy=np.__version__,
                                              platform=platform.platform()),
        threads={k: os.environ.get(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
        timing_scope='shared host; no speed claim'))
    write_json(output / 'config.json', dict(experiment='LAU-001-R1', stage=stage,
        fixtures={n: geometry_record(g) for n, g in fixtures.items()}, frequencies_hz=frequencies,
        electrical_sizes=sizes, cutoff_ladder=CUTOFF_LADDER, initial_bandwidth=96,
        bessel_terms=[28, 48], oracle_nodes=[256, 384], gates=GATES, control_gates=CONTROL_GATES,
        ceilings=ledger.CEILINGS, fractions=FRACTIONS, bands=BAND_WIDTHS, fd_steps=FD_STEPS,
        acquisition=acq, validation_acquisition=validation_acq,
        refinement='2x K at fixed B; 2x B at fixed K; both as labelled bridge',
        offset_rms=[.005, .01], support_floor=SUPPORT_FLOOR, score_floor=SCORE_FLOOR))
    if dry_run:
        write_json(output / 'dry_run.json', dict(ceilings=ledger.CEILINGS,
            note='Reservations occur in adapters before each assembly, LU, or RHS batch.'))
        return
    tables = {n: [] for n in ('reference_convergence', 'structure', 'fd_convergence',
                              'compression', 'derivatives', 'refinement', 'heldout', 'timings')}
    summary = dict(experiment='LAU-001-R1', status='IN_PROGRESS', cases={}, unqualified=[], notes=[])

    def checkpoint():
        for name, rows in tables.items():
            write_csv(output / f'{name}.csv', rows)
        summary['work'] = ledger.report(perf_counter() - started)
        write_json(output / 'summary.json', summary)

    def record(key, case, reference, observed, derivatives, full_dy, qualified,
               label, arm, mask, table='compression', meta=None, directions=None):
        solved = (full_solution(case, ledger) if arm == 'FULL' else
                  solve_masked(*case.parts(label), mask, case.b, case.c, ledger))
        directions = directions or [d for _, d in directions_for(case.geometry, equivalent_radius(case.geometry))]
        result, detail = assess(case, solved, mask, label, derivatives, reference, observed,
                                full_dy, qualified=qualified, directions=directions)
        comparison_id = f'{table}:{len(tables[table]):05d}'
        row = dict(comparison_id=comparison_id, case=key, split=label, arm=arm,
            cutoff=case.cutoff, bandwidth=case.bandwidth,
            bessel_terms=case.terms, **(meta or {}), **mask_rules.retention(mask, case, label),
            mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
            protected_dense_slots=case.a.size if label == 'VERIFIED_SINGULAR_SPLIT' else 0,
            identity_entries=case.a.shape[0], actual_dense_matrix_bytes=case.a.nbytes, **result)
        row['training_significant_support_union_fraction'] = mask_rules.derivative_support_union(
            mask, case, derivatives[:4], label, SUPPORT_FLOOR)
        tables[table].append(row)
        for d in detail:
            tables['derivatives'].append(dict(comparison_id=comparison_id,
                                              case=key, table=table, split=label, arm=arm,
                                              cutoff=case.cutoff, bandwidth=case.bandwidth,
                                              bessel_terms=case.terms,
                                              mask_sha256=row['mask_sha256'], **(meta or {}), **d))
        mask_file = output / 'masks' / f'{row["mask_sha256"]}.npz'
        if not mask_file.exists():
            np.savez_compressed(mask_file, mask=mask)
        return row

    (output / 'masks').mkdir()
    try:
        for name, geometry in fixtures.items():
            radius = equivalent_radius(geometry)
            named_directions = directions_for(geometry, radius)
            directions = [d for _, d in named_directions]
            truth_geometry = moved_geometry(geometry, {2: .015 * radius / geometry.scale,
                                                      4: .010 * radius / geometry.scale}, 1.)
            for ka in sizes:
                key, frequency = f'{name}@ka{ka:g}', frequencies[ka]
                print(f'qualifying {key}', flush=True)
                reference = reference_bundle(geometry, acq, frequency, directions, ledger)
                if not reference['qualification']['qualified']:
                    summary['unqualified'].append(dict(case=key, reason='nodal oracle',
                                                        **reference['qualification']))
                    checkpoint()
                    continue
                case, derivatives, full_dy, trail = qualify_cutoff(
                    geometry, acq, frequency, reference, directions, 28, ledger)
                if case is None and ka == 10:
                    case, derivatives, full_dy, fallback = qualify_cutoff(
                        geometry, acq, frequency, reference, directions, 48, ledger)
                    trail += fallback
                tables['reference_convergence'].extend(dict(case=key, **r) for r in trail)
                if case is None:
                    summary['unqualified'].append(dict(case=key, reason='native control', trail=trail))
                    checkpoint()
                    continue
                if ka == 10:
                    summary['notes'].append(f'{key}: stress qualification only; masks not swept')
                    checkpoint()
                    continue
                observed = paired(nodal_reference([parameterization(truth_geometry)], frequency,
                                                   acq, 384, ledger)['y'])
                fd_passes = True
                if ka == 2:
                    fd_rows, fd_passes = finite_difference_checks(case, reference, named_directions,
                                                                 observed, ledger)
                    tables['fd_convergence'].extend(dict(case=key, **r) for r in fd_rows)
                summary['cases'][key] = dict(cutoff=case.cutoff, bandwidth=case.bandwidth,
                    candidate_count=case.a.size, oracle=reference['qualification'], native_control=trail[-1],
                    finite_difference_passes=fd_passes if ka == 2 else None,
                    finite_difference_scope='all six directions at ka2 per fixture',
                    directions=[dict(name=n, coefficients={str(j): [v.real, v.imag] for j, v in d.items()},
                                     normal_fraction=normal_fraction(geometry, d)) for n, d in named_directions])
                if not fd_passes:
                    summary['unqualified'].append(dict(case=key, reason='finite difference gate'))
                    checkpoint()
                    continue
                rows, info = structure.support_report(case, SUPPORT_FLOOR, WEIGHT_FLOOR)
                tables['structure'].extend(dict(case=key, **r) for r in rows)
                summary['cases'][key]['structure'] = info
                anchor_masks = {}
                for label in SPLIT_LABELS:
                    arms = [('FULL', mask_rules.full(case, label), {})]
                    arms += [('BAND', mask_rules.band(case, label, w), dict(band_width=w)) for w in BAND_WIDTHS]
                    for fraction in FRACTIONS:
                        for arm, factory in (('FORWARD', mask_rules.forward),
                                             ('DERIVATIVE_AWARE', mask_rules.derivative_aware)):
                            mask = factory(case, label, fraction, derivatives=derivatives[:4], floor=SCORE_FLOOR)
                            arms.append((arm, mask, dict(nominal_fraction=fraction)))
                            if fraction in (.3, .5):
                                anchor_masks[label, arm, fraction] = mask
                    arms.append(('ANALYTIC_SUPPORT', mask_rules.analytic_support(case, label), {}))
                    for arm, mask, meta in arms:
                        record(key, case, reference, observed, derivatives, full_dy, True,
                               label, arm, mask, meta=meta)

                refined_cases = {}
                label = 'VERIFIED_SINGULAR_SPLIT'
                for variant, cutoff, bandwidth in [('trace_only', 2*case.cutoff, case.bandwidth),
                        ('coefficient_only', case.cutoff, 2*case.bandwidth),
                        ('both', 2*case.cutoff, 2*case.bandwidth)]:
                    if cutoff > bandwidth:
                        tables['refinement'].append(dict(case=key, variant=variant,
                                                       qualified=False, reason='K exceeds fixed B'))
                        continue
                    big = native_case(geometry, acq, frequency, cutoff, bandwidth, case.terms, ledger)
                    big_d = [big.derivative(d) for d in directions]
                    control, big_dy = qualify_native(big, reference, big_d, ledger)
                    meta = dict(variant=variant, original_candidate_count=case.a.size)
                    record(key, big, reference, observed, big_d, big_dy, control['qualified'], label,
                           'FULL', mask_rules.full(big, label), 'refinement', meta)
                    if not control['qualified']:
                        continue
                    refined_cases[variant] = big
                    for fraction in (.3, .5):
                        fixed_count = int(np.floor(fraction * (2*case.cutoff+1)**2 + .5))
                        budgets = [('fraction', None), ('absolute', fixed_count)]
                        if cutoff == case.cutoff:
                            budgets = [('fraction_and_absolute', fixed_count)]
                        for budget_kind, count in budgets:
                            for arm, factory in (('FORWARD', mask_rules.forward),
                                                 ('DERIVATIVE_AWARE', mask_rules.derivative_aware)):
                                mask = factory(big, label, fraction, derivatives=big_d[:4],
                                               floor=SCORE_FLOOR, count_per_block=count)
                                record(key, big, reference, observed, big_d, big_dy, True, label, arm,
                                       mask, 'refinement', dict(meta, nominal_fraction=fraction,
                                       budget_kind=budget_kind, retained_to_original_dense=float(mask.sum()/case.a.size)))
                for bandwidth, terms in sorted(set(((max(case.cutoff, 64), case.terms),
                                                     (max(case.cutoff, 64), 20)))):
                    window = native_case(geometry, acq, frequency, case.cutoff, bandwidth, terms, ledger)
                    window_d = [window.derivative(d) for d in directions]
                    record(key, window, reference, observed, window_d, full_dy, True, label, 'FULL',
                           mask_rules.full(window, label), meta=dict(variant='COEFFICIENT_WINDOW',
                                                                    assembly_seconds=window.assembly_seconds))
                held_reference = reference_bundle(geometry, validation_acq, frequency, directions, ledger)
                held_observed = paired(nodal_reference([parameterization(truth_geometry)], frequency,
                                                        validation_acq, 384, ledger)['y'])
                validation_anchors = [('base', case)]
                if 'trace_only' in refined_cases:
                    validation_anchors.append(('trace_only', refined_cases['trace_only']))
                for variant, anchor in validation_anchors:
                    held_case = native_case(geometry, validation_acq, frequency, anchor.cutoff,
                                           anchor.bandwidth, anchor.terms, ledger)
                    held_d = [held_case.derivative(d) for d in directions]
                    held_control, held_dy = qualify_native(held_case, held_reference, held_d, ledger)
                    anchor_d = [anchor.derivative(d) for d in directions]
                    for split in SPLIT_LABELS:
                        for arm, fraction in (('FORWARD', .3), ('DERIVATIVE_AWARE', .3), ('DERIVATIVE_AWARE', .5)):
                            factory = mask_rules.forward if arm == 'FORWARD' else mask_rules.derivative_aware
                            mask = (anchor_masks[split, arm, fraction] if variant == 'base' else
                                    factory(anchor, split, fraction, derivatives=anchor_d[:4], floor=SCORE_FLOOR))
                            record(key, held_case, held_reference, held_observed, held_d, held_dy,
                                   held_control['qualified'], split, arm, mask, 'heldout',
                                   dict(check='new_illuminations', variant=variant, nominal_fraction=fraction))
                if name == 'star' and ka == 5:
                    offset_d = {2: .7 + .2j, -2: -.3 + .4j, 4: .2j}
                    factor = radius / (geometry.scale * np.sqrt(sum(abs(v)**2 for v in offset_d.values())))
                    offset_d = {j: v * factor for j, v in offset_d.items()}
                    for step in (.005, .01):
                        moved = moved_geometry(geometry, offset_d, step)
                        offset_reference = reference_bundle(moved, acq, frequency, directions, ledger)
                        for variant, anchor in validation_anchors:
                            moved_case = native_case(moved, acq, frequency, anchor.cutoff, anchor.bandwidth,
                                                     anchor.terms, ledger)
                            moved_d = [moved_case.derivative(d) for d in directions]
                            moved_control, moved_dy = qualify_native(moved_case, offset_reference, moved_d, ledger)
                            anchor_d = [anchor.derivative(d) for d in directions]
                            for fraction in (.3, .5):
                                mask = mask_rules.derivative_aware(anchor, label, fraction,
                                    derivatives=anchor_d[:4], floor=SCORE_FLOOR)
                                record(key, moved_case, offset_reference, observed, moved_d, moved_dy,
                                       moved_control['qualified'], label, 'DERIVATIVE_AWARE', mask,
                                       'heldout', dict(check='geometry_offset', variant=variant,
                                                      nominal_fraction=fraction, rms_offset=step), directions)
                tables['timings'].append(dict(case=key, native_case_seconds=case.assembly_seconds,
                                              elapsed_seconds=perf_counter()-started))
                checkpoint()
                print(f'done {key}; work={ledger.counts}', flush=True)
        ledger.check_resources()
        summary['status'] = 'COMPLETE'
    except (RuntimeError, ValueError, FloatingPointError) as error:
        summary['status'] = 'INCOMPLETE'
        summary['error'] = str(error)
        raise
    finally:
        summary['source_drift'] = [p for p, digest in hashes.items() if not Path(p).exists()
                                  or hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        if summary['source_drift']:
            summary['status'] = 'INVALID_SOURCE_DRIFT'
        checkpoint()
    print(f'wrote {output} in {perf_counter()-started:.1f}s', flush=True)
    if summary['source_drift']:
        raise RuntimeError('Source changed during the run; measurements are invalid.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('pilot', 'campaign'), default='pilot')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run(args.output, args.stage, args.dry_run)


if __name__ == '__main__':
    main()
