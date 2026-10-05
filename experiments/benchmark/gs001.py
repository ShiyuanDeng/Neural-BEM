"""Bounded single-frequency known-material GauGal TG-002 probe (GS-001)."""
import argparse
import fcntl
import json
import subprocess
import time
import traceback
from pathlib import Path

import numpy as np
import torch

from bem_inverse.io import digest, write, read, curve_from
from . import campaign as B
from . import gs001_adapter as G
from . import on002_adapter as A
from .on002 import mie, adjoint_check, derivative_check

ROOT = B.ROOT
OUT = ROOT/'results/validation/cleaned_interfaces/GS-001'
CASE = 'c_shape__c13.3'
INDEX = 2
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')


def tv(value):
    dy = torch.roll(value, -1, 0)-value
    dx = torch.roll(value, -1, 1)-value
    return torch.sqrt(dx*dx+dy*dy).mean()


def snapshot(folder, f, step, prediction):
    A.sync(str(f.projected.device))
    np.savez_compressed(folder/f'state_{step:03d}.npz',
        occupancy=f.render().cpu().numpy(), coefficients=f.coefficients.cpu().numpy(),
        prediction=prediction.cpu().numpy(), x=f.model.x.cpu().numpy(), y=f.model.y.cpu().numpy())


def run(folder, device, tv_prox='native'):
    folder.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    seal = B.verify(require_inputs=True)
    source_paths = [Path(__file__), Path(G.__file__), Path(A.__file__),
        ROOT/'experiments/benchmark/test_gs001.py', ROOT/'docs/iterations/CI-SPD/GS-001_plan.md']
    if tv_prox == 'qualified':
        source_paths.append(ROOT/'docs/iterations/CI-SPD/GS-001_tv_repair_plan.md')
    source_paths += list((A.EXTERNAL/'src').rglob('*.py'))
    hashes = {str(p): digest(p) for p in source_paths}
    write(folder/'manifest.json', dict(experiment='GS-001', case=CASE, frequency_hz=5e8,
        frequency_index=INDEX, device=device, source_hashes=hashes, versions=A.versions(),
        benchmark_manifest_sha256=digest(B.INPUTS/'manifest.json'),
        input_sealed=seal['inputs_sealed'], known_material=True, localization='none',
        parent_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        branch=subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        authorization='User: try run gau gal in one of our high contrast scenes. see single frequency will take it how far',
        max_steps=300, fit_wall_cap_seconds=1800, preconditioner='exact separable Gaussian mass',
        tv_prox=tv_prox))
    problem = B.problem(CASE)
    observation = problem.real[INDEX]
    assert observation.frequency_hz == 5e8
    qualifications = []
    for pixels, centres in ((128,112), (256,224)):
        print('BUILD', pixels, centres, flush=True)
        f = G.build(problem, observation, pixels=pixels, centers=centres, device=device)
        prediction, _, residual = f.predict()
        reference = mie(problem, observation)
        discrepancy = float(np.linalg.norm(prediction.cpu().numpy()-reference)/np.linalg.norm(reference))
        row = dict(pixels=pixels, centres=centres, start_disk_relative_field_error=discrepancy,
                   start_true_residual=residual, mass_condition_1d=f.mass_condition,
                   adjoint=adjoint_check(f), derivative=derivative_check(f,
                       torch.as_tensor(observation.scattered.copy(), device=device, dtype=torch.complex128)))
        qualifications.append(row)
        write(folder/'qualification.json', qualifications)
        print('QUALIFICATION', json.dumps(row), flush=True)
        if (row['adjoint']['system_relative'] > 1e-5 or
            row['adjoint']['sensor_relative'] > 1e-5 or
            row['adjoint']['off_pair_max'] != 0 or not row['derivative']['passed']):
            raise RuntimeError('Full-grid adjoint/derivative qualification failed')
        if discrepancy <= .01 or pixels == 256:
            break
        del f
        if device.startswith('cuda'):
            torch.cuda.empty_cache()
    target = torch.as_tensor(observation.scattered.copy(), device=device, dtype=torch.complex128)
    norm2 = torch.sum(abs(target)**2)
    C, _ = A.external()
    f.options.contrast_max = 1.
    f.options.collocation_tv_mode = 'coefficient'
    fit_started = time.perf_counter()
    history, rejected = [], []
    step_size = None
    stop = 'STEP_CAP'
    accepted = 0
    snapshot(folder, f, 0, prediction)
    for iteration in range(300):
        if time.perf_counter()-fit_started >= 1800:
            stop = 'WALL_CAP'
            break
        lam = (1e-3, 1e-4, 1e-5)[iteration//100]
        loss, grad, solves = f.objective_gradient(target)
        n = f.projected.grid_size
        current = f.coefficients
        penalty = tv(current.reshape(n,n))
        total = float((loss+lam*penalty).cpu())
        relative = float(torch.sqrt(2*loss).cpu())
        row = dict(step=accepted, data_residual=relative, data_loss=float(loss.cpu()),
            tv_mean=float(penalty.cpu()), lam=lam, objective=total,
            elapsed_seconds=time.perf_counter()-fit_started, **solves)
        history.append(row)
        write(folder/'history.json', history)
        if relative <= .003:
            stop = 'SINGLE_FREQUENCY_DISCREPANCY_REACHED'
            break
        maximum = float(abs(grad).max().cpu())
        if maximum == 0 or not np.isfinite(maximum):
            stop = 'GRADIENT_INVALID_OR_ZERO'
            break
        step_size = min(.1/maximum, .05/maximum if step_size is None else step_size*1.5)
        accepted_trial = False
        for backtrack in range(12):
            raw = current-step_size*grad
            if tv_prox == 'qualified':
                candidate = G.bounded_tv_prox(raw.reshape(n,n),
                    step_size*lam/current.numel()).reshape(-1)
            else:
                candidate, _, _, _ = C._collocation_tv_prox(f.model, f.projected,
                    raw, step_size*lam/current.numel(), None, None,
                    f.options, max_iter=100)
            candidate = candidate.clamp(0,1)
            try:
                pred, _, true_residual = f.predict(candidate)
                trial_loss = .5*torch.sum(abs(pred-target)**2)/norm2
                trial_total = float((trial_loss+lam*tv(candidate.reshape(n,n))).cpu())
                descent = float(torch.sum(grad*(candidate-current)).cpu())
                # Composite projected/proximal Armijo, allowing only descent.
                if trial_total < total and trial_total <= total+1e-4*min(descent,0):
                    f.coefficients = candidate
                    prediction = pred
                    accepted += 1
                    row.update(step_size=step_size, backtracks=backtrack,
                               trial_true_residual=true_residual)
                    accepted_trial = True
                    break
                rejected.append(dict(step=accepted, backtrack=backtrack,
                    trial_objective=trial_total, base_objective=total, true_residual=true_residual))
            except Exception:
                rejected.append(dict(step=accepted, backtrack=backtrack,
                                     traceback=traceback.format_exc()))
            step_size *= .5
        write(folder/'rejected_trials.json', rejected)
        if not accepted_trial:
            stop = 'LINE_SEARCH_STALLED'
            break
        if accepted % 25 == 0:
            snapshot(folder, f, accepted, prediction)
        print('STEP', accepted, 'residual', float(torch.sqrt(2*trial_loss).cpu()),
              'elapsed', round(time.perf_counter()-fit_started,2), flush=True)
    prediction, _, residual = f.predict()
    snapshot(folder, f, accepted, prediction)
    result = dict(experiment='GS-001', case=CASE, stop=stop, accepted_steps=accepted,
        frequency_hz=5e8, pixels=f.grid, centres=f.projected.grid_size, tv_prox=tv_prox,
        initial_data_residual=history[0]['data_residual'],
        final_data_residual=float((torch.linalg.vector_norm(prediction-target)/torch.linalg.vector_norm(target)).cpu()),
        final_true_residual=residual, fit_seconds=time.perf_counter()-fit_started,
        total_seconds=time.perf_counter()-started, qualification=qualifications,
        certified_tg002_recovery=False,
        recovery_note='Single frequency; sampled image/contour diagnostics are not a TG-002 all-frequency audit.')
    write(folder/'linear_solves.json', f.projected.linear_solve_stats)
    changes = [p for p,h in hashes.items() if digest(p) != h]
    if changes:
        raise RuntimeError('Sources changed during run: '+str(changes))
    result['source_hashes_unchanged'] = True
    write(folder/'result.json', result)
    report(folder)


def report(folder):
    """Truth access starts after the inverse result has been saved."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as Polygon
    from scipy.spatial import cKDTree
    from skimage.measure import find_contours
    result = read(folder/'result.json')
    initial = np.load(folder/'state_000.npz')
    final = np.load(folder/f'state_{result["accepted_steps"]:03d}.npz')
    row = B.row(CASE)
    truth_curve = curve_from(read(ROOT/row['truth']))
    problem = B.problem(CASE)
    boundary = problem.origin_m+problem.length_unit_m*truth_curve.values(16384)
    target_polygon = Polygon(np.column_stack([boundary.real,boundary.imag]))
    x,y = final['x'],final['y']
    xx,yy = np.meshgrid(x,y)
    truth = target_polygon.contains_points(np.column_stack([xx.ravel(),yy.ravel()])).reshape(xx.shape)
    diagnostics = {}
    contours_save = {}
    for label, state in (('initial',initial), ('final',final)):
        image = state['occupancy']
        mask = image >= .5
        intersection = np.count_nonzero(mask & truth)
        union = np.count_nonzero(mask | truth)
        contours = find_contours(image,.5)
        sampled = []
        lengths = []
        for i,c in enumerate(contours):
            cx = np.interp(c[:,1],np.arange(len(x)),x)
            cy = np.interp(c[:,0],np.arange(len(y)),y)
            z = cx+1j*cy
            contours_save[f'{label}_{i}'] = np.column_stack([cx,cy])
            ds = np.r_[0,np.cumsum(abs(np.diff(z)))]
            lengths.append(float(ds[-1]))
            t = np.linspace(0,ds[-1],max(2,int(np.ceil(ds[-1]/.0001))))
            sampled.append(np.interp(t,ds,z.real)+1j*np.interp(t,ds,z.imag))
        metric = dict(occupancy_iou=intersection/union if union else 0.,
            contour_count=len(contours), contour_lengths_m=lengths,
            area_relative_error=(np.count_nonzero(mask)/np.count_nonzero(truth)-1),
            image_relative_l2=float(np.linalg.norm(image-truth)/np.linalg.norm(truth)))
        if sampled:
            a = np.concatenate(sampled)
            target_xy = np.column_stack([boundary.real,boundary.imag])
            contour_xy = np.column_stack([a.real,a.imag])
            d1 = cKDTree(target_xy).query(contour_xy)[0]
            d2 = cKDTree(contour_xy).query(target_xy)[0]
            metric.update(sampled_symmetric_rms_mm=1000*np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2),
                          sampled_hausdorff_mm=1000*max(max(d1),max(d2)))
        if mask.any():
            delta = complex(xx[mask].mean()-xx[truth].mean(), yy[mask].mean()-yy[truth].mean())
            metric['centroid_error_mm'] = 1000*abs(delta)
        diagnostics[label] = metric
    np.savez_compressed(folder/'contours.npz', **contours_save)
    np.savez_compressed(folder/'truth_readout.npz',occupancy=truth,boundary=boundary)
    result['postfit_geometry'] = diagnostics
    write(folder/'result.json', result)
    figure,axes = plt.subplots(1,3,figsize=(12,4),constrained_layout=True)
    extent = [1000*x[0],1000*x[-1],1000*y[0],1000*y[-1]]
    for ax,image,title in zip(axes,[truth,initial['occupancy'],final['occupancy']],
        ['TG-002 truth','Centred circle start','GauGal: 0.5 GHz only']):
        ax.imshow(image,origin='lower',extent=extent,vmin=0,vmax=1,cmap='viridis')
        ax.plot(1000*boundary.real,1000*boundary.imag,'r-',lw=1,label='Truth boundary')
        ax.set(xlim=(400,600),ylim=(400,600),title=title,xlabel='x (mm)',ylabel='y (mm)')
    figure.suptitle(f'C-shape, contrast 13.3 | residual {result["initial_data_residual"]:.3%} → {result["final_data_residual"]:.3%}')
    figure.savefig(folder/'reconstruction.png',dpi=180)
    plt.close(figure)
    print('RESULT', json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','report'])
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--tv-prox',choices=['native','qualified'],default='native')
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.command == 'report':
        report(args.output)
        return
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute, (COORD/'source.lock').open('a') as source:
        print('WAITING_FOR_COMPUTE_LOCK',flush=True)
        fcntl.flock(compute,fcntl.LOCK_EX)
        fcntl.flock(source,fcntl.LOCK_SH)
        try:
            run(args.output,args.device,args.tv_prox)
        except Exception:
            args.output.mkdir(parents=True,exist_ok=True)
            write(args.output/'failure.json',dict(traceback=traceback.format_exc()))
            raise


if __name__ == '__main__':
    main()
