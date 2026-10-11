"""Registered supplemental phase sampling and physical readout diagnostics."""
from __future__ import annotations

import argparse
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from bem_inverse.continuation.forward import PointSourceAcquisition, solve
from bem_inverse.io import curve_from, read, write, digest
from experiments.benchmark import campaign as B
from .cvx002 import ROOT, disk_field, incident, relative, paired_check, resample


def square(n):
    axis = np.linspace(-2.4, 2.4, n)
    x, y = np.meshgrid(axis, axis)
    ids = np.arange(n*n).reshape(n, n)
    cycle = np.r_[ids[0, :], ids[1:, -1], ids[-1, -2::-1], ids[-2:0:-1, 0]]
    return axis, np.column_stack((x.ravel(), y.ravel())), cycle


def boundary_phase(ratio):
    edges = np.angle(np.roll(ratio, -1)/ratio)
    return dict(winding=float(edges.sum()/(2*np.pi)), min_abs=float(abs(ratio).min()),
                max_wrapped_increment=float(abs(edges).max()))


def grid_phase(ratio, axis, cycle):
    ex = np.angle(ratio[:, 1:]/ratio[:, :-1])
    ey = np.angle(ratio[1:, :]/ratio[:-1, :])
    residues = (ex[:-1]+ey[:, 1:]-ex[1:]-ey[:, :-1])/(2*np.pi)
    indices = np.rint(residues).astype(int)
    iy, ix = np.nonzero(indices)
    centers = np.column_stack(((axis[ix]+axis[ix+1])/2, (axis[iy]+axis[iy+1])/2))
    boundary = boundary_phase(ratio.ravel()[cycle])
    return dict(positive=int(np.sum(indices > 0)), negative=int(np.sum(indices < 0)),
                total=int(np.count_nonzero(indices)), net_index=int(indices.sum()),
                integer_error=float(abs(residues-indices).max()), boundary=boundary,
                telescoping_error=float(abs(indices.sum()-boundary['winding'])),
                min_abs=float(abs(ratio).min()), max_wrapped_increment=float(max(abs(ex).max(), abs(ey).max())),
                centers=centers, indices=indices[iy, ix])


def same_sign_displacement(a, b):
    distances = []
    for sign in (-1, 1):
        aa = np.asarray(a['centers']).reshape(-1, 2)[np.asarray(a['indices']) == sign]
        bb = np.asarray(b['centers']).reshape(-1, 2)[np.asarray(b['indices']) == sign]
        if len(aa) != len(bb):
            return None
        if len(aa):
            distances.extend(cKDTree(aa).query(bb)[0]); distances.extend(cKDTree(bb).query(aa)[0])
    return float(max(distances, default=0)*50)


def phase_start(contrast, folder):
    problem = B.problem(f'circle__c{contrast:g}')
    source = problem.real[0].acquisition.sources[0]
    strength = problem.real[0].acquisition.strength
    records = []; arrays = {}
    for n in (41, 81, 161):
        axis, points, cycle = square(n); arrays[f'axis{n}'] = axis
        for j, observation in enumerate(problem.real[:3]):
            k = observation.wavenumber
            low = disk_field(points, k, contrast, source, strength, cutoff=36)
            high = disk_field(points, k, contrast, source, strength, cutoff=46)
            inc = incident(points, k, source, strength)[0]
            ratio = (high/inc).reshape(n, n)
            record = grid_phase(ratio, axis, cycle)
            record.update(grid=n, frequency_hz=observation.frequency_hz, mie_relative=relative(low, high))
            record['qualified'] = bool(np.isfinite(ratio).all() and record['mie_relative'] < 1e-8
                                      and record['integer_error'] < 1e-10 and record['telescoping_error'] < 1e-10)
            records.append(record)
            arrays[f'ratio{n}_frequency{j}'] = ratio
            arrays[f'ratio36_{n}_frequency{j}'] = (low/inc).reshape(n, n)
            np.savez_compressed(folder/f'initial_c{contrast:g}.npz', **arrays)
            write(folder/f'initial_c{contrast:g}.json', dict(complete=False, records=records))
            print('PHASE', contrast, n, j, record['positive'], record['negative'], record['min_abs'], flush=True)
    comparisons = []
    for j in range(3):
        a, b = records[3+j], records[6+j]
        comparisons.append(dict(frequency_hz=a['frequency_hz'], counts_stable=(a['positive'], a['negative']) == (b['positive'], b['negative']),
                                same_sign_max_nearest_displacement_mm=same_sign_displacement(a, b)))
    np.savez_compressed(folder/f'initial_c{contrast:g}.npz', **arrays)
    result = dict(complete=True, qualified=all(r['qualified'] for r in records), records=records, refinement81_to161=comparisons,
                  interpretation='Sampled phase evidence, not a continuous zero certificate')
    write(folder/f'initial_c{contrast:g}.json', result)
    return result


