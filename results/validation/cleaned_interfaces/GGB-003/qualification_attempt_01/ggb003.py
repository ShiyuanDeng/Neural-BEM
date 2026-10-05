"""GGB-003: exact translation during M3 only; immutable GGB-002 F4 data.

The run command requires a recorded explicit approval of this experiment ID.
Qualification is bounded correctness testing and performs no inverse fits.
"""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
from time import perf_counter
import traceback
from types import SimpleNamespace

import numpy as np

from . import ggb002 as previous

ROOT = previous.ROOT
INPUT = previous.DEFAULT_OUTPUT
OUTPUT = ROOT/'results/validation/cleaned_interfaces/GGB-003'
ID = 'GGB-003'


def portable(value):
    if isinstance(value, np.ndarray):
        return portable(value.tolist())
    if isinstance(value, np.generic):
        return portable(value.item())
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write(path, value):
    previous.write(path, portable(value))


def sources():
    paths = list((ROOT/'solvers').rglob('*.py'))
    paths += [Path(__file__), Path(previous.__file__),
              ROOT/'experiments/benchmark/ggb002_adapter.py',
              ROOT/'pytest/bem_inverse/test_translation.py',
              ROOT/'experiments/benchmark/test_ggb003.py']
    return {str(p.relative_to(ROOT)): previous.sha256(p) for p in sorted(paths)}


def inputs():
    prep = json.loads((INPUT/'preparation.json').read_text())
    if previous.sha256(INPUT/'inputs.npz') != prep['inputs_sha256']:
        raise ValueError('Original GGB-002 input seal does not match.')
    with np.load(INPUT/'inputs.npz') as archive:
        data = dict(archive)
    return data, dict(path=str((INPUT/'inputs.npz').relative_to(ROOT)),
                     sha256=prep['inputs_sha256'],
                     original_preparation_sha256=previous.sha256(INPUT/'preparation.json'))


def record_stage(result):
    return {k: v for k, v in asdict(result).items() if k not in ('curve', 'checkpoint')}


def stage_one(curve, stage, contrast, shape, config, ledger, physics, *, on_block=None):
    """Alternate independent LM blocks without resetting the shared ledger."""
    from bem_inverse.continuation.lm_backend import fit_stage
    from bem_inverse.translation import TranslationUpdate
    if stage.update_modes != 3:
        raise ValueError('This experiment permits explicit translation only in M3.')
    pose = TranslationUpdate(shape.length_unit_m)
    damping = dict(translation=config.initial_damping, shape=config.initial_damping)
    blocks, history, trials, checks, failures = [], [], [], [], []
    accepted, initial_loss, final_loss = 0, None, None
    outcome, stop, detail, converged = 'NORMAL_OPTIMIZER_RETURN', 'iteration_limit', None, False
    started = perf_counter()
    done = False
    for cycle in range(stage.iterations):
        moved = False
        for kind, update in (('translation', pose), ('shape', shape)):
            substage = replace(stage, label=f'{stage.label}_{cycle:03d}_{kind}', iterations=1)
            subconfig = replace(config, initial_damping=damping[kind])
            result = fit_stage(curve, substage, contrast, update, subconfig, ledger, physics=physics)
            curve = result.curve
            block = dict(record_stage(result), block=kind, cycle=cycle,
                         initial_damping=damping[kind])
            blocks.append(block)
            if initial_loss is None:
                initial_loss = result.initial_loss
            final_loss = result.final_loss
            for row in result.history:
                if not history or row['iteration'] > 0:
                    if row['iteration'] > 0:
                        accepted += 1
                    history.append(dict(row, iteration=accepted, block_iteration=row['iteration'],
                                        block=kind, cycle=cycle))
            trials.extend(dict(t, block=kind, cycle=cycle) for t in result.trials)
            checks.extend(dict(c, block=kind, cycle=cycle) for c in result.acceptance_checks)
            failures.extend(result.physics_failures)
            if result.accepted_steps:
                moved = True
                damping[kind] = result.history[-1]['next_damping']
            if on_block is not None:
                on_block(curve, block)
            if result.outcome != 'NORMAL_OPTIMIZER_RETURN':
                outcome, stop, detail = result.outcome, result.stop_reason, result.detail
                done = True
                break
            # A block gradient tolerance is not whole-objective convergence.
            if np.isfinite(final_loss) and final_loss <= config.loss_tolerance:
                stop, converged, done = 'loss_tolerance', True, True
                break
        if done:
            break
        if not moved:
            stop = 'no_decreasing_blocks'
            break
    return curve, dict(stage_label=stage.label, outcome=outcome, stop_reason=stop,
        detail=detail, converged=converged, accepted_steps=accepted,
        initial_loss=initial_loss, final_loss=final_loss, history=history, trials=trials,
        acceptance_checks=checks, physics_failures=failures, blocks=blocks,
        work=ledger.snapshot(), seconds=perf_counter()-started,
        translation_work=pose.counts, damping_next=damping,
        final_nodes=stage.nodes, final_refined_nodes=stage.refined_nodes)


