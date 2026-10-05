"""Approved GGB-002: independent pixel-volume data and bounded case-8 fits.

Run commands individually: prepare, run --arm S1, run --arm F4, report, verify.
The full-matrix adapter is a byte-identical copy of GGB-001's qualified adapter.
Truth is used only for observation generation and post-fit image scoring.
"""
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from time import perf_counter
from collections import Counter
import argparse
import hashlib
import json
import pickle
import traceback

import numpy as np
from scipy.special import hankel1

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'results/validation/cleaned_interfaces/GGB-002'
ORIGINAL = Path('/home/drdeng/Gau-Gal/outputs/GGB-001/prepared')
FREQUENCIES = np.array([.4e9, .5e9, .75e9, 1e9, 1.25e9])
ARCHIVE_HASH = '060e9d779ec8b6ebfd299c54cf9204148cdd9f5c43b71c6b43cdc55c5b1e5cd6'
DOMAIN = ((-1., -1.), (1., 1.))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    def convert(v):
        if isinstance(v, np.ndarray):
            return v.tolist()
        if isinstance(v, np.generic):
            return v.item()
        raise TypeError(type(v).__name__)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=convert, allow_nan=False) + '\n')
    temporary.replace(path)


def sources():
    files = list((ROOT / 'solvers/bem_inverse').rglob('*.py'))
    for package in ('gpr_bem_kress', 'ordered_boundary', 'periodic_kress'):
        files.extend((ROOT / 'solvers' / package).rglob('*.py'))
    files.extend(Path(__file__).parent.glob('*ggb002*.py'))
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(files)}


def green(k, first, second):
    distance = np.linalg.norm(first[:, None] - second[None, :], axis=-1)
    return .25j * hankel1(0, k * distance)


def volume_kernel(k, points, area):
    """Point-cell off-diagonals; equal-area disk average on the diagonal.

    G=i H0^(1)/4. Integral over radius a is i*pi*a*H1^(1)(ka)/(2k)-1/k^2.
    This diagonal and the point off-diagonals reproduce archived Phi entries.
    """
    distance = np.linalg.norm(points[:, None] - points[None, :], axis=-1)
    np.fill_diagonal(distance, 1.)
    result = .25j * hankel1(0, k * distance)
    radius = np.sqrt(area / np.pi)
    diagonal = (.5j * np.pi * radius * hankel1(1, k * radius) / k - 1/k**2) / area
    np.fill_diagonal(result, diagonal)
    return result


def generate(frequency, acquisition, case, eta):
    # Only non-background cells carry polarization, so the exact discrete
    # system reduces to 93 active pixels without a full 4096-square solve.
    epsilon = case['epsilon_truth'].ravel(order='F')
    active = epsilon > 1 + 1e-5
    points = acquisition['points'][active]
    contrast = epsilon[active] - 1
    k = float(acquisition['wavenumber']) * frequency / .4e9
    omega = k * 3e8
    mu = eta / 3e8
    area = float(np.diff(np.unique(case['x'])).mean() * np.diff(np.unique(case['y'])).mean())
    strength = complex(acquisition['source_scale']) * frequency / .4e9
    coefficient = omega**2 * mu * 8.85e-12 * area
    kernel = volume_kernel(k, points, area)
    incident = strength * green(k, points, acquisition['sources'])
    matrix = np.eye(len(points)) - coefficient * kernel * contrast[None, :]
    total = np.linalg.solve(matrix, incident)
    prediction = (coefficient * (green(k, acquisition['receivers'], points) @
                                 (contrast[:, None] * total))).T
    residual = float(np.linalg.norm(matrix @ total - incident) / np.linalg.norm(incident))
    if not np.isfinite(prediction).all() or residual > 1e-10:
        raise ValueError(f'Volume generation failed at {frequency}: residual={residual}')
    return prediction, dict(frequency_hz=float(frequency), wavenumber=k,
        active_cells=int(active.sum()), cell_area_m2=area, volume_relative_residual=residual,
        source_strength_real=strength.real, source_strength_imag=strength.imag)


def noise(clean):
    receiver_first = clean.T
    sigma = .05 * np.sqrt(np.mean(abs(receiver_first)**2) / 2)
    rng = np.random.RandomState(1000)
    value = receiver_first.real + sigma * rng.randn(*receiver_first.shape) + 1j * (
        receiver_first.imag + sigma * rng.randn(*receiver_first.shape))
    return value.T, float(sigma)