def measured_phase(folder):
    problem = B.problem('c_shape__c13.3')
    truth = curve_from(read(ROOT/B.row('c_shape__c13.3')['truth']))
    source = problem.real[0].acquisition.sources[0]
    strength = problem.real[0].acquisition.strength
    records = []; arrays = {}
    for n in (41, 81, 161):
        _, points, cycle = square(n); boundary = points[cycle]
        arrays[f'points{n}'] = boundary
        acq = PointSourceAcquisition(source[None], boundary, strength, False)
        for j, observation in enumerate(problem.real[:3]):
            k = observation.wavenumber
            inc = incident(boundary, k, source, strength)[0]
            total = [solve(truth, k, problem.contrast, acq, nodes, execution_backend='cpu').prediction[0]+inc for nodes in (512, 1024)]
            ratio = total[-1]/inc
            record = boundary_phase(ratio)
            record.update(grid=n, perimeter_points=len(boundary), frequency_hz=observation.frequency_hz,
                          field_refinement=relative(total[0], total[1]))
            record['qualified'] = bool(np.isfinite(ratio).all() and record['field_refinement'] < 1e-7
                                      and abs(record['winding']-round(record['winding'])) < 1e-10)
            records.append(record)
            arrays[f'ratio{n}_frequency{j}'] = ratio
            arrays[f'ratio512_{n}_frequency{j}'] = total[0]/inc
            np.savez_compressed(folder/'measured_c_shape.npz', **arrays)
            write(folder/'measured_c_shape.json', dict(complete=False, records=records))
            print('BOUNDARY', n, j, record['winding'], record['max_wrapped_increment'], flush=True)
    np.savez_compressed(folder/'measured_c_shape.npz', **arrays)
    stable = all(len({round(r['winding']) for r in records if r['frequency_hz'] == f}) == 1 for f in {r['frequency_hz'] for r in records})
    result = dict(complete=True, qualified=all(r['qualified'] for r in records), records=records, sampled_winding_stable=stable,
                  interpretation='Refined sampled boundary winding, not a continuous winding certificate')
    write(folder/'measured_c_shape.json', result)
    return result


def geometry_readouts(folder):
    problem = B.problem('circle__c0.5')
    baseline_folder = folder/'starting_circle'; baseline_folder.mkdir()
    baseline = paired_check('circle__c0.5', problem.initial, baseline_folder)
    truth_curve = curve_from(read(ROOT/B.row('circle__c0.5')['truth']))
    truth = resample(truth_curve.values(16384), 16384)
    truth_points = np.column_stack((truth.real, truth.imag))
    rows = []
    curves = [('prescribed_circle', problem.initial, None, None)]
    for run in ('screen', 'refinement57'):
        for span in (0, 4):
            arm = folder.parent/run/'circle__c0.5'/f'span{span}'
            curves.append((f'{run}/span{span}', curve_from(read(arm/'final_curve.json')), read(arm/'result.json'), arm))
    for name, curve, result, arm in curves:
        z = resample(curve.values(16384), 16384)
        xy = np.column_stack((z.real, z.imag))
        d1 = cKDTree(truth_points).query(xy)[0]; d2 = cKDTree(xy).query(truth_points)[0]
        row = dict(name=name, sampled_rms_mm=float(50*np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2)),
                   sampled_hausdorff_mm=float(50*max(d1.max(), d2.max())))
        paired = baseline if result is None else result['paired']
        row.update(paired_rms=paired['rms_relative_residual'], paired_max=paired['maximum_relative_residual'],
                   paired_qualified=paired['qualified'], count_below_003=paired['frequencies_below_003'])
        if result is not None:
            arrays = np.load(arm/'final_scoring.npz')
            areas = []
            for k in arrays.files:
                if k.startswith('contour_'):
                    p = arrays[k]
                    areas.append(float(abs(np.sum(p[:-1].real*p[1:].imag-p[1:].real*p[:-1].imag))/2*2500))
            row.update(threshold_component_areas_mm2=sorted(areas, reverse=True),
                       discarded_components=result['final']['readout_discarded_components'],
                       all_contour_sampled_rms_mm=result['final']['sampled_symmetric_rms_mm'],
                       all_contour_sampled_hausdorff_mm=result['final']['sampled_hausdorff_mm'])
        rows.append(row)
    write(folder/'readout_comparison.json', dict(rows=rows, baseline=baseline, qualified=all(r['paired_qualified'] for r in rows)))
    return rows