def qualify(device):
    """Full-array translation derivative at fixed circle and curved fixtures."""
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.physics import Execution
    from bem_inverse.problem import Observation
    from bem_inverse.translation import TranslationUpdate
    from .ggb002_adapter import FullAcquisition, FullMatrixModal
    data, _ = inputs()
    saved = json.loads((INPUT/'F4/result.json').read_text())['stages'][0]['history'][8]['coefficients']
    curved = np.array(saved['real']) + 1j*np.array(saved['imag'])
    fixtures = [('circle', FourierCurve.circle(.2, .03+.04j).coefficients, 1.),
                ('curved_nonunit', curved, .25)]
    rows = []
    for name, physical, unit in fixtures:
        curve = FourierCurve(physical/unit)
        update = TranslationUpdate(unit)
        space = update.prepare(curve, 3, curve.band)
        service = FullMatrixModal(Execution(device=device, frequency_threads=1))
        for index in (1, 2, 3, 4):
            f = float(data['frequencies_hz'][index])
            acq = FullAcquisition(data['sources']/unit, data['receivers']/unit,
                                  complex(data['source_scale'])*f/.4e9)
            observation = Observation(float(data['reference_wavenumber'])*f/.4e9*unit,
                                      acq, np.ones((16, 32), complex), f)
            base = service.evaluate(curve, observation, float(data['known_epsilon']), 8*64)
            jacobian = service.derivative(base, update, space)
            errors = []
            for column in range(2):
                step = np.eye(2)[column]*1e-6
                plus = update.trial(space, step)[0]
                minus = update.trial(space, -step)[0]
                for shifted in (plus, minus):
                    keep = np.arange(len(physical)) != curve.band
                    np.testing.assert_array_equal(shifted.coefficients[keep], curve.coefficients[keep])
                high = service.evaluate(plus, observation, float(data['known_epsilon']), 8*64).prediction
                low = service.evaluate(minus, observation, float(data['known_epsilon']), 8*64).prediction
                fd = ((high-low)/2e-6).reshape(-1)
                errors.append(float(np.linalg.norm(fd-jacobian[:, column])/np.linalg.norm(fd)))
            rows.append(dict(fixture=name, unit_m=unit, frequency_hz=f, errors=errors))
        service.close()
    worst = max(e for row in rows for e in row['errors'])
    if not np.isfinite(worst) or worst > 1e-5:
        raise ValueError(f'Translation derivative qualification failed: {worst}')
    return dict(passed=True, device=device, maximum_relative_column_error=worst, rows=rows)


def qualification(output):
    output.mkdir(parents=True, exist_ok=True)
    before = sources()
    row = dict(experiment_id=ID, purpose='bounded correctness qualification, no inverse',
               source_hashes=before, input=inputs()[1], status='RUNNING', devices=[])
    path = output/'qualification.json'
    write(path, row)
    try:
        for device in ('cpu', 'cuda'):
            row['devices'].append(qualify(device))
            write(path, row)
        if sources() != before:
            raise ValueError('Source changed during qualification.')
        row.update(status='PASSED')
    except Exception:
        row.update(status='FAILED', traceback=traceback.format_exc())
        write(path, row)
        raise
    write(path, row)
    print(json.dumps({d['device']: d['maximum_relative_column_error'] for d in row['devices']}, indent=2))


def audit(curve, data, service, weights, config):
    predictions, refined, rows = [], [], []
    for i, observation in enumerate(previous.observations(data, range(5))):
        coarse = service.evaluate(curve, observation, float(data['known_epsilon']), 8*64).prediction
        fine = service.evaluate(curve, observation, float(data['known_epsilon']), 8*96).prediction
        target = data['archived_observed'] if i == 0 else observation.scattered
        sigma = float(data['archived_sigma'] if i == 0 else observation.sigma_real_imag)
        residual = float(np.linalg.norm(fine-target)/np.linalg.norm(target))
        threshold = float(1.1*np.sqrt(2*target.size*sigma**2/np.linalg.norm(target)**2))
        error = float(np.linalg.norm(coarse-fine)/np.linalg.norm(fine))
        rows.append(dict(frequency_hz=observation.frequency_hz, active_in_fit=i>0,
            relative_residual=residual, noise_target_relative=threshold,
            field_refinement_relative_error=error, field_gate_passed=bool(error <= 1e-4),
            noise_target_met=bool(residual <= threshold)))
        predictions.append(coarse)
        refined.append(fine)
    joint = .5*sum(w*r['relative_residual']**2 for w, r in zip(weights, rows[1:]))
    return dict(audit=rows, refined_joint_loss=joint,
                noise_discrepancy_met=bool(joint <= config.loss_tolerance),
                all_frequency_noise_targets_met=all(r['noise_target_met'] for r in rows[1:]),
                field_gates_passed=all(r['field_gate_passed'] for r in rows[1:])), predictions, refined


