"""Bounded current-source qualification on archived topology states."""
import argparse
from pathlib import Path
import shutil
from time import perf_counter
import numpy as np
from experiments.spd005_reciprocal import qualify as prior
from experiments.spd004_pipeline_readiness import run as previous
from sdf_inverse.compiled_jacobian import CompiledEvaluator, relative_columns
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.radial_topology import evaluate_multiradial_objective
from sdf_inverse.runtime import inverse_runtime
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution

ROOT, HISTORY, p = previous.ROOT, previous.HISTORY, previous.p
read, write, sha = previous.read, previous.write, previous.sha


def sources():
    fixture_source = Path(prior.__file__).resolve()
    return {**previous.sources(), str(fixture_source.relative_to(ROOT)):sha(fixture_source),
            'pytest/sdf_inverse/test_spd006.py':sha(ROOT/'pytest/sdf_inverse/test_spd006.py'),
            **{str(x.relative_to(ROOT)):sha(x) for x in Path(__file__).parent.glob('*.py')}}


def fixtures():
    inputs, cases = prior.fixtures()
    for scene in ('death', 'split', 'merge'):
        path = HISTORY/'runs'/scene/'handoff.json'
        observed_path = HISTORY/'inputs'/scene/'training_observations.json'
        for item in (path, observed_path): inputs[str(item.relative_to(ROOT))] = sha(item)
        observed = read(observed_path)
        data = p.training_data(p.TRAIN, np.array(observed['observed_real'])+1j*np.array(observed['observed_imag']))
        cases.append((scene+'_capacity_handoff', p.driver.deserialize_state(read(path)['state']), data))
    return inputs, cases


def qualify(bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    frozen = sources(); inputs, cases = fixtures()
    for name in {*frozen, *inputs}:
        destination = bundle/'snapshot'/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, destination)
    ledger = previous.m.Ledger(cap=2000, seconds=1800)
    rows, status, error = [], 'PASS', None
    started = perf_counter()
    solve = p.driver.baseline.iteration01_solve_config()
    try:
        with inverse_runtime('reciprocal'), execution(kernels='real_bessel'), ledger.instrument(), collect_work() as passive:
            for name, state, data in cases:
                directions = state.gauge_tangent_basis()
                for nodes in (256, 512):
                    tick = perf_counter(); geometry = p.driver.baseline._geometry_config(nodes)
                    evaluator = CompiledEvaluator(data, geometry, solve, directions, allow_single=True)
                    actual = evaluator.evaluate(state)
                    if actual is None:
                        raise ValueError('Raw compiled qualification fallback: '+name+str(evaluator.snapshot()))
                    reference, prediction = cartesian_residual_jacobian(state, data, geometry,
                        solve_config=solve, directions=directions, method='reciprocal')
                    errors = relative_columns(actual['jacobian'], reference)
                    forward = np.linalg.norm(actual['prediction']-prediction, axis=0)/np.linalg.norm(prediction, axis=0)
                    row = dict(fixture=name, nodes=nodes, directions=len(directions), check='full_gauge',
                        per_frequency_prediction_relative=forward.tolist(), jacobian_relative=errors[0], worst_column=errors[1],
                        passed=bool(max(forward)<=1e-10 and errors[0]<=1e-6 and errors[1]<=1e-5),
                        seconds=perf_counter()-tick, compiled=evaluator.snapshot())
                    rows.append(row)
                    np.savez(bundle/f'{name}_{nodes}.npz', compiled_jacobian=actual['jacobian'], reference=reference,
                             prediction=actual['prediction'], reference_prediction=prediction, directions=directions)
                    print('QUALIFY', name, nodes, row['passed'], max(forward), errors, flush=True)
                    write(bundle/'progress.json', rows)
                    if not row['passed']:
                        raise ValueError('Full gauge qualification failed: '+name)
                    if nodes == 256:
                        v = np.sum(directions, axis=0)/np.sqrt(len(directions))
                        values = [evaluate_multiradial_objective(state.incremented(sign*1e-6*v), data,
                            geometry, solve_config=solve).residual for sign in (1, -1)]
                        fd = (values[0]-values[1])/2e-6
                        analytic = np.sum(actual['jacobian'], axis=1)/np.sqrt(len(directions))
                        error_fd = float(np.linalg.norm(analytic-fd)/np.linalg.norm(fd))
                        rows.append(dict(fixture=name, nodes=nodes, check='directional_fd', relative=error_fd,
                                         passed=error_fd<=2e-4))
                        if error_fd>2e-4:
                            raise ValueError('Directional FD qualification failed: '+name)
            if sources()!=frozen or any(sha(ROOT/name)!=h for name,h in inputs.items()):
                raise RuntimeError('Qualification source/input drift')
    except Exception as exc:
        status, error = 'FAIL', repr(exc)
    write(bundle/'qualification.json', dict(status=status, error=error, rows=rows,
        seconds=perf_counter()-started, source_sha256=frozen, input_sha256=inputs,
        work=ledger.snapshot(), passive_work=passive.snapshot(), environment=previous.environment()))
    if status!='PASS': raise RuntimeError(error)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--bundle', type=Path, required=True)
    qualify(parser.parse_args().bundle.resolve())
