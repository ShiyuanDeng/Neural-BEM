"""Qualify guarded runtime against the frozen raw diagnostic's operator arrays.

Reuse the expensive discrete reference after verifying its complete artifact
manifest and unchanged operator/forward sources. Recompute runtime sensitivities
and independent FD on current sources, rather than repeating the reference LU
and direction assemblies. The initial raw-reciprocal failure remains immutable.
"""
import argparse
from pathlib import Path
import shutil
import signal
import time
import numpy as np
from . import qualify as q
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.radial_topology import evaluate_multiradial_objective
from sdf_inverse.runtime import inverse_runtime
from gpr_bem_kress.execution import execution


def frequency_errors(actual, reference):
    pairs, frequencies = 24, 4
    result = []
    for fi in range(frequencies):
        indices = np.r_[np.arange(fi, pairs*frequencies, frequencies),
                        np.arange(pairs*frequencies+fi, 2*pairs*frequencies, frequencies)]
        result.append(q.errors(actual[indices], reference[indices]))
    return result


def qualify(bundle, reference):
    frozen = q.sources()
    manifest = q.read(reference/'artifact_manifest.json')
    for name, digest in manifest.items():
        if q.sha(reference/name) != digest:
            raise ValueError('Raw qualification artifact changed: '+name)
    raw = q.read(reference/'qualification.json')
    # Reviewed changes: runtime minimum-node metadata, automatic selection guard,
    # and tests of that guard. The explicit operator/reciprocal bodies are intact.
    changed = ('solvers/sdf_inverse/analytic_jacobian.py', 'solvers/sdf_inverse/runtime.py',
               'pytest/sdf_inverse/test_spd005.py')
    for name, digest in raw['source_sha256'].items():
        if name not in changed and q.sha(q.ROOT/name) != digest:
            raise ValueError('Reference numerical source changed: '+name)
    if raw['error'] is not None or len(raw['rows']) != 58:
        raise ValueError('Complete raw diagnostic required')
    inputs, cases = q.fixtures()
    if inputs != raw['input_sha256']:
        raise ValueError('Qualification inputs changed')
    bundle.mkdir(parents=True, exist_ok=False)
    shutil.copytree(reference, bundle/'raw_diagnostic')
    for name in frozen:
        target = bundle/'measured_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(q.ROOT/name, target)
    q.write(bundle/'manifest.json', dict(source_sha256=frozen, input_sha256=inputs,
        raw_reference_manifest_sha256=q.sha(reference/'artifact_manifest.json'),
        reviewed_changed_files=changed, environment=q.previous.environment()))
    rows = []
    started = time.perf_counter()
    def timeout(*_):
        raise TimeoutError('Combined qualification wall budget')
    old = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, max(.001, 1200-raw['seconds']))
    status, error = 'PASS', None
    try:
        solve = q.p.driver.baseline.iteration01_solve_config()
        with inverse_runtime('reciprocal'), execution(kernels='real_bessel') as work:
            for name, state, data in cases:
                current = {}
                for nodes in (64,128,256,512):
                    saved = np.load(reference/f'{name}_{nodes}.npz')
                    geom = q.p.driver.baseline._geometry_config(nodes)
                    actual, prediction = cartesian_residual_jacobian(state, data, geom, solve_config=solve,
                        directions=saved['directions'])
                    current[nodes] = actual
                    err = q.errors(actual, saved['operator'])
                    by_frequency = frequency_errors(actual, saved['operator'])
                    maximum = max(*err.values(), *(max(e.values()) for e in by_frequency))
                    prediction_error = float(np.linalg.norm(prediction-saved['prediction'])/np.linalg.norm(prediction))
                    passed = (maximum <= 1e-4 and prediction_error <= 2e-11
                              and (nodes != 64 or np.array_equal(actual, saved['operator'])))
                    rows.append(dict(fixture=name, nodes=nodes, check='guarded_same_grid',
                        **err, per_frequency=by_frequency, prediction_error=prediction_error,
                        derivative='operator' if nodes == 64 else 'reciprocal', passed=passed))
                    np.savez(bundle/f'{name}_{nodes}.npz', jacobian=actual, prediction=prediction)
                for low,high in ((128,256),(256,512)):
                    saved = np.load(reference/f'{name}_{high}.npz')
                    err = q.errors(current[low], saved['operator'])
                    by_frequency = frequency_errors(current[low], saved['operator'])
                    rows.append(dict(fixture=name, nodes=low, refined_nodes=high, check='refined',
                        **err, per_frequency=by_frequency,
                        passed=max(*err.values(), *(max(e.values()) for e in by_frequency)) <= 1e-4))
                saved = np.load(reference/f'{name}_256.npz')
                v = np.sum(saved['directions'], axis=0)/np.sqrt(len(saved['directions']))
                geom = q.p.driver.baseline._geometry_config(256)
                values = [evaluate_multiradial_objective(state.incremented(sign*1e-6*v), data, geom,
                          solve_config=solve).residual for sign in (1,-1)]
                fd = (values[0]-values[1])/2e-6
                actual = np.sum(current[256], axis=1)/np.sqrt(len(saved['directions']))
                err = float(np.linalg.norm(actual-fd)/np.linalg.norm(fd))
                rows.append(dict(fixture=name, nodes=256, check='directional_fd', relative=err, passed=err <= 2e-4))
                if name.endswith('handoff'):
                    saved = np.load(reference/f'{name}_full.npz')
                    actual, _ = cartesian_residual_jacobian(state, data, geom, solve_config=solve,
                        directions=saved['basis'])
                    err = q.errors(actual, saved['operator'])
                    by_frequency = frequency_errors(actual, saved['operator'])
                    rows.append(dict(fixture=name, nodes=256, check='full_basis', **err,
                        directions=len(saved['basis']), per_frequency=by_frequency,
                        passed=max(*err.values(), *(max(e.values()) for e in by_frequency)) <= 1e-4))
                q.write(bundle/'progress.json', rows)
                print('GUARDED', name, all(r['passed'] for r in rows if r['fixture']==name), flush=True)
            if not all(row['passed'] for row in rows):
                status = 'FAIL'
            if q.sources() != frozen or any(q.sha(q.ROOT/n) != h for n,h in inputs.items()):
                raise RuntimeError('Guarded qualification source/input drift')
    except Exception as exc:
        status, error = 'FAIL', repr(exc)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    q.write(bundle/'qualification.json', dict(status=status, error=error, rows=rows,
        seconds=time.perf_counter()-started, prior_qualification_seconds=raw['seconds'],
        source_sha256=frozen, input_sha256=inputs, frequencies_hz=q.p.TRAIN,
        raw_reciprocal_status=raw['status'], minimum_reciprocal_nodes=128,
        operator_references_reused=True, counts=work.counts, timings=work.seconds))
    print('GUARDED QUALIFICATION', status, error, flush=True)
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if qualify(args.bundle.resolve(), args.reference.resolve()) == 'PASS' else 1)