def qualify_adapter(device):
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.mie_localize import paired_data
    from bem_inverse.physics import Execution
    from bem_inverse.problem import Observation
    from .ggb002_adapter import FullAcquisition, FullMatrixModal
    angles = np.arange(4) * 2*np.pi/4
    tx = 3 * np.column_stack((np.cos(angles), np.sin(angles)))
    angles = np.arange(5) * 2*np.pi/5
    rx = 3 * np.column_stack((np.cos(angles), np.sin(angles)))
    acq = FullAcquisition(tx, rx, 2+3j)
    curve = FourierCurve.circle(.2, .03+.04j)
    velocity = np.array([[0, 0, 0], [1, 1j, 0], [0, 0, 1]], complex)
    space = SimpleNamespace(curve=curve, derivatives=velocity)
    service = FullMatrixModal(Execution(device=device, frequency_threads=1))
    rows = []
    for f in FREQUENCIES[1:]:
        k = 2*np.pi/.75 * f/.4e9
        observation = Observation(k, acq, np.ones((4, 5), complex), f)
        pred = service.evaluate(curve, observation, 1.4, 8*64)
        exact = paired_data(k, 1.4, [.03+.04j], [.2], np.repeat(tx, 5, axis=0),
                            np.tile(rx, (4, 1)), 64)[0, 0].reshape(4, 5) * acq.strength
        error = float(np.linalg.norm(pred.prediction-exact)/np.linalg.norm(exact))
        row = dict(frequency_hz=float(f), analytic_disk_relative_error=error,
                   diagnostics=pred.diagnostics)
        if error > 1e-8:
            raise ValueError(f'Independent Mie gate failed: {row}')
        if f in (FREQUENCIES[1], FREQUENCIES[-1]):
            derivative = service.derivative(pred, None, space)
            errors = []
            for column in range(3):
                step = 1e-6 * velocity[:, column]
                plus = service.evaluate(FourierCurve(curve.coefficients+step), observation, 1.4, 8*64)
                minus = service.evaluate(FourierCurve(curve.coefficients-step), observation, 1.4, 8*64)
                fd = (plus.prediction-minus.prediction).reshape(-1)/2e-6
                errors.append(float(np.linalg.norm(derivative[:, column]-fd)/np.linalg.norm(fd)))
            row['rebuilt_geometry_derivative_relative_errors'] = errors
            if max(errors) > 1e-5:
                raise ValueError(f'Rebuilt geometry gate failed: {row}')
        rows.append(row)
    return dict(passed=True, rows=rows, physics_receipt=service.receipt())