def plots(folder, starts):
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), constrained_layout=True)
    for row, contrast in enumerate((4, 13.3)):
        arrays = np.load(folder/f'initial_c{contrast:g}.npz')
        records = starts[row]['records'][6:]
        for j in range(3):
            ax = axes[row, j]
            ax.imshow(np.angle(arrays[f'ratio161_frequency{j}']), origin='lower', extent=(-120,120,-120,120), cmap='twilight', vmin=-np.pi, vmax=np.pi)
            record = records[j]
            centers = np.asarray(record['centers']).reshape(-1,2)*50
            indices = np.asarray(record['indices'])
            for sign, marker, color in ((1,'+','white'),(-1,'x','black')):
                zz = centers[indices == sign]
                ax.scatter(zz[:,0], zz[:,1], marker=marker, color=color, s=45, linewidths=1.4)
            ax.set(title=f"Contrast {contrast:g}, {record['frequency_hz']/1e9:g} GHz: {record['positive']}+ / {record['negative']}−",
                   xlabel='x (mm)', ylabel='y (mm)', aspect='equal')
    fig.suptitle('Prescribed starting field: phase and sampled winding defects on 161 x 161 grid')
    fig.savefig(folder/'phase.png', dpi=150); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); folder = args.output; folder.mkdir(parents=True, exist_ok=False)
    started = perf_counter(); summary = dict(complete=False)
    def interrupted(signum, frame):
        raise TimeoutError(f'External watchdog signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    prior = read(folder.parent/'refinement57'/'manifest.json')['source_hashes']
    paths = sorted(set(prior) | {str(Path(__file__).resolve().relative_to(ROOT)), 'docs/iterations/convexification/CVX-002_diagnostics_plan.md'})
    hashes = {p: digest(ROOT/p) for p in paths}
    inputs = [folder.parent/run/name for run in ('screen', 'refinement57') for name in ('manifest.json', 'summary.json')]
    inputs.extend(folder.parent/run/'circle__c0.5'/f'span{span}'/name
                  for run in ('screen', 'refinement57') for span in (0,4)
                  for name in ('final_curve.json', 'result.json', 'final_scoring.npz'))
    input_hashes = {str(p.resolve().relative_to(ROOT)): digest(p) for p in inputs}
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for p in paths: archive.add(ROOT/p, arcname=p)
    write(folder/'manifest.json', dict(source_hashes=hashes, head=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                                       input_hashes=input_hashes, experiment='CVX-002 supplementary diagnostics', command=[sys.executable,*sys.argv], python=sys.version))
    try:
        B.verify(require_inputs=True)
        starts = [phase_start(contrast, folder) for contrast in (4, 13.3)]
        measured = measured_phase(folder)
        readouts = geometry_readouts(folder)
        plots(folder, starts)
        summary.update(complete=True, qualified=all(s['qualified'] for s in starts) and measured['qualified'] and all(r['paired_qualified'] for r in readouts),
                       initial_phase=starts, measured_phase=measured, readouts=readouts)
    except BaseException:
        (folder/'failure.txt').write_text(traceback.format_exc()); raise
    finally:
        summary.update(seconds=perf_counter()-started, source_hashes_unchanged=all(digest(ROOT/p)==h for p,h in hashes.items()))
        summary['input_hashes_unchanged'] = all(digest(ROOT/p)==h for p,h in input_hashes.items())
        write(folder/'summary.json', summary)


if __name__ == '__main__': main()