def shape_metrics(curve, data):
    # Post-fit diagnostics, never an argument of stage_one or fit_stage.
    z, dz = curve.values(8192), curve.values(8192, derivative=1)
    dt = 2*np.pi/len(z)
    area = .5*dt*np.sum(z.real*dz.imag-z.imag*dz.real)
    centre = .5*dt*(np.sum(z.real**2*dz.imag)-1j*np.sum(z.imag**2*dz.real))/area
    mask = data['truth'] > 1+1e-5
    truth_centre = np.mean(data['x'][mask])+1j*np.mean(data['y'][mask])
    cell = np.diff(np.unique(data['x'])).mean()*np.diff(np.unique(data['y'])).mean()
    radius = float(np.sqrt(area/np.pi))
    target_radius = float(np.sqrt(mask.sum()*cell/np.pi))
    image = previous.raster(curve.coefficients, data)
    return dict(image_metrics=previous.metrics(image, data['truth']),
                centre_m=[float(centre.real), float(centre.imag)],
                centre_error_m=float(abs(centre-truth_centre)), equivalent_radius_m=radius,
                target_equivalent_radius_m=target_radius, radius_error_m=abs(radius-target_radius))


def run(output, arm):
    import torch
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.continuation.lm_backend import FitStage, Ledger, fit_stage
    from bem_inverse.geometry_selection import make_update
    from bem_inverse.physics import Execution
    from bem_inverse.policy import CumulativePolicy
    from .ggb002_adapter import FullMatrixModal
    approval = json.loads((output/'approval.json').read_text())
    if approval.get('experiment_id') != ID or approval.get('approved') is not True or not approval.get('user_message'):
        raise ValueError('Explicit user approval of GGB-003 must be recorded before fitting.')
    qualification_row = json.loads((output/'qualification.json').read_text())
    before = sources()
    if qualification_row['status'] != 'PASSED' or qualification_row['source_hashes'] != before:
        raise ValueError('Current sources have not passed translation qualification.')
    data, seal = inputs()
    if seal != qualification_row['input']:
        raise ValueError('Qualification inputs changed.')
    if arm == 'T' and not (output/'B/result.json').exists():
        raise ValueError('Run and retain the fresh B control first.')
    directory = output/arm
    directory.mkdir(exist_ok=False)
    obs = previous.observations(data, (1, 2, 3, 4))
    config, weights, expected = CumulativePolicy()._config(SimpleNamespace(domain_box=previous.DOMAIN), obs)
    execution = Execution(device='cuda', frequency_threads=1)
    service = FullMatrixModal(execution)
    shape = make_update('certified_spectral', 1., execution)
    curve = FourierCurve(np.r_[np.zeros(33, complex), .35, np.zeros(31, complex)])
    ledger = Ledger(cap=8000, seconds=2400, strict_dispatch=True)
    row = dict(experiment_id=ID, arm=arm, status='RUNNING', source_hashes=before,
        environment=dict(torch=torch.__version__, cuda=torch.version.cuda,
                         gpu=torch.cuda.get_device_name(0)),
        input=seal, backend_config=asdict(config), execution=asdict(execution),
        weights=weights, expected_noise_loss=expected, frequencies_hz=[o.frequency_hz for o in obs],
        settings=dict(M=[3,7,11], geometry_band=32, trace_cutoffs=[64,96], iterations=100,
                      stage_quota=2600, work_cap=8000, fit_seconds_cap=2400,
                      translation_stage_only=3 if arm == 'T' else None,
                      translation_cap_m=.018), stages=[])
    write(directory/'result.json', row)
    started = perf_counter()
    def checkpoint(current, block):
        np.savez_compressed(directory/'curve.npz', coefficients=current.coefficients)
        with (directory/'blocks.jsonl').open('a') as stream:
            stream.write(json.dumps(portable(block), allow_nan=False)+'\n')
    try:
        torch.cuda.synchronize()
        for modes in (3,7,11):
            label = f'{arm}_M{modes}'
            stage = FitStage(label, obs, weights, (1e-4,)*4, modes, 32, 8*64, 8*96, 100, 2600)
            ledger.begin_stage(label, stage.quota)
            print(f'{arm}: {label}', flush=True)
            if arm == 'T' and modes == 3:
                curve, stage_row = stage_one(curve, stage, float(data['known_epsilon']), shape,
                                             config, ledger, service, on_block=checkpoint)
            else:
                result = fit_stage(curve, stage, float(data['known_epsilon']), shape, config, ledger, physics=service)
                curve, stage_row = result.curve, record_stage(result)
            row['stages'].append(stage_row)
            row.update(fit_seconds=perf_counter()-started, ledger=ledger.snapshot(),
                       physics_receipt_fit=service.receipt(), geometry_work=shape.counts)
            np.savez_compressed(directory/'curve.npz', coefficients=curve.coefficients)
            write(directory/'result.json', row)
            print(f"{label}: {stage_row['outcome']}/{stage_row['stop_reason']}; "
                  f"{stage_row['accepted_steps']} accepted; loss {stage_row['final_loss']}", flush=True)
            if stage_row['converged'] or stage_row['outcome'] != 'NORMAL_OPTIMIZER_RETURN':
                break
        torch.cuda.synchronize()
        row.update(fit_seconds=perf_counter()-started, ledger=ledger.snapshot(), physics_receipt_fit=service.receipt())
        began_audit = perf_counter()
        audited, prediction, refined = audit(curve, data, service, weights, config)
        torch.cuda.synchronize()
        row.update(audited, audit_seconds=perf_counter()-began_audit,
                   physics_receipt_with_audits=service.receipt())
        np.savez_compressed(directory/'endpoint.npz', coefficients=curve.coefficients,
                            prediction=np.stack(prediction), refined_prediction=np.stack(refined))
        row.update(shape_metrics(curve, data))
        if sources() != before:
            raise ValueError('Numerical sources changed during the run; retain but do not qualify this result.')
        row.update(status='COMPLETE')
    except Exception:
        row.update(status='FAILED', traceback=traceback.format_exc(),
                   fit_or_audit_elapsed_seconds=perf_counter()-started, ledger=ledger.snapshot())
        np.savez_compressed(directory/'curve.npz', coefficients=curve.coefficients)
        write(directory/'result.json', row)
        raise
    finally:
        service.close()
    write(directory/'result.json', row)
    print(json.dumps({k: row[k] for k in ('arm','status','fit_seconds','refined_joint_loss',
                     'centre_error_m','noise_discrepancy_met','field_gates_passed')}, indent=2))