def prepare(output, device):
    import torch
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(experiment_id='GGB-002', approval='User: go (2026-10-05)',
                   status='PREPARING', device=device, torch=torch.__version__,
                   gpu=torch.cuda.get_device_name(0) if device == 'cuda' else None,
                   source_hashes=sources(), original_preparation=str(ORIGINAL))
    write(output / 'preparation.json', receipt)
    try:
        inventory = json.loads((ORIGINAL / 'inventory.json').read_text())
        if not inventory['physical_mapping_gate_passed'] or inventory['source_sha256'] != ARCHIVE_HASH:
            raise ValueError('Original provenance/physical mapping gate failed')
        for name, expected in inventory['prepared_file_sha256'].items():
            if sha256(ORIGINAL/name) != expected:
                raise ValueError('Prepared input hash mismatch: '+name)
        if sha256(inventory['source_path']) != ARCHIVE_HASH:
            raise ValueError('Official archive hash mismatch')
        receipt['original_inventory'] = inventory
        acq = dict(np.load(ORIGINAL/'acquisition.npz'))
        case = dict(np.load(ORIGINAL/'sample_0008.npz'))
        # Check diagonal/off-diagonal rules directly against the archived
        # operator, independent of observed scattered data or any inverse fit.
        with open(inventory['source_path'], 'rb') as stream:
            archive = pickle.load(stream)
        raw = archive['data']
        active = case['epsilon_truth'].ravel(order='F') > 1+1e-5
        ids = np.flatnonzero(active)
        phi = (raw['Phi_mat_real'][np.ix_(ids, ids)].astype(complex) +
               1j*raw['Phi_mat_imag'][np.ix_(ids, ids)])
        k = float(acq['wavenumber'])
        area = float(np.diff(np.unique(case['x'])).mean() * np.diff(np.unique(case['y'])).mean())
        eta = float(inventory['params']['eta_0'])
        rebuilt = 1j*k*eta * volume_kernel(k, acq['points'][active], area)
        op_error = float(np.linalg.norm(rebuilt-phi)/np.linalg.norm(phi))
        receipt['archived_phi_relative_error'] = op_error
        if op_error > 1e-5:
            raise ValueError(f'Archived operator convention gate failed: {op_error}')
        del archive, raw, phi
        clean, observed, sigmas, generation = [], [], [], []
        value, row = generate(.4e9, acq, case, eta)
        error = float(np.linalg.norm(value-case['clean_tx_rx'])/np.linalg.norm(case['clean_tx_rx']))
        receipt['archived_clean_field_relative_error'] = error
        receipt['generating_model'] = 'Original pixel mask; point-cell off-diagonal Green; equal-area disk self average'
        receipt['physical_source_convention'] = 'Archived source scale proportional to omega; mu=eta_0/c; eps0=8.85e-12; c=3e8'
        receipt['operator_reference'] = 'https://github.com/gomenei/SingleTX-EISP/blob/772d6eb81269353d7396c85fefa8c0a6d5091477/physics.py'
        receipt['operator_rule_evidence'] = 'Archived active-cell Phi, incident and receiver Green mappings; no scattered-field calibration'
        receipt['preliminary_read_only_probe'] = dict(archived_phi_offdiagonal_ratios_rounded=[1.,1.,1.,1.],
            archived_phi_diagonal_real=-787.3483, archived_phi_diagonal_imag=1258.4226,
            field_relative_error=3.2137529365238018e-6, volume_relative_residual=4.590989770497033e-16)
        if error > 1e-5:
            raise ValueError(f'Archived clean field gate failed: {error}')
        for f in FREQUENCIES:
            if f != .4e9:
                value, row = generate(f, acq, case, eta)
            noisy, sigma = noise(value)
            clean.append(value); observed.append(noisy); sigmas.append(sigma); generation.append(row)
        receipt['generation'] = generation
        receipt['adapter_qualification'] = qualify_adapter(device)
        np.savez_compressed(output/'inputs.npz', frequencies_hz=FREQUENCIES,
            clean=np.stack(clean), observed=np.stack(observed), sigma_real_imag=sigmas,
            archived_clean=case['clean_tx_rx'], archived_observed=case['noisy_tx_rx'],
            archived_sigma=case['sigma_real_imag'], truth=case['epsilon_truth'],
            x=case['x'], y=case['y'], sources=acq['sources'], receivers=acq['receivers'],
            source_scale=acq['source_scale'], reference_wavenumber=acq['wavenumber'],
            known_epsilon=case['known_epsilon'])
        receipt.update(status='QUALIFIED', inputs_sha256=sha256(output/'inputs.npz'))
        write(output/'preparation.json', receipt)
    except Exception:
        receipt.update(status='FAILED_QUALIFICATION', traceback=traceback.format_exc())
        write(output/'preparation.json', receipt)
        raise
    print(json.dumps({k:receipt[k] for k in ('status', 'archived_phi_relative_error',
                                           'archived_clean_field_relative_error')}, indent=2), flush=True)


def sealed(output):
    receipt = json.loads((output/'preparation.json').read_text())
    if receipt['status'] != 'QUALIFIED' or sha256(output/'inputs.npz') != receipt['inputs_sha256']:
        raise ValueError('Inputs are unqualified or changed')
    if sources() != receipt['source_hashes']:
        raise ValueError('Experiment sources changed after qualification')
    return dict(np.load(output/'inputs.npz')), receipt


def observations(data, indices):
    from bem_inverse.problem import Observation
    from .ggb002_adapter import FullAcquisition
    result = []
    for i in indices:
        f = float(data['frequencies_hz'][i])
        acq = FullAcquisition(data['sources'], data['receivers'], complex(data['source_scale'])*f/.4e9)
        result.append(Observation(float(data['reference_wavenumber'])*f/.4e9, acq,
                                  data['observed'][i], f, float(data['sigma_real_imag'][i])))
    return tuple(result)


