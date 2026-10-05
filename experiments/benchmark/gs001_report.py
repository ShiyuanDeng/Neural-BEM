"""Read-only validation and combined GS-001 probe report; no forward calls."""
import hashlib
import json
import tarfile
from pathlib import Path

import numpy as np

from .gs001 import OUT, ROOT, CASE, INDEX
from . import campaign as B
from bem_inverse.io import read, write, curve_from


def validate(folder):
    result = read(folder/'result.json')
    manifest = read(folder/'manifest.json')
    assert manifest['case'] == CASE and manifest['frequency_index'] == INDEX
    assert manifest['frequency_hz'] == 5e8 and manifest['localization'] == 'none'
    assert result['source_hashes_unchanged']
    with tarfile.open(folder/'sources.tar.gz') as archive:
        for path, expected in manifest['source_hashes'].items():
            p = Path(path)
            name = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'external/'+str(p.relative_to('/home/drdeng/Gau-Gal'))
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == expected
    endpoint = np.load(folder/f'state_{result["accepted_steps"]:03d}.npz')
    target = B.problem(CASE).real[INDEX].scattered
    residual = np.linalg.norm(endpoint['prediction']-target)/np.linalg.norm(target)
    assert abs(residual-result['final_data_residual']) <= 1e-12
    assert endpoint['coefficients'].min() >= 0 and endpoint['coefficients'].max() <= 1
    history = read(folder/'history.json')
    assert abs(history[0]['data_residual']-result['initial_data_residual']) <= 1e-12
    assert all(r['forward_true_residual'] <= 1e-6 and r['adjoint_true_residual'] <= 1e-6 for r in history)
    # Each schedule interval keeps a fixed composite objective.
    assert all(b['objective'] <= a['objective']+1e-12 for a,b in zip(history,history[1:]) if a['lam'] == b['lam'])
    assert result['final_true_residual'] <= 1e-6
    return dict(folder=str(folder.relative_to(ROOT)), source_archive_verified=True,
                saved_prediction_residual_verified=True, bounded_occupancy=True,
                accepted_solve_gates_passed=True, interval_descent_verified=True,
                result=result)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    B.verify(require_inputs=True)
    rows = [validate(OUT), validate(OUT/'qualified_tv')]
    write(OUT/'comparison_validation.json',dict(passed=True,runs=rows,benchmark_seal_verified=True))
    results = [r['result'] for r in rows]
    fig,axes = plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    for folder,label,result in zip([OUT,OUT/'qualified_tv'],['Native finite TV step','Corrected bounded TV step'],results):
        history = read(folder/'history.json')
        times = [r['elapsed_seconds'] for r in history]+[result['fit_seconds']]
        steps = [r['step'] for r in history]+[result['accepted_steps']]
        residuals = [100*r['data_residual'] for r in history]+[100*result['final_data_residual']]
        axes[0].plot(times,residuals,label=label)
        axes[1].plot(steps,residuals,label=label)
    for ax in axes:
        ax.set(ylabel='Relative data residual (%)',yscale='log')
        ax.axhline(.3,color='grey',ls=':',label='0.3% discrepancy target')
        ax.grid(alpha=.2)
        ax.legend()
    axes[0].set_xlabel('Fit wall time (s)')
    axes[1].set_xlabel('Accepted updates')
    fig.suptitle('C-shape, contrast 13.3 — known-material GauGal adaptation, 0.5 GHz only')
    fig.savefig(OUT/'residual_history.png',dpi=180)
    plt.close(fig)
    truth = curve_from(read(ROOT/B.row(CASE)['truth']))
    problem = B.problem(CASE)
    boundary = problem.origin_m+problem.length_unit_m*truth.values(16384)
    states = [np.load(OUT/'state_000.npz')]+[
        np.load(folder/f'state_{result["accepted_steps"]:03d}.npz') for folder,result in zip([OUT,OUT/'qualified_tv'],results)]
    # Show all thresholded components, including any unwanted fragments.
    all_x, all_y = [boundary.real], [boundary.imag]
    for state in states:
        iy,ix = np.where(state['occupancy'] >= .5)
        if len(ix):
            all_x.append(state['x'][ix])
            all_y.append(state['y'][iy])
    all_x,all_y = np.concatenate(all_x),np.concatenate(all_y)
    centre = ((all_x.max()+all_x.min())/2,(all_y.max()+all_y.min())/2)
    half = max(.1,(all_x.max()-all_x.min())/2+.02,(all_y.max()-all_y.min())/2+.02)
    xlim = ((centre[0]-half)*1000,(centre[0]+half)*1000)
    ylim = ((centre[1]-half)*1000,(centre[1]+half)*1000)
    fig,axes = plt.subplots(1,3,figsize=(12,4),constrained_layout=True)
    for ax,state,title in zip(axes,states,['Prescribed circle','Native TV: stalled','Corrected TV: final']):
        x,y = state['x'],state['y']
        ax.imshow(state['occupancy'],origin='lower',extent=[x[0]*1000,x[-1]*1000,y[0]*1000,y[-1]*1000],
                  vmin=0,vmax=1,cmap='viridis')
        ax.contour(x*1000,y*1000,state['occupancy'],levels=[.5],colors='white',linewidths=1)
        ax.plot(boundary.real*1000,boundary.imag*1000,'r-',lw=1)
        ax.set(xlim=xlim,ylim=ylim,title=title,xlabel='x (mm)',ylabel='y (mm)')
    fig.suptitle('0.5 GHz, contrast 13.3 | red: truth, white: fixed 0.5 occupancy contour')
    fig.savefig(OUT/'comparison.png',dpi=180)
    plt.close(fig)
    print(json.dumps(dict(passed=True, results=results)))


if __name__ == '__main__':
    main()