def verify(output):
    data, seal = inputs()
    validated = []
    for arm in ('B','T'):
        directory = output/arm
        if not (directory/'result.json').exists():
            continue
        row = json.loads((directory/'result.json').read_text())
        assert row['input'] == seal
        if row['status'] != 'COMPLETE':
            assert 'traceback' in row
            validated.append(dict(arm=arm, status='FAILED_PRESERVED'))
            continue
        with np.load(directory/'endpoint.npz') as end:
            with np.load(directory/'curve.npz') as curve:
                np.testing.assert_array_equal(end['coefficients'], curve['coefficients'])
            for i, a in enumerate(row['audit']):
                target = data['archived_observed'] if i == 0 else data['observed'][i]
                residual = np.linalg.norm(end['refined_prediction'][i]-target)/np.linalg.norm(target)
                np.testing.assert_allclose(residual, a['relative_residual'], rtol=1e-13)
            from bem_inverse.continuation.geometry import FourierCurve
            for k,v in shape_metrics(FourierCurve(end['coefficients']), data).items():
                if isinstance(v,dict):
                    for key,value in v.items():
                        np.testing.assert_allclose(value,row[k][key],rtol=1e-12)
                else:
                    np.testing.assert_allclose(v,row[k],rtol=1e-12)
        for stage in row['stages']:
            if not stage['stage_label'].endswith('M3'):
                assert 'blocks' not in stage
        validated.append(dict(arm=arm, status='PASSED'))
    write(output/'validation.json', dict(experiment_id=ID, arms=validated))
    print(json.dumps(validated,indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('qualify','run','verify'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--arm', choices=('B','T'))
    args = parser.parse_args()
    if args.command == 'qualify':
        qualification(args.output)
    elif args.command == 'run':
        if args.arm is None:
            parser.error('run requires --arm B or T')
        run(args.output,args.arm)
    else:
        verify(args.output)


if __name__ == '__main__':
    main()