def run(output, arm, device):
    import torch
    from bem_inverse.continuation.geometry import FourierCurve
    from bem_inverse.continuation.lm_backend import FitStage, Ledger, fit_stage
    from bem_inverse.geometry_selection import make_update
    from bem_inverse.physics import Execution
    from bem_inverse.policy import CumulativePolicy
    from .ggb002_adapter import FullMatrixModal
    data, preparation = sealed(output)
    if device != preparation['device']:
        raise ValueError('Execution device differs from qualification')
    directory = output/arm
    directory.mkdir(exist_ok=False)
    indices = [1] if arm == 'S1' else [1, 2, 3, 4]
    obs = observations(data, indices)
    n = len(obs)
    config, weights, expected = CumulativePolicy()._config(SimpleNamespace(domain_box=DOMAIN), obs)
    execution = Execution(device=device, frequency_threads=1)
    service = FullMatrixModal(execution)
    update = make_update('certified_spectral', 1., execution)
    curve = FourierCurve(np.r_[np.zeros(33, complex), .35, np.zeros(31, complex)])
    ledger = Ledger(cap=2000*n, seconds=600*n, strict_dispatch=True)
    receipt = dict(experiment_id='GGB-002', arm=arm, status='RUNNING', indices=indices,
        frequencies_hz=[o.frequency_hz for o in obs], weights=weights,
        expected_noise_loss=expected, backend_config=asdict(config), execution=asdict(execution),
        settings=dict(M=[3,7,11], geometry_band=32, trace_cutoffs=[64,96], iterations=100,
                      stage_quota=650*n, work_cap=2000*n, fit_seconds_cap=600*n), stages=[])
    write(directory/'result.json', receipt)

    def sync():
        if device == 'cuda':
            torch.cuda.synchronize()

    started = perf_counter()
    try:
        sync()
        for modes in (3,7,11):
            label = f'{arm}_M{modes}'
            stage = FitStage(label, obs, weights, (1e-4,)*n, modes, 32, 8*64, 8*96, 100, 650*n)
            ledger.begin_stage(label, stage.quota)
            print(f'{arm}: starting {label}', flush=True)
            result = fit_stage(curve, stage, float(data['known_epsilon']), update, config, ledger, physics=service)
            curve = result.curve
            stage_row = {key:value for key,value in asdict(result).items() if key not in ('curve','checkpoint')}
            receipt['stages'].append(stage_row)
            receipt.update(fit_seconds=perf_counter()-started, ledger=ledger.snapshot(),
                           physics_receipt_fit=service.receipt())
            np.savez_compressed(directory/'curve.npz', coefficients=curve.coefficients)
            write(directory/'result.json', receipt)
            print(f'{arm}: {label} {result.outcome}/{stage_row["stop_reason"]}, '
                  f'{stage_row["accepted_steps"]} accepted, {receipt["fit_seconds"]:.1f}s', flush=True)
            if result.converged or result.outcome != 'NORMAL_OPTIMIZER_RETURN':
                break
        sync()
        receipt.update(fit_seconds=perf_counter()-started, ledger=ledger.snapshot(),
                       physics_receipt_fit=service.receipt())
        audit_start = perf_counter()
        predictions, refined, audit = [], [], []
        for i, observation in enumerate(observations(data, range(5))):
            first = service.evaluate(curve, observation, float(data['known_epsilon']), 8*64)
            second = service.evaluate(curve, observation, float(data['known_epsilon']), 8*96)
            predictions.append(first.prediction); refined.append(second.prediction)
            error = float(np.linalg.norm(first.prediction-second.prediction)/np.linalg.norm(second.prediction))
            target = data['archived_observed'] if i == 0 else observation.scattered
            residual = float(np.linalg.norm(second.prediction-target)/np.linalg.norm(target))
            sigma = float(data['archived_sigma'] if i == 0 else observation.sigma_real_imag)
            threshold = 1.1*np.sqrt(2*target.size*sigma**2/np.linalg.norm(target)**2)
            audit.append(dict(frequency_hz=observation.frequency_hz, active_in_fit=i in indices,
                relative_residual=residual, noise_target_relative=threshold,
                field_refinement_relative_error=error, field_gate_passed=bool(error<=1e-4),
                noise_target_met=bool(residual<=threshold),
                clean_relative_error=float(np.linalg.norm(second.prediction-data['clean'][i])/np.linalg.norm(data['clean'][i]))))
        image = raster(curve.coefficients, data)
        sync()
        receipt.update(audit_seconds=perf_counter()-audit_start, audit=audit,
            image_metrics=metrics(image,data['truth']), physics_receipt_with_audits=service.receipt(), status='COMPLETE')
        np.savez_compressed(directory/'endpoint.npz', coefficients=curve.coefficients,
            prediction=np.stack(predictions), refined_prediction=np.stack(refined), image=image)
        joint = .5*sum(w*audit[i]['relative_residual']**2 for w,i in zip(weights,indices))
        receipt.update(refined_joint_loss=joint,
            noise_discrepancy_met=bool(joint <= config.loss_tolerance),
            field_gates_passed=all(audit[i]['field_gate_passed'] for i in indices))
    except Exception:
        receipt.update(status='FAILED', traceback=traceback.format_exc(),
            fit_or_audit_elapsed_seconds=perf_counter()-started, ledger=ledger.snapshot(),
            physics_receipt_with_audits=service.receipt())
        np.savez_compressed(directory/'curve.npz', coefficients=curve.coefficients)
        write(directory/'result.json', receipt)
        raise
    write(directory/'result.json', receipt)
    report(output)
    print(json.dumps({k:receipt[k] for k in ('arm','status','fit_seconds','refined_joint_loss',
                                           'noise_discrepancy_met','field_gates_passed')},indent=2),flush=True)


