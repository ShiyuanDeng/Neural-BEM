"""Run the pre-registered FI-001 study without inverse fits.

PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
taskset -c 0-5 python -m experiments.frequency_interpolation.study --curve hook_release
"""
import argparse
import os
from pathlib import Path
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np

from bem_inverse import a3_waves, a4_fields, b7_data_jacobian
from bem_inverse.b5_residual import normalize
from bem_inverse.forward_solvers import modal_muller as mm
from bem_inverse.geometry_selection import make_update
from bem_inverse.io import curve_from, digest, read, write
from bem_inverse.physics import Execution
from experiments.benchmark import audit, campaign

ROOT = campaign.ROOT
OUT = ROOT/'results/validation/cleaned_interfaces/FI-001'
BASE = ROOT/'results/validation/cleaned_interfaces'
SPECS = {
    'hook_release': ('hook__c13.3', 'PS-003/H3/runs/hook__c13.3/release_M11.json', 'slider'),
    'hook_final': ('hook__c13.3', 'PS-003/H3/runs/hook__c13.3/fixed_M67.json', 'slider'),
    'peanut_final': ('peanut__c4', 'NR-001/M1/runs/peanut__c4/fixed_M37.json', 'spectral'),
}
COUNTS = (4, 6, 8, 10, 12, 14)


