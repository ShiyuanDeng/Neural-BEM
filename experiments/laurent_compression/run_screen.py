"""LAU-001 screen: derivative-preserving compression of the native Laurent operator.

Stages G0-G4 of docs/iterations/laurent/iteration_01/03_plan.md. Reuses the
qualified solvers read-only through adapters.py; writes only into its own
fresh output directory.
"""
import argparse
import csv
import hashlib
import json
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.bie002_modal_diagnostic.fixtures import inputs
from experiments.modal_muller_research.coefficient_operator import LaurentGeometry
from experiments.modal_muller_research.scattering_library import parameterization

from . import masks as mask_rules
from . import structure
from .adapters import (BLOCK_NAMES, NativeCase, lift, masked_data_derivative, moved_geometry,
                       nodal_reference, operator_at, relative, solve_masked, waves)
from .metrics import (CONTROL_GATES, GATES, Ledger, cancellation_allowance, lifted_residual,
                      objective, objective_derivative, objective_derivative_passes, paired)

LIBRARY_SOURCES = ['coefficient_operator.py', 'coefficient_fields.py', 'coefficient_derivative.py',
                   'modal.py', 'inverse.py', 'scattering_library.py']
ELECTRICAL_SIZES = (2.0, 5.0, 10.0)
CUTOFF_LADDER = (16, 24, 32, 40, 48, 56)
BAND_WIDTHS = (4, 8, 16, 32)
FRACTIONS = (0.10, 0.20, 0.30, 0.50)
SPLIT_LABELS = ('IDENTITY_ONLY', 'VERIFIED_SINGULAR_SPLIT')
SUPPORT_FLOOR = 1e-12
WEIGHT_FLOOR = 1e-14
SCORE_FLOOR = 1e-12
FD_STEPS = (1e-3, 5e-4, 2.5e-4)


def equivalent_radius(geometry):
    """Equivalent-area radius: area = pi * scale^2 * sum_j j |z_j|^2."""
    total = sum(j * abs(v) ** 2 for j, v in geometry.coefficients.items())
    if total <= 0:
        raise ValueError('Non-positive enclosed area; orientation or coefficients are wrong.')
    return geometry.scale * float(np.sqrt(total))


def fixture_set():
    return {
        'circle': LaurentGeometry.circle(.5 + .5j, .05),
        'ellipse': LaurentGeometry.ellipse(.445 + .445j),
        'star': LaurentGeometry.star(.555 + .555j)}


def directions_for(geometry, a_ref):
    """Four training and two held-out real coordinate directions, RMS-normalised."""
    raw = [('train_c2_re', {2: 1 + 0j}), ('train_c2_im', {2: 1j}),
           ('train_cm1_re', {-1: 1 + 0j}), ('train_c3_im', {3: 1j}),
           ('heldout_cm2_re', {-2: 1 + 0j}), ('heldout_c5_re', {5: 1 + 0j})]
    out = []
    for name, dz in raw:
        norm = np.sqrt(sum(abs(v) ** 2 for v in dz.values()))
        factor = a_ref / (geometry.scale * norm)
        out.append((name, {j: v * factor for j, v in dz.items()}))
    return out


def normal_fraction(geometry, dz, samples=512):
    """RMS normal component of the displacement, over RMS total displacement."""
    theta = 2 * np.pi * np.arange(samples) / samples
    z_prime = sum(1j * j * v * np.exp(1j * j * theta) for j, v in geometry.coefficients.items())
    delta = sum(v * np.exp(1j * j * theta) for j, v in dz.items())
    speed = np.abs(z_prime)
    normal = np.real(delta * np.conj(-1j * z_prime)) / np.maximum(speed, 1e-300)
    return float(np.sqrt(np.mean(normal ** 2)) / max(np.sqrt(np.mean(np.abs(delta) ** 2)), 1e-300))


def source_hashes():
    root = Path('experiments/modal_muller_research')
    digest = {}
    for name in LIBRARY_SOURCES:
        path = root / name
        digest[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(Path('experiments/laurent_compression').glob('*.py')):
        digest[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def git_state():
    def run(*args):
        return subprocess.run(args, capture_output=True, text=True).stdout.strip()
    return dict(commit=run('git', 'rev-parse', 'HEAD'),
                branch=run('git', 'branch', '--show-current'),
                dirty=run('git', 'status', '--short'))


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=float) + '\n')


