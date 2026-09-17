"""Frozen saved-state qualification, including event and difficult geometries."""
import argparse
from pathlib import Path
import signal
import time
import numpy as np
from experiments.spd004_pipeline_readiness import run as previous
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.radial_topology import evaluate_multiradial_objective
from gpr_bem_kress.execution import execution

ROOT, p = previous.ROOT, previous.p
read, write, sha, HISTORY = previous.read, previous.write, previous.sha, previous.HISTORY


def sources():
    paths = [*Path(__file__).parent.glob('*.py'), ROOT/'pytest/sdf_inverse/test_spd005.py']
    return {**previous.sources(), **{str(x.relative_to(ROOT)):sha(x) for x in paths}}


def errors(actual, reference):
    delta = np.linalg.norm(actual-reference, axis=0)
    norms = np.linalg.norm(reference, axis=0)
    return dict(relative=float(np.linalg.norm(delta)/np.linalg.norm(reference)),
                worst_column=float(np.max(delta/np.maximum(norms, 1e-12*np.max(norms)))))


def fixtures():
    inputs, cases = {}, []
    for scene in ('death', 'split', 'merge', 'central-ellipse-star', 'far-two-stars'):
        observed_path = HISTORY/'inputs'/scene/'training_observations.json'
        observed = read(observed_path)
        data = p.training_data(p.TRAIN, np.array(observed['observed_real'])+1j*np.array(observed['observed_imag']))
        inputs[str(observed_path.relative_to(ROOT))] = sha(observed_path)
        if scene in ('death', 'split', 'merge'):
            trajectory = HISTORY/'runs'/scene/'topology/trajectory.jsonl'
            import json
            rows = [json.loads(line) for line in trajectory.read_text().splitlines()]
            inputs[str(trajectory.relative_to(ROOT))] = sha(trajectory)
            selected = [r for r in rows if r['label'].startswith('before ') or r['label'].endswith(' accepted')]
            for row in selected:
                cases.append((scene+'_'+row['label'].replace(' ', '_'), p.driver.deserialize_state(row['state']), data))
        else:
            path = HISTORY/'runs'/scene/'handoff.json'
            inputs[str(path.relative_to(ROOT))] = sha(path)
            cases.append((scene+'_handoff', p.driver.deserialize_state(read(path)['state']), data))
    return inputs, cases


def qualify(bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    frozen = sources()
    inputs, cases = fixtures()
    write(bundle/'manifest.json', dict(source_sha256=frozen, input_sha256=inputs,
                                      environment=previous.environment()))
    import shutil
    for name in {*frozen, *inputs}:
        destination = bundle/'snapshot'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    rows = []
    started = time.perf_counter()
    def timeout(*_):
        raise TimeoutError('Qualification wall cap 1200 seconds')
    old = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 1200)
    status, error = 'PASS', None
    try:
        solve = p.driver.baseline.iteration01_solve_config()
        with execution(kernels='real_bessel') as work:
            for name, state, data in cases:
                basis = state.gauge_tangent_basis()
                indices = sorted(set((0, len(basis)//2, len(basis)-1)))
                directions = basis[indices]
                records = {}
                for nodes in (64, 128, 256, 512):
                    geom = p.driver.baseline._geometry_config(nodes)
                    tick = time.perf_counter()
                    reciprocal, prediction = cartesian_residual_jacobian(state, data, geom,
                        solve_config=solve, directions=directions, method='reciprocal')
                    operator, reference = cartesian_residual_jacobian(state, data, geom,
                        solve_config=solve, directions=directions, method='operator')
                    err = errors(reciprocal, operator)
                    records[nodes] = (reciprocal, operator)
                    row = dict(fixture=name, nodes=nodes, check='selected_same_grid', directions=indices,
                        **err, prediction_relative=float(np.linalg.norm(prediction-reference)/np.linalg.norm(reference)),
                        passed=max(err.values()) <= 1e-4, seconds=time.perf_counter()-tick)
                    rows.append(row)
                    np.savez(bundle/f'{name}_{nodes}.npz', reciprocal=reciprocal, operator=operator,
                             prediction=prediction, directions=directions)
                    print('QUALIFY', name, nodes, err, row['passed'], flush=True)
                    write(bundle/'progress.json', rows)
                for low, high in ((64,128), (256,512)):
                    err = errors(records[low][0], records[high][1])
                    rows.append(dict(fixture=name, nodes=low, refined_nodes=high, check='refined',
                                     **err, passed=max(err.values()) <= 1e-4))
                geom = p.driver.baseline._geometry_config(256)
                v = np.sum(directions, axis=0)/np.sqrt(len(directions))
                values = [evaluate_multiradial_objective(state.incremented(sign*1e-6*v), data, geom,
                          solve_config=solve).residual for sign in (1,-1)]
                fd = (values[0]-values[1])/2e-6
                actual = np.sum(records[256][0], axis=1)/np.sqrt(len(directions))
                err = float(np.linalg.norm(actual-fd)/np.linalg.norm(fd))
                rows.append(dict(fixture=name, nodes=256, check='directional_fd', step=1e-6,
                                 relative=err, passed=err <= 2e-4))
                # Full reachable production basis for both difficult handoffs.
                if name.endswith('handoff'):
                    actual, _ = cartesian_residual_jacobian(state, data, geom, solve_config=solve,
                        directions=basis, method='reciprocal')
                    reference, _ = cartesian_residual_jacobian(state, data, geom, solve_config=solve,
                        directions=basis, method='operator')
                    err = errors(actual, reference)
                    rows.append(dict(fixture=name, nodes=256, check='full_basis', directions=len(basis),
                                     **err, passed=max(err.values()) <= 1e-4))
                    np.savez(bundle/f'{name}_full.npz', reciprocal=actual, operator=reference, basis=basis)
            if not all(row['passed'] for row in rows):
                status = 'FAIL'
            if sources() != frozen or any(sha(ROOT/n) != h for n,h in inputs.items()):
                raise RuntimeError('Qualification source or input drift')
    except Exception as exc:
        status, error = 'FAIL', repr(exc)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    write(bundle/'qualification.json', dict(status=status, error=error, rows=rows,
        seconds=time.perf_counter()-started, counts=work.counts, timings=work.seconds,
        frequencies_hz=p.TRAIN, source_sha256=frozen, input_sha256=inputs))
    print('QUALIFICATION', status, error, flush=True)
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if qualify(args.bundle.resolve()) == 'PASS' else 1)