def machine():
    """Record contemporaneous contention; no cross-track timing comparisons."""
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                          '--format=csv,noheader,nounits'], capture_output=True, text=True)
    return dict(load_average=os.getloadavg(), cpu_affinity=sorted(os.sched_getaffinity(0)),
                gpu=gpu.stdout.strip(), memory=Path('/proc/meminfo').read_text(),
                max_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def nodes(x):
    """Endpoint-first discrete Leja ordering; depends only on catalog abscissae."""
    x = (np.asarray(x)-x[0])/(x[-1]-x[0])
    selected = [0, len(x)-1]
    while len(selected) < max(COUNTS):
        scores = np.prod(np.abs(x[:, None]-x[selected]), axis=1)
        scores[selected] = -1
        selected.append(int(np.argmax(scores)))
    return selected


def interpolation_matrix(x, selected):
    """Deterministic barycentric polynomial evaluation, including exact node rows."""
    x = (np.asarray(x)-x[0])/(x[-1]-x[0])
    z = x[selected]
    differences = z[:, None]-z[None, :]
    np.fill_diagonal(differences, 1)
    barycentric = 1/np.prod(differences, axis=1)
    matrix = np.empty((len(x), len(z)))
    for i, value in enumerate(x):
        if i in selected:
            matrix[i] = 0
            matrix[i, selected.index(i)] = 1
        else:
            row = barycentric/(value-z)
            matrix[i] = row/row.sum()
    return matrix


def exact_batch(curve, problem, cutoff, weights, indices):
    """Fresh production context and all setup charged once per selected node set."""
    matrices, fields, jacobians, diagnostics = [], [], [], []
    def observer(kind, data):
        if kind == 'field':
            matrices.append(data['A'])
    context = mm.ModalMuller(Execution(device='cpu', frequency_threads=1), observer=observer)
    started = perf_counter()
    for i in indices:
        prediction = mm.forward_solve(curve, problem.real[i], problem.contrast,
                                      mm.token(cutoff), context=context)
        fields.append(prediction.prediction)
        jacobians.append(context._derivative(prediction._handle, weights))
        diagnostics.append(prediction.diagnostics)
    result = dict(matrices=np.stack(matrices), fields=np.stack(fields),
                  jacobians=np.stack(jacobians), diagnostics=diagnostics, context=context)
    # Include node-array packing in future timings. Original FI-001 receipts
    # stopped immediately before these np.stack calls; preserve those receipts.
    result['seconds'] = perf_counter()-started
    return result


def solve_matrix(matrix, curve, observation, contrast, cutoff, context, weights):
    """Production A3, A4, B7 with an interpolated A2 matrix."""
    settings = context.settings
    geometry = mm.prepare_geometry(curve, cutoff+settings.window_margin, 'cpu', context=context)
    k = observation.wavenumber
    sources, receivers = a3_waves.point_kernels(geometry, k,
        (observation.acquisition.sources, observation.acquisition.receivers),
        tolerance=settings.graf_tolerance, series_loss=settings.series_loss)
    factors = a4_fields.factorize(matrix)
    data = a4_fields.solve_and_predict(matrix, factors, sources, receivers, cutoff,
                                       geometry.band, observation.acquisition.strength)
    reciprocal_rhs = np.vstack((receivers[0][data.test_indices], receivers[1][data.test_indices]))
    state = mm.ModalState(k, k*np.sqrt(contrast), observation.acquisition, cutoff,
                         curve.coefficients, factors, data.traces, reciprocal_rhs)
    jacobian, _ = b7_data_jacobian.reciprocal_jacobian(state, weights)
    return data.prediction, jacobian


def errors(fields, jacobians, reference, problem, selected):
    held = np.array([i for i in range(19) if i not in selected])
    ef = np.linalg.norm(fields-reference['fields'], axis=1)/np.linalg.norm(reference['fields'], axis=1)
    ej = np.linalg.norm(jacobians-reference['jacobians'], axis=1)/np.maximum(
        np.linalg.norm(reference['jacobians'], axis=1), 1e-30)
    observed = np.column_stack([o.scattered for o in problem.real])
    actual = normalize(jacobians.transpose(1, 0, 2), observed, np.ones(19)/19)
    expected = normalize(reference['jacobians'].transpose(1, 0, 2), observed, np.ones(19)/19)
    stacked = np.linalg.norm(actual-expected, axis=0)/np.maximum(np.linalg.norm(expected, axis=0), 1e-30)
    tolerances = np.array(audit.field_tolerances(problem.real))
    return dict(field_relative=ef, jacobian_per_frequency_column_relative=ej,
                jacobian_stacked_column_relative=stacked, worst_field=float(ef[held].max()),
                worst_jacobian=float(stacked.max()), worst_local_jacobian=float(ej[held].max()),
                passed=bool(np.all(ef[held] <= tolerances[held]) and
                            np.max(stacked) <= audit.JACOBIAN_TOLERANCE),
                field_tolerance_ratio=float(np.max(ef[held]/tolerances[held])))


def run(name):
    folder = OUT/name
    if folder.exists():
        raise FileExistsError(f'Preserve previous evidence at {folder}')
    if any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')):
        raise RuntimeError('Use single-thread BLAS')
    case, source, update_name = SPECS[name]
    source = BASE/source
    saved = read(source)
    curve = curve_from(saved['curve'])
    problem = campaign.problem(case)
    cutoff = saved.get('Ku') or saved['nodes']//8
    x = np.array([o.wavenumber for o in problem.real], float)
    order = nodes(x)
    manifest = dict(curve=name, case=case, source=str(source.relative_to(ROOT)),
                    source_sha256=digest(source), source_revision=subprocess.check_output(
                        ['git', 'rev-parse', 'HEAD'], text=True).strip(),
                    prototype_sha256=digest(Path(__file__)), storage_band=curve.band,
                    trace_cutoff=cutoff, update=update_name, update_modes=saved['M'],
                    frequencies_hz=[o.frequency_hz for o in problem.real],
                    wavenumbers=x, node_order=order, node_counts=COUNTS,
                    interpolation='degree n-1 barycentric polynomial in real wavenumber',
                    timing_backend='CPU; one frequency at a time; B6 preparation excluded equally',
                    machine_before=machine())
    write(folder/'manifest.json', manifest)
    try:
        execution = Execution(device='cpu', frequency_threads=1)
        update, _ = make_update(update_name, problem.length_unit_m, execution)
        space = update.prepare(curve, saved['M'], curve.band)
        weights = b7_data_jacobian.normal_velocity_weights(curve.coefficients, space.derivatives)
        del space, update
        reference = exact_batch(curve, problem, cutoff, weights, list(range(19)))
        write(folder/'reference.json', dict(seconds=reference['seconds'],
            diagnostics=reference['diagnostics'], physics=reference['context'].receipt(),
            field_norm=np.linalg.norm(reference['fields'], axis=1),
            jacobian_norm=np.linalg.norm(reference['jacobians'], axis=(1, 2)), machine=machine()))
        # Small complete output receipt allows error analysis without rerunning physics.
        write(folder/'exact_outputs.json', dict(fields=reference['fields'], jacobians=reference['jacobians']))
        rows = []
        for count in COUNTS:
            before = machine()
            selected = order[:count]
            training = exact_batch(curve, problem, cutoff, weights, selected)
            started = perf_counter()
            interpolation = interpolation_matrix(x, selected)
            field_b = interpolation@training['fields']
            jac_b = np.einsum('fn,nrc->frc', interpolation, training['jacobians'])
            b_seconds = training['seconds']+perf_counter()-started
            # Replay one exact node through the low-level held-out path once.
            # This is validation only and does not enter either arm timing.
            if count == COUNTS[0]:
                pf, pj = solve_matrix(training['matrices'][0], curve, problem.real[selected[0]],
                                     problem.contrast, cutoff, training['context'], weights)
                np.testing.assert_allclose(pf, training['fields'][0], rtol=1e-13, atol=1e-14)
                np.testing.assert_allclose(pj, training['jacobians'][0], rtol=1e-13, atol=1e-12)
            # Build weights separately so Arm A pays its own interpolant setup.
            started = perf_counter()
            interpolation_a = interpolation_matrix(x, selected)
            field_a, jac_a = field_b.copy(), jac_b.copy()
            for i in range(19):
                if i in selected:
                    continue
                matrix = np.einsum('n,nij->ij', interpolation_a[i], training['matrices'])
                field_a[i], jac_a[i] = solve_matrix(matrix, curve, problem.real[i], problem.contrast,
                                                   cutoff, training['context'], weights)
            a_seconds = training['seconds']+perf_counter()-started
            for arm, fields, jac, elapsed in [('A', field_a, jac_a, a_seconds), ('B', field_b, jac_b, b_seconds)]:
                row = dict(curve=name, arm=arm, nodes=count, node_indices=selected,
                           exact_seconds=reference['seconds'], interpolated_seconds=elapsed,
                           node_seconds=training['seconds'], saving=1-elapsed/reference['seconds'],
                           errors=errors(fields, jac, reference, problem, selected),
                           training_physics=training['context'].receipt(), machine_before=before,
                           machine_after=machine())
                write(folder/f'{arm}_{count:02d}.json', row)
                rows.append(row)
                print(name, arm, count, row['errors']['passed'], row['errors']['worst_field'],
                      row['errors']['worst_jacobian'], row['saving'], flush=True)
            del training
            write(folder/'summary.json', rows)
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > 6*1024**2:
                raise MemoryError('FI-001 exceeded its 6 GB resident-memory limit')
        write(folder/'completed.json', dict(rows=len(rows), machine_after=machine()))
    except BaseException:
        write(folder/'failed.json', dict(traceback=traceback.format_exc(), machine=machine()))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--curve', choices=SPECS, required=True)
    run(parser.parse_args().curve)