def qualify_cutoff(geometry, acq, frequency, reference, terms, ledger, bandwidth_rule):
    """Smallest ladder cutoff meeting the uncompressed control gates."""
    trail = []
    for cutoff in CUTOFF_LADDER:
        bandwidth = bandwidth_rule(cutoff)
        ledger.charge(assemblies=1, factorizations=1, rhs_batches=1,
                      rhs_columns=len(acq['source_points']))
        case = NativeCase(geometry, acq, frequency, cutoff, bandwidth, terms)
        data = relative(paired(case.y), paired(reference['y']))
        residual = lifted_residual(case.u, reference, cutoff)
        trail.append(dict(cutoff=cutoff, bandwidth=bandwidth, terms=terms,
                          data_error=data, lifted_residual=residual,
                          reconstruction_error=case.reconstruction_error,
                          passes=bool(data <= CONTROL_GATES['receiver']
                                      and residual <= CONTROL_GATES['lifted_residual'])))
        if trail[-1]['passes']:
            return case, trail
    return None, trail


def run(output, stage, dry_run):
    started = perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    ledger = Ledger()
    acq, _ = inputs()
    fixtures = fixture_set()
    anchor = fixtures['star']
    a_ref_anchor = equivalent_radius(anchor)
    light = float(1 / np.sqrt(acq['eps0'] * acq['mu0']))
    epsr_out = acq['exterior']['epsr']
    frequencies = {size: size * light / (2 * np.pi * np.sqrt(epsr_out) * a_ref_anchor)
                   for size in ELECTRICAL_SIZES}

    selected_fixtures = ['circle', 'ellipse'] if stage == 'pilot' else ['circle', 'ellipse', 'star']
    selected_sizes = [2.0] if stage == 'pilot' else [2.0, 5.0, 10.0]

    config = dict(
        experiment='LAU-001', stage=stage, anchor='star',
        a_ref_anchor_m=a_ref_anchor, light_speed=light,
        electrical_sizes=selected_sizes,
        frequencies_hz={str(k): v for k, v in frequencies.items()},
        fixtures=selected_fixtures, cutoff_ladder=list(CUTOFF_LADDER),
        bandwidth_rule='max(96, 2*K_u)', bessel_terms_primary=28, bessel_terms_fallback=48,
        oracle_nodes=[256, 384], band_widths=list(BAND_WIDTHS), fractions=list(FRACTIONS),
        split_labels=list(SPLIT_LABELS), support_floor=SUPPORT_FLOOR,
        bessel_weight_floor=WEIGHT_FLOOR, score_floor=SCORE_FLOOR,
        finite_difference_steps=list(FD_STEPS),
        truth_direction={'2': '0.015*a_ref, inside the training span',
                         '4': '0.010*a_ref, unmodelled by every probed direction'},
        gates=GATES, control_gates=CONTROL_GATES, ceilings=Ledger.CEILINGS,
        acquisition=dict(sources=len(acq['source_points']),
                         receivers=len(acq['receiver_points']),
                         selection='paired diagonal', provenance=acq['provenance'],
                         exterior=acq['exterior'], interior=acq['interior']))
    write_json(output / 'config.json', config)

    if dry_run:
        estimate = dict(native_assemblies=len(selected_fixtures) * len(selected_sizes) * 5
                        + len(selected_fixtures) * 24 + len(selected_fixtures) * len(selected_sizes) * 4 + 12,
                        nodal_solves=len(selected_fixtures) * len(selected_sizes) * 2 + 18,
                        factorizations=len(selected_fixtures) * len(selected_sizes) * 28 + 60)
        write_json(output / 'dry_run.json', dict(config=config, estimate=estimate))
        print(json.dumps(estimate, indent=2))
        return

    reference_rows, structure_rows, decay_rows = [], [], []
    fd_rows, compression_rows, heldout_rows, timing_rows = [], [], [], []
    summary = dict(cases={}, unqualified=[], notes=[])
    bandwidth_rule = lambda cutoff: max(96, 2 * cutoff)

    for fixture_name in selected_fixtures:
        geometry = fixtures[fixture_name]
        a_ref = equivalent_radius(geometry)
        curve = parameterization(geometry, component_id=fixture_name)
        directions = directions_for(geometry, a_ref)
        # Frozen synthetic truth: one unmodelled harmonic, never a training direction.
        # Mode 2 lies in the training span (so the objective gradient is not
        # symmetry-zero) and mode 4 is unmodelled by every probed direction.
        truth_dz = {2: 0.015 * a_ref / geometry.scale, 4: 0.010 * a_ref / geometry.scale}
        truth_curve = parameterization(moved_geometry(geometry, truth_dz, 1.0),
                                       component_id=fixture_name)

        for size in selected_sizes:
            frequency = frequencies[size]
            key = f'{fixture_name}@ka{size:g}'
            tick = perf_counter()
            terms = 28
            ledger.charge(factorizations=2, rhs_batches=2,
                          rhs_columns=2 * len(acq['source_points']))
            oracle = nodal_reference([curve], frequency, acq, 384)
            coarse = nodal_reference([curve], frequency, acq, 256)
            oracle_discrepancy = relative(paired(coarse['y']), paired(oracle['y']))
            ledger.time('oracle', perf_counter() - tick)

            case, trail = qualify_cutoff(geometry, acq, frequency, oracle, terms,
                                         ledger, bandwidth_rule)
            if case is None and size >= 10:
                terms = 48
                case, extra = qualify_cutoff(geometry, acq, frequency, oracle, terms,
                                             ledger, bandwidth_rule)
                trail += extra
            for row in trail:
                reference_rows.append(dict(case=key, fixture=fixture_name, electrical_size=size,
                                           frequency_hz=frequency,
                                           oracle_256_384_error=oracle_discrepancy, **row))
            if case is None:
                summary['unqualified'].append(dict(case=key, reason='no ladder cutoff met the '
                                                   'uncompressed control gates', trail=trail))
                print(f'UNQUALIFIED {key}', flush=True)
                continue

            ledger.charge(rhs_batches=1, rhs_columns=len(acq['source_points']))
            truth = nodal_reference([truth_curve], frequency, acq, 384)
            observed = paired(truth['y'])

            # Analytic derivatives, computed once and reused by every mask.
            tick = perf_counter()
            derivative_objects, direction_meta = [], []
            for name, dz in directions:
                derivative_objects.append(case.derivative(dz))
                direction_meta.append(dict(name=name, normal_fraction=normal_fraction(geometry, dz),
                                           coefficients={str(j): [v.real, v.imag]
                                                         for j, v in dz.items()}))
            ledger.time('analytic_derivatives', perf_counter() - tick)
            training = derivative_objects[:4]

            rows, info = structure.support_report(case, SUPPORT_FLOOR, WEIGHT_FLOOR)
            for row in rows:
                structure_rows.append(dict(case=key, fixture=fixture_name,
                                           electrical_size=size, cutoff=case.cutoff,
                                           bandwidth=case.bandwidth, **row))
            for part, blocks in (('log', case.log_blocks), ('smooth', case.smooth_blocks)):
                for block_name, block in blocks.items():
                    diagonal, box = structure.decay_profile(block, case.cutoff)
                    for entry in diagonal:
                        decay_rows.append(dict(case=key, part=part, block=block_name,
                                               axis='mode_difference', **entry))
                    for entry in box:
                        decay_rows.append(dict(case=key, part=part, block=block_name,
                                               axis='box_radius', **entry))

            summary['cases'][key] = dict(
                fixture=fixture_name, electrical_size=size, frequency_hz=frequency,
                a_ref_m=a_ref, cutoff=case.cutoff, modes_per_trace=2 * case.cutoff + 1,
                bandwidth=case.bandwidth, bessel_terms=terms,
                oracle_256_384_error=oracle_discrepancy,
                reconstruction_error=case.reconstruction_error,
                uncompressed_data_error=relative(paired(case.y), paired(oracle['y'])),
                uncompressed_lifted_residual=lifted_residual(case.u, oracle, case.cutoff),
                assembly_seconds=case.assembly_seconds,
                directions=direction_meta, **info)

            # ---- reference derivative and objective at the anchor ----
            full_mask = np.ones_like(case.a, dtype=bool)
            reference_solved = solve_masked(*case.parts('VERIFIED_SINGULAR_SPLIT'),
                                            full_mask, case.b, case.c)
            ledger.charge(factorizations=1, rhs_batches=1)
            reference_dy = [paired(masked_data_derivative(reference_solved, case, d, full_mask,
                                                          'VERIFIED_SINGULAR_SPLIT'))
                            for d in derivative_objects]
            base_loss, base_residual = objective(paired(case.y), observed)
            reference_gradient = [objective_derivative(base_residual, dy) for dy in reference_dy]
            allowances = [cancellation_allowance(base_residual, dy) for dy in reference_dy]
            summary['cases'][key]['objective'] = dict(
                loss=base_loss, gradient=reference_gradient,
                residual_norm=float(np.linalg.norm(base_residual)))

            # ---- G2: finite differences (shared perturbed assemblies) ----
            if size == selected_sizes[0]:
                perturbed = {}
                for (name, dz), analytic in zip(directions[:4], training):
                    for step in FD_STEPS:
                        pair = []
                        for sign in (+1, -1):
                            ledger.charge(assemblies=1, factorizations=1, rhs_batches=1)
                            # A full case: the perturbed b and C must move too, or
                            # the finite difference is of a different model.
                            pair.append(NativeCase(moved_geometry(geometry, dz, sign * step),
                                                   acq, frequency, case.cutoff,
                                                   case.bandwidth, terms))
                        perturbed[(name, step)] = pair
                        fd = (pair[0].a - pair[1].a) / (2 * step)
                        fd_rows.append(dict(case=key, direction=name, step=step,
                                            check='entrywise_D_vA_vs_centered_difference',
                                            error=relative(analytic['total'], fd)))
                # Discrete correctness of the frozen-mask tangent.
                for label in SPLIT_LABELS:
                    for arm_name, mask in (('FULL', full_mask),
                                           ('DERIVATIVE_AWARE@0.30',
                                            mask_rules.derivative_aware(case, label, 0.30,
                                                                        derivatives=training,
                                                                        floor=SCORE_FLOOR))):
                        solved = solve_masked(*case.parts(label), mask, case.b, case.c)
                        ledger.charge(factorizations=1, rhs_batches=1)
                        for (name, dz), analytic in zip(directions[:4], training):
                            tangent = objective_derivative(
                                objective(paired(solved['y']), observed)[1],
                                paired(masked_data_derivative(solved, case, analytic, mask, label)))
                            step = FD_STEPS[1]
                            values = []
                            for side in perturbed[(name, step)]:
                                moved = solve_masked(*side.parts(label), mask, side.b, side.c)
                                ledger.charge(factorizations=1, rhs_batches=1)
                                values.append(objective(paired(moved['y']), observed)[0])
                            fd_value = (values[0] - values[1]) / (2 * step)
                            index = [d[0] for d in directions].index(name)
                            verdict = objective_derivative_passes(tangent, fd_value,
                                                                  allowances[index])
                            fd_rows.append(dict(
                                case=key, direction=name, step=step, arm=arm_name, split=label,
                                check='frozen_mask_objective_tangent_vs_centered_difference',
                                error=verdict['relative_error'], tangent=tangent,
                                finite_difference=fd_value, passes=verdict['passes'],
                                controlling_term=verdict['controlling_term'],
                                absolute_error=verdict['absolute_error'],
                                allowed=verdict['allowed']))

            # ---- G3: retention arms ----
            for label in SPLIT_LABELS:
                protected, remainder = case.parts(label)
                arms = [('FULL', full_mask, dict(nominal=1.0))]
                for width in BAND_WIDTHS:
                    arms.append(('BAND', mask_rules.band(case, label, width),
                                 dict(width=width, nominal=None)))
                for fraction in FRACTIONS:
                    arms.append(('FORWARD', mask_rules.forward(case, label, fraction),
                                 dict(nominal=fraction)))
                    arms.append(('DERIVATIVE_AWARE',
                                 mask_rules.derivative_aware(case, label, fraction,
                                                             derivatives=training, floor=SCORE_FLOOR),
                                 dict(nominal=fraction)))
                arms.append(('ANALYTIC_SUPPORT',
                             mask_rules.analytic_support(case, label),
                             dict(nominal=None)))
                for arm_name, mask, meta in arms:
                    ledger.charge(factorizations=1, rhs_batches=2,
                                  rhs_columns=len(acq['source_points'])
                                  + len(acq['receiver_points']))
                    solved = solve_masked(protected, remainder, mask, case.b, case.c)
                    y = paired(solved['y'])
                    row = dict(case=key, fixture=fixture_name, electrical_size=size,
                               split=label, arm=arm_name, cutoff=case.cutoff,
                               nominal_fraction=meta.get('nominal'), band_width=meta.get('width'))
                    row.update(mask_rules.retention(mask, case, label))
                    row['derivative_support_union'] = mask_rules.derivative_support_union(
                        mask, case, training, label, SUPPORT_FLOOR)
                    row['data_error'] = relative(y, paired(oracle['y']))
                    row['lifted_residual'] = lifted_residual(solved['state'], oracle, case.cutoff)
                    loss, residual = objective(y, observed)
                    worst_data_derivative = worst_heldout = worst_training = 0.
                    objective_checks = []
                    for meta_d, analytic, ref_dy, ref_g, scale in zip(
                            direction_meta, derivative_objects, reference_dy,
                            reference_gradient, allowances):
                        dy = paired(masked_data_derivative(solved, case, analytic, mask, label))
                        error = relative(dy, ref_dy)
                        worst_data_derivative = max(worst_data_derivative, error)
                        verdict = objective_derivative_passes(
                            objective_derivative(residual, dy), ref_g, scale)
                        objective_checks.append(verdict)
                        if not meta_d['name'].startswith('heldout'):
                            worst_training = max(worst_training, error)
                        if meta_d['name'].startswith('heldout'):
                            worst_heldout = max(worst_heldout, error)
                            heldout_rows.append(dict(case=key, split=label, arm=arm_name,
                                                     nominal_fraction=meta.get('nominal'),
                                                     band_width=meta.get('width'),
                                                     direction=meta_d['name'],
                                                     normal_fraction=meta_d['normal_fraction'],
                                                     data_derivative_error=error, **verdict))
                    row['worst_data_derivative_error'] = worst_data_derivative
                    row['worst_training_derivative_error'] = worst_training
                    row['worst_heldout_derivative_error'] = worst_heldout
                    row['objective_derivative_worst_relative'] = max(
                        v['relative_error'] for v in objective_checks)
                    row['objective_derivative_all_pass'] = bool(
                        all(v['passes'] for v in objective_checks))
                    row['passes_receiver'] = bool(row['data_error'] <= GATES['receiver'])
                    row['passes_residual'] = bool(row['lifted_residual'] <= GATES['lifted_residual'])
                    row['passes_data_derivative'] = bool(
                        worst_training <= GATES['data_derivative'])
                    row['passes_heldout_derivative'] = bool(
                        worst_heldout <= GATES['data_derivative'])
                    # G3 gates on training directions; G4 gates on held-out ones.
                    row['passes_training'] = bool(row['passes_receiver'] and row['passes_residual']
                                                  and row['passes_data_derivative'])
                    row['passes_all'] = bool(row['passes_training']
                                             and row['passes_heldout_derivative'])
                    compression_rows.append(row)

            # ---- G3 COEFFICIENT_WINDOW: the only arm that changes real work ----
            for bandwidth, window_terms in ((case.bandwidth, terms), (96, terms),
                                            (max(2 * case.cutoff, 64), terms),
                                            (max(2 * case.cutoff, 64), 20)):
                if bandwidth < case.cutoff:
                    continue
                ledger.charge(assemblies=1, factorizations=1, rhs_batches=1)
                tick = perf_counter()
                window = NativeCase(geometry, acq, frequency, case.cutoff, bandwidth, window_terms)
                seconds = perf_counter() - tick
                compression_rows.append(dict(
                    case=key, fixture=fixture_name, electrical_size=size,
                    split='N/A', arm='COEFFICIENT_WINDOW', cutoff=case.cutoff,
                    coefficient_bandwidth=bandwidth, bessel_terms=window_terms,
                    assembly_seconds=seconds,
                    data_error=relative(paired(window.y), paired(oracle['y'])),
                    lifted_residual=lifted_residual(window.u, oracle, case.cutoff),
                    matrix_change_vs_qualified=relative(window.a, case.a),
                    passes_receiver=bool(relative(paired(window.y), paired(oracle['y']))
                                         <= GATES['receiver'])))

            # ---- G4: doubled trace dimension, mask rebuilt at the new dimension ----
            doubled = 2 * case.cutoff
            if doubled <= 96:
                ledger.charge(assemblies=1)
                big = NativeCase(geometry, acq, frequency, doubled, bandwidth_rule(doubled), terms)
                big_all = [big.derivative(dz) for _, dz in directions]
                big_training = big_all[:4]
                big_full = np.ones_like(big.a, dtype=bool)
                for label in SPLIT_LABELS:
                    protected, remainder = big.parts(label)
                    ledger.charge(factorizations=1, rhs_batches=1, rhs_columns=2 * len(case.b[0]))
                    big_reference = solve_masked(protected, remainder, big_full, big.b, big.c)
                    big_reference_dy = [paired(masked_data_derivative(big_reference, big, d,
                                                                      big_full, label))
                                        for d in big_all]
                    for fraction in (0.30, 0.50):
                        mask = mask_rules.derivative_aware(big, label, fraction,
                                                           derivatives=big_training,
                                                           floor=SCORE_FLOOR)
                        ledger.charge(factorizations=1, rhs_batches=1,
                                      rhs_columns=2 * len(case.b[0]))
                        solved = solve_masked(protected, remainder, mask, big.b, big.c)
                        errors = [relative(paired(masked_data_derivative(solved, big, d, mask,
                                                                        label)), ref)
                                  for d, ref in zip(big_all, big_reference_dy)]
                        data = relative(paired(solved['y']), paired(oracle['y']))
                        residual = lifted_residual(solved['state'], oracle, doubled)
                        heldout_rows.append(dict(
                            case=key, split=label, arm='DERIVATIVE_AWARE', check='doubled_cutoff',
                            cutoff=doubled, nominal_fraction=fraction,
                            retained_total=float(mask.mean()),
                            retained_count=int(np.count_nonzero(mask)),
                            data_error=data, lifted_residual=residual,
                            worst_training_derivative_error=max(errors[:4]),
                            worst_heldout_derivative_error=max(errors[4:]),
                            passes_receiver=bool(data <= GATES['receiver']),
                            passes_residual=bool(residual <= GATES['lifted_residual']),
                            passes_training=bool(max(errors[:4]) <= GATES['data_derivative']),
                            passes_heldout_derivative=bool(max(errors[4:])
                                                           <= GATES['data_derivative']),
                            passes_all=bool(data <= GATES['receiver']
                                            and residual <= GATES['lifted_residual']
                                            and max(errors) <= GATES['data_derivative'])))

            timing_rows.append(dict(case=key, assembly_seconds=case.assembly_seconds,
                                    oracle_seconds=oracle['seconds'] + coarse['seconds'],
                                    elapsed_seconds=perf_counter() - started))
            print(f'done {key}', flush=True)

    elapsed = perf_counter() - started
    write_csv(output / 'reference_convergence.csv', reference_rows)
    write_csv(output / 'structure.csv', structure_rows)
    write_csv(output / 'decay.csv', decay_rows)
    write_csv(output / 'fd_convergence.csv', fd_rows)
    write_csv(output / 'compression.csv', compression_rows)
    write_csv(output / 'heldout.csv', heldout_rows)
    write_csv(output / 'timings.csv', timing_rows)
    summary['work'] = ledger.report(elapsed)
    write_json(output / 'summary.json', summary)
    write_json(output / 'manifest.json', dict(
        experiment='LAU-001', stage=stage, git=git_state(), source_sha256=source_hashes(),
        environment=dict(python=platform.python_version(), numpy=np.__version__,
                         platform=platform.platform()),
        threads=dict(OMP='1', OPENBLAS='1', MKL='1'),
        acquisition_provenance=acq['provenance'], elapsed_seconds=elapsed))
    print(f'wrote {output} in {elapsed:.1f}s', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('pilot', 'campaign'), default='pilot')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run(args.output, args.stage, args.dry_run)


if __name__ == '__main__':
    main()
