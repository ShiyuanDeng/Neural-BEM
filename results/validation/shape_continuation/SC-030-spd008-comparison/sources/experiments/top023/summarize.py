"""Independent saved-array TOP-023 replay; no solver imports or calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.top019 import summarize as saved

read, write, digest, state_hash = saved.read, saved.write, saved.digest, saved.state_hash


def vector(state):
    return np.concatenate([c['parameters'] for c in state])


def complex_array(record):
    return np.asarray(record['real'])+1j*np.asarray(record['imag'])


def close(a, b):
    np.testing.assert_allclose(a, b, rtol=1e-9, atol=1e-12)


def verify(output):
    manifest, contract, inputs = [read(output/n) for n in ('manifest.json', 'contract.json', 'inputs.json')]
    saved.verify_inputs(output, manifest)
    for name, sha in read(output/'artifact_manifest.json').items(): assert digest(output/name) == sha, name
    assert contract['experiment'] == 'TOP-023' and contract['solve_cap'] == 600 and contract['worst_case_calls'] == 580
    assert contract['frequencies_hz'] == saved.TRAIN and inputs['state_sha256'] == state_hash(inputs['state'])
    result = read(output/'result.json')
    assert not result['inverse_executed'] and not result['full_suite_released']
    work = result['work']
    for field in ('attempted', 'completed', 'failed'):
        assert sum(work[field].values()) == sum(work['per_frequency_'+field].values())
    assert work['total_attempted'] == sum(work['attempted'].values()) <= 600
    assert work['total_attempted'] == sum(work['completed'].values())+sum(work['failed'].values())
    assert work['active_wall_seconds'] <= 1201
    verification = dict(status='PASS', new_physical_solves=0, source_files=len(manifest['source_sha256']),
        charged_calls=work['total_attempted'], operational_improvement=False)
    if not (output/'model.json').exists():
        assert result['status'] != 'COMPLETED_DIAGNOSTIC'
        return verification, []
    model, predictions, arms = [read(output/n) for n in ('model.json', 'predictions.json', 'arms.json')]
    records, aliases = predictions['records'], predictions['aliases']
    observed = np.array(inputs['training']['observed_real'])+1j*np.array(inputs['training']['observed_imag'])
    def residual(value):
        scaled = (value-observed)/np.linalg.norm(observed, axis=0)[None, :]/2
        return np.r_[scaled.real.ravel(), scaled.imag.ravel()]
    def prediction(label): return complex_array(records[aliases[label]]['prediction'])
    for record in records.values():
        assert record['state_sha256'] == state_hash(record['state'])
        assert complex_array(record['prediction']).shape == (24, 4)
    if not sum(work['failed'].values()):
        measured = Counter()
        for row in records.values():
            if row['origin'] == 'new': measured[row['category']] += 4
        assert dict(measured) == work['completed']
    basis = np.asarray(model['basis']); close(basis@basis.T, np.eye(34))
    assert model['state_sha256'] == inputs['state_sha256']
    bases = {n: residual(prediction('base:'+str(n))) for n in (256, 512)}
    for n in bases:
        close(prediction('base:'+str(n)), complex_array(inputs['base_predictions'][str(n)]))
        close(bases[n], model['base_residuals'][str(n)])
    for key, estimate in model['estimates'].items():
        i, h, n = key.split(':'); i, h, n = int(i), float(h), int(n)
        sides = {int(s): residual(prediction(label)) for s, label in estimate['side_labels'].items()}
        for sign, label in estimate['side_labels'].items():
            close(vector(records[aliases[label]]['state'])-vector(inputs['state']), int(sign)*h*basis[i])
        if len(sides) == 2: value, stencil = (sides[1]-sides[-1])/(2*h), 'central'
        elif 1 in sides: value, stencil = (sides[1]-bases[n])/h, 'forward'
        else: value, stencil = (bases[n]-sides[-1])/h, 'backward'
        close(value, estimate['derivative']); assert stencil == estimate['stencil']
    if 'jacobian' not in model:
        assert result['status'] != 'COMPLETED_DIAGNOSTIC'
        return verification, arms
    matrix = np.column_stack([model['estimates'][f'{i}:0.0001:256']['derivative'] for i in range(34)])
    close(matrix, model['jacobian'])
    gradient = matrix.T@bases[256]
    close(gradient, model['reduced_gradient']); close(np.linalg.svd(matrix, compute_uv=False), model['singular_values'])
    original = basis@np.asarray(inputs['saved_gradient']['coefficient_gradient'])
    close(original, model['saved_reduced_gradient'])
    assert model['gradient_replay_pass'] == bool(np.allclose(gradient, original, rtol=1e-5, atol=1e-8))
    first = int(np.argmax(np.abs(original))); selected = [first, 33 if first != 33 else 0]
    assert model['selected_rows'] == selected
    if 'repeat' in aliases:
        repeat = float(np.linalg.norm(residual(prediction('repeat'))-bases[256]))
        close(repeat, model['repeatability_residual_norm'])
        for row in model['selected_direction_checks']:
            i = row['index']; assert i in selected and row['normal_rms_per_unit_coefficient'] > 1e-10
            d = lambda n, h: np.asarray(model['estimates'][f'{i}:{h:g}:{n}']['derivative'])
            floor = max(repeat, 64*np.finfo(float).eps, 5e-5*float(np.linalg.norm(d(256, 5e-5)-d(512, 5e-5))))
            for check in row['checks']:
                n = check['nodes']; norm = np.linalg.norm(d(n, 5e-5))
                relative = np.linalg.norm(d(n, 1e-4)-d(n, 5e-5))/norm if norm > 0 else None
                signal = 5e-5*norm
                assert check['passed'] == bool(relative is not None and np.isfinite(relative) and relative <= .25 and signal >= 5*floor)
                if relative is not None: close(relative, check['relative_scale_discrepancy'])
                close(signal, check['half_step_residual_signal']); close(floor, check['numerical_floor'])
            assert row['passed'] == all(c['passed'] for c in row['checks'])
    assert model['selected_directions_qualified'] == (len(model['selected_direction_checks']) == 2 and
        all(c['passed'] for c in model['selected_direction_checks']))
    normal = matrix.T@matrix; scaling = np.maximum(np.diag(normal), 1.)
    maximum = np.asarray(inputs['optimizer']['max_steps'])
    bounds = np.min(np.where(np.abs(basis)>1e-12, maximum/np.maximum(np.abs(basis), 1e-12), np.inf), axis=1)
    for arm, damping in zip(arms, contract['dampings']):
        assert arm['damping'] == damping
        if 'raw_reduced_step' not in arm:
            assert arm['status'] == 'NOT_STARTED'; continue
        raw = np.linalg.solve(normal+damping*np.diag(scaling), -gradient)
        reduced = np.clip(raw, -bounds, bounds); coefficient = basis.T@reduced
        close(raw, arm['raw_reduced_step']); close(reduced, arm['reduced_step']); close(coefficient, arm['coefficient_step'])
        close(bounds, arm['reduced_bounds']); close(scaling, arm['normal_scaling'])
        assert arm['active_bounds'] == (np.abs(raw)>bounds).tolist()
        assert len(arm['attempts']) <= 8
        accepted = []
        for item in arm['attempts']:
            j = item['backtrack']; step = 2.**-j*reduced
            close(item['coefficient_step'], 2.**-j*coefficient)
            close(item['relative_step'], np.linalg.norm(2.**-j*coefficient)/max(np.linalg.norm(vector(inputs['state'])), 1.))
            if 'losses' not in item: continue
            assert item['state_sha256'] == state_hash(item['state'])
            close(vector(item['state'])-vector(inputs['state']), item['coefficient_step'])
            values = {n: prediction(item['prediction_labels'][str(n)]) for n in (256, 512)}
            losses = {n: .5*float(residual(value)@residual(value)) for n, value in values.items()}
            for n in losses:
                close(losses[n], item['losses'][str(n)])
                assert records[aliases[item['prediction_labels'][str(n)]]]['state_sha256'] == item['state_sha256']
            discrepancy = np.linalg.norm(values[256]-values[512], axis=0)/np.linalg.norm(values[512], axis=0)
            close(discrepancy, item['prediction_discrepancy'])
            numerical = bool(np.all(discrepancy <= np.array([1e-5, 1e-7, 1e-7, 1e-7])))
            assert item['numerically_qualified'] == numerical
            dp, dr = [inputs['base_objectives'][str(n)]-losses[n] for n in (256, 512)]
            margin = max(1e-14+1e-8*inputs['base_objectives'][str(n)] for n in (256, 512))
            uncertainty = 5*abs(dp-dr)
            close([dp, dr, margin, uncertainty], [item[k] for k in ('production_gain','refined_gain','margin','disagreement_allowance')])
            assert item['accepted'] == bool(numerical and min(dp, dr)>margin+uncertainty)
            close(item['linear_predicted_gain'], -gradient@step)
            close(item['quadratic_predicted_gain'], -gradient@step-.5*np.linalg.norm(matrix@step)**2)
            if item['accepted']: accepted.append(item)
        assert len(accepted) <= 1
        if accepted:
            assert accepted[0] == arm['attempts'][-1] and arm['accepted']['state_sha256'] == accepted[0]['state_sha256']
            close(arm['accepted']['production_gain'], accepted[0]['production_gain'])
        if arm['status'] == 'COMPLETE': assert arm['candidate_calls'] == work['attempted'].get('candidate_'+arm['label'], 0)
    if result['status'] == 'COMPLETED_DIAGNOSTIC':
        assert len(arms) == 4 and all(a['status'] == 'COMPLETE' for a in arms)
        assert model['gradient_replay_pass'] and model['selected_directions_qualified'] and result['sources_and_inputs_unchanged']
        control = arms[0]
        eligible = [a['label'] for a in arms[1:] if a.get('accepted') and (not control.get('accepted') or
            (a['accepted']['production_gain'] >= 2*control['accepted']['production_gain'] and a['candidate_calls'] <= control['candidate_calls']))]
        assert result['operational_improvement'] == bool(eligible)
        assert result['operational_gate']['eligible_arms'] == eligible
        verification.update(operational_improvement=bool(eligible), eligible_arms=eligible)
    return verification, arms


def summarize(output):
    verification, arms = verify(output)
    write(output/'verification.json', verification)
    write(output/'scorecard.json', dict(verification=verification, arms=[dict(label=a['label'], damping=a['damping'],
        status=a['status'], candidate_calls=a['candidate_calls'], accepted=a.get('accepted')) for a in arms]))
    write(output/'artifact_manifest.json', {str(x.relative_to(output)): digest(x)
        for x in sorted(output.rglob('*')) if x.is_file() and x.name != 'artifact_manifest.json'})
    return verification


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(summarize(parser.parse_args().output.resolve())))