def raster(coefficients, data):
    from matplotlib.path import Path as Polygon
    from bem_inverse.continuation.geometry import FourierCurve
    curve = FourierCurve(coefficients).values(4096)
    points = np.column_stack((data['x'].ravel(),data['y'].ravel()))
    inside = Polygon(np.column_stack((curve.real,curve.imag))).contains_points(points).reshape(data['truth'].shape)
    return np.where(inside,float(data['known_epsilon']),1.)


def metrics(image, truth):
    # Use the unchanged released metric implementation; never a solver input.
    import sys
    path = '/home/drdeng/Gau-Gal/src'
    if path not in sys.path:
        sys.path.insert(0,path)
    from gaugal.paper2d.metrics import single_tx_metrics, snr_db
    return dict(single_tx_metrics(image,truth),snr_db=snr_db(image-1,truth-1))


def report(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from bem_inverse.continuation.geometry import FourierCurve
    data = dict(np.load(output/'inputs.npz'))
    rows = []
    for arm in ('S1','F4'):
        path = output/arm/'result.json'
        if path.exists():
            rows.append(json.loads(path.read_text()))
    text = ['# GGB-002 — Case 8 with four frequencies','',
        'Approved synthetic extension of the original pixel target. Material is known. '
        'Start: centred radius-0.35 m circle. No localization or restart.', '',
        '| Arm | Frequencies GHz | Fit s | SSIM | RRMSE | Contrast SNR dB | Joint discrepancy met | Field gates passed |',
        '|---|---|---:|---:|---:|---:|---|---|']
    for row in rows:
        if row['status'] == 'COMPLETE':
            m = row['image_metrics']
            text.append(f'| {row["arm"]} | '+', '.join(f'{f/1e9:g}' for f in row['frequencies_hz'])+
                f' | {row["fit_seconds"]:.3f} | {m["ssim"]:.5f} | {m["rrmse"]:.5f} | {m["snr_db"]:.2f} | '
                f'{row["noise_discrepancy_met"]} | {row["field_gates_passed"]} |')
        else:
            text.append(f'| {row["arm"]} | — | — | — | — | — | {row["status"]} | — |')
    text += ['', '## Endpoint residuals', '',
        '| Arm | Frequency GHz | Relative residual | Noise target | Field refinement error | Used in fit |',
        '|---|---:|---:|---:|---:|---|']
    for row in rows:
        for a in row.get('audit',[]):
            text.append(f'| {row["arm"]} | {a["frequency_hz"]/1e9:g} | {100*a["relative_residual"]:.3f}% | '
                f'{100*a["noise_target_relative"]:.3f}% | {a["field_refinement_relative_error"]:.3g} | {a["active_in_fit"]} |')
    text += ['', '## Optimizer evidence', '']
    for row in rows:
        trials = [trial for stage in row['stages'] for trial in stage['trials']]
        refusals = Counter(t.get('reason','unspecified') for t in trials if t.get('status')=='refused')
        stops = ', '.join(stage['label']+': '+stage['outcome']+'/'+stage['stop_reason'] for stage in row['stages'])
        accepted = sum(s['accepted_steps'] for s in row['stages'])
        text.append(f'- {row["arm"]}: {accepted} accepted steps; {len(trials)} proposals; refusals {dict(refusals)}. {stops}.')
    text += ['', 'The original archived 0.4 GHz BEM residual was 87.662% (GGB-001). '
        'The new matched control is S1 at 0.5 GHz. The entire standard damped/19-frequency '
        'continuation recipe was not used.', '', '![Case 8 reconstruction comparison](comparison.png)', '']
    (output/'report.md').write_text('\n'.join(text))
    panels = [('Truth',data['truth'],None),('Initial circle',raster(np.r_[np.zeros(33),.35,np.zeros(31)],data),
                np.r_[np.zeros(33),.35,np.zeros(31)])]
    for row in rows:
        path = output/row['arm']/'endpoint.npz'
        if path.exists():
            end = dict(np.load(path))
            panels.append((row['arm']+': '+', '.join(f'{f/1e9:g}' for f in row['frequencies_hz'])+' GHz',end['image'],end['coefficients']))
    fig, axes = plt.subplots(1,len(panels),figsize=(4.2*len(panels),4.2),constrained_layout=True)
    for ax,(title,image,coeff) in zip(np.atleast_1d(axes),panels):
        im = ax.imshow(image,extent=(-1,1,-1,1),origin='upper',vmin=1,vmax=float(data['known_epsilon']),cmap='viridis')
        if coeff is not None:
            z=FourierCurve(coeff).values(4096)
            ax.plot(z.real,z.imag,color='white',linewidth=.7)
        ax.set(title=title,xlabel='x (m)',ylabel='y (m)',xlim=(-1,1),ylim=(-1,1))
    fig.colorbar(im,ax=axes,label='Relative permittivity',shrink=.8)
    fig.savefig(output/'comparison.png',dpi=160)
    plt.close(fig)


def verify(output):
    from bem_inverse.policy import CumulativePolicy
    data, prep = sealed(output)
    verified = dict(inputs_sha256=prep['inputs_sha256'],arms=[])
    for arm in ('S1','F4'):
        path = output/arm/'result.json'
        if not path.exists():
            continue
        row=json.loads(path.read_text())
        if row['status'] != 'COMPLETE':
            verified['arms'].append(dict(arm=arm,status=row['status'],failure_evidence_present='traceback' in row))
            continue
        end=dict(np.load(output/arm/'endpoint.npz'))
        image=raster(end['coefficients'],data)
        if not np.array_equal(image,end['image']):
            raise ValueError('Saved image differs from rasterized curve')
        for key,value in metrics(image,data['truth']).items():
            if not np.isclose(value,row['image_metrics'][key],rtol=1e-12,atol=1e-12):
                raise ValueError('Metric read-back mismatch: '+key)
        for i,a in enumerate(row['audit']):
            target=data['archived_observed'] if i==0 else data['observed'][i]
            p=end['prediction'][i];ref=end['refined_prediction'][i]
            residual=np.linalg.norm(ref-target)/np.linalg.norm(target)
            error=np.linalg.norm(p-ref)/np.linalg.norm(ref)
            if not np.isclose(residual,a['relative_residual'],rtol=1e-12) or not np.isclose(error,a['field_refinement_relative_error'],rtol=1e-12,atol=1e-15):
                raise ValueError('Residual/refinement read-back mismatch')
        config,weights,_=CumulativePolicy()._config(SimpleNamespace(domain_box=DOMAIN),observations(data,row['indices']))
        joint=.5*sum(w*row['audit'][i]['relative_residual']**2 for w,i in zip(weights,row['indices']))
        if not np.isclose(joint,row['refined_joint_loss'],rtol=1e-12):
            raise ValueError('Joint loss read-back mismatch')
        if bool(joint<=config.loss_tolerance) != row['noise_discrepancy_met']:
            raise ValueError('Discrepancy decision mismatch')
        verified['arms'].append(dict(arm=arm,status='VERIFIED',endpoint_sha256=sha256(output/arm/'endpoint.npz'),
                                    result_sha256=sha256(path)))
    write(output/'validation.json',verified)
    print(json.dumps(verified,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','report','verify'))
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--device',choices=('cuda','cpu'),default='cuda')
    parser.add_argument('--arm',choices=('S1','F4'))
    args=parser.parse_args()
    if args.command=='prepare':
        prepare(args.output,args.device)
    elif args.command=='run':
        if args.arm is None:
            parser.error('run requires --arm S1 or F4')
        run(args.output,args.arm,args.device)
    elif args.command=='report':
        report(args.output)
    else:
        verify(args.output)


if __name__=='__main__':
    main()
