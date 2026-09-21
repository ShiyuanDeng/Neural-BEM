"""MC-001 sequential entry screen. All outputs go to a fresh evidence bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import time

import numpy as np

from .core import (
    BLOCK_NAMES, acquisition, fixtures, serialize, directions, normal_direction,
    family, nodal, solve, data_derivatives, hadamard, relative, blocks,
    block_mask, block_errors, crop_derivatives, moved,
)

LADDER = [16, 24, 32, 40, 48, 64, 80, 96]
TAILS = [1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-8]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


class Budget:
    def __init__(self):
        self.started = time.monotonic()
        self.counts = dict(assemblies=0, factorizations=0)

    def charge(self, assemblies=0, factorizations=0):
        if time.monotonic()-self.started > 1800:
            raise RuntimeError('30-minute numerical budget exhausted')
        for name, number, cap in [('assemblies', assemblies, 1000),
                                  ('factorizations', factorizations, 4000)]:
            if self.counts[name]+number > cap:
                raise RuntimeError(f'{name} budget exhausted')
            self.counts[name] += number
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2 > 8:
            raise RuntimeError('8 GiB peak RSS budget exhausted')

    def record(self):
        return dict(**self.counts, seconds=time.monotonic()-self.started,
                    peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024**2)


def hashes():
    roots = ['experiments/modal_entry_screen', 'experiments/laurent_fgm',
             'experiments/modal_muller_research', 'solvers/gpr_bem_kress',
             'solvers/ordered_boundary', 'solvers/periodic_kress']
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in roots for p in sorted(Path(root).rglob('*.py'))}


def dy_errors(values, reference, names):
    scale = max(np.linalg.norm(reference[n]) for n in names)
    return {n: relative(values[n], reference[n], max(1e-8*scale, 1e-300))
            for n in names}


def measured_solve(budget, system, mask=None):
    budget.charge(factorizations=1)
    return solve(system, mask)


def measured_family(budget, c, ko, ki, cutoff, grid, src, rec, dm=None):
    budget.charge(assemblies=1+len(dm or {}))
    return family(c, ko, ki, cutoff, grid, src, rec, dm)


def measured_nodal(budget, c, ko, ki, nodes, src, rec, dm=None, cutoff=None):
    budget.charge(assemblies=1, factorizations=1)
    return nodal(c, ko, ki, nodes, src, rec, dm, cutoff=cutoff)


def run_case(folder, name, c, kd, src, rec, budget):
    started = time.monotonic()
    dm = directions(c)
    physical = [n for n in dm if n != 'tangent']
    ko, ki = kd, kd/np.sqrt(2)
    print(f'{name} kD={kd:g}: independent controls', flush=True)
    kmax = 128
    coarse, dc = measured_family(budget, c, ko, ki, kmax, 512, src, rec, dm)
    fine, df = measured_family(budget, c, ko, ki, kmax, 1024, src, rec, dm)
    n1 = measured_nodal(budget, c, ko, ki, 384, src, rec, dm)
    n2 = measured_nodal(budget, c, ko, ki, 512, src, rec, dm, cutoff=kmax)
    oracle_error = relative(n1['y'], n2['y'])
    oracle_dy = dy_errors(n1['derivatives'], n2['derivatives'], physical)
    reference_ok = oracle_error <= 1e-8 and max(oracle_dy.values()) <= 1e-5
    ladder = []
    selected = None
    for cutoff in LADDER:
        system = fine.crop(cutoff)
        derivatives = crop_derivatives(df, kmax, cutoff)
        sol = measured_solve(budget, system)
        dy = data_derivatives(system, derivatives, sol)
        errors = dy_errors(dy, n2['derivatives'], physical)
        field_error = relative(sol['y'], n2['y'])
        grid_error = max(block_errors(coarse.crop(cutoff).a-np.eye(len(system.a)),
                                      system.a-np.eye(len(system.a))).values())
        grid_deriv = max(max(block_errors(x[0], derivatives[n][0]).values())
                         for n, x in crop_derivatives(dc, kmax, cutoff).items()
                         if n in physical)
        row = dict(cutoff=cutoff, field_error=field_error,
                   worst_derivative_error=max(errors.values()),
                   matrix_grid_error=grid_error, derivative_grid_error=grid_deriv,
                   passed=bool(reference_ok and field_error <= 1e-8
                               and max(errors.values()) <= 1e-5
                               and grid_error <= 1e-8 and grid_deriv <= 1e-6))
        ladder.append(row)
        if row['passed']:
            selected = (system, derivatives, sol, dy)
            break
    if selected is None:
        cutoff = 96
        system = fine.crop(cutoff)
        derivatives = crop_derivatives(df, kmax, cutoff)
        sol = measured_solve(budget, system)
        dy = data_derivatives(system, derivatives, sol)
        qualified = False
    else:
        system, derivatives, sol, dy = selected
        cutoff = system.cutoff
        qualified = True
    size = len(system.a)
    identity = np.eye(size)
    remainder = system.a-identity
    # Data/FD comparison is independent of the derivative amplitude algebra.
    fd_rows = []
    check_name = 'p6_cos'
    for step in (1e-4, 5e-5, 2.5e-5):
        plus, _ = measured_family(budget, moved(c, dm[check_name], step), ko, ki,
                                  cutoff, 1024, src, rec)
        minus, _ = measured_family(budget, moved(c, dm[check_name], -step), ko, ki,
                                   cutoff, 1024, src, rec)
        fd = (plus.a-minus.a)/(2*step)
        yfd = (measured_solve(budget, plus)['y']-measured_solve(budget, minus)['y'])/(2*step)
        fd_rows.append(dict(step=step, matrix_errors=block_errors(fd, derivatives[check_name][0]),
                            data_error=relative(yfd, dy[check_name])))
    qualified = bool(qualified and max(fd_rows[-1]['matrix_errors'].values()) <= 1e-4
                     and fd_rows[-1]['data_error'] <= 1e-4)
    hdy = hadamard(c, dm, ko, ki, sol, cutoff)
    herrors = dy_errors(hdy, n2['derivatives'], physical)
    idx = np.concatenate((np.arange(kmax-cutoff, kmax+cutoff+1),
                          2*kmax+1+np.arange(kmax-cutoff, kmax+cutoff+1)))
    projected_error = max(block_errors(n2['projected'][np.ix_(idx, idx)]-identity,
                                       remainder).values())
    qualified = bool(qualified and projected_error <= 1e-7)
    # Curves do not impose a band. Individual matrices have independent top sets.
    curve_tols = np.logspace(-2, -8, 31)
    curves = []
    for tol in curve_tols:
        fm = block_mask(remainder, tol)
        dms = [block_mask(derivatives[n][0], tol) for n in physical]
        union = np.logical_or.reduce([fm]+dms)
        curves.append(dict(tolerance=float(tol), forward_count=int(fm.sum()),
                           derivative_counts={n: int(m.sum()) for n, m in zip(physical, dms)},
                           union_count=int(union.sum()), denominator=int(remainder.size)))
    scans, masks = [], {}
    for tol in TAILS:
        fm = block_mask(remainder, tol)
        common = np.logical_or.reduce([fm]+[block_mask(derivatives[n][0], tol) for n in physical])
        for arm, mask in [('forward', fm), ('common', common)]:
            key = f'{arm}_{tol:g}'
            masks[key] = mask
            estimate = measured_solve(budget, system, mask)
            edy = data_derivatives(system, derivatives, estimate, mask)
            ehy = hadamard(c, dm, ko, ki, estimate, cutoff)
            field_error = relative(estimate['y'], n2['y'])
            errors = dy_errors(edy, n2['derivatives'], physical)
            herrors_c = dy_errors(ehy, n2['derivatives'], physical)
            # Fixed scale for flux; do not normalize each candidate separately.
            flux_scale = np.concatenate((np.ones(size//2), np.ones(size//2)/ko))
            residual = flux_scale[:, None]*(system.a@estimate['x']-system.b)
            resid_error = float(np.linalg.norm(residual)/np.linalg.norm(flux_scale[:, None]*system.b))
            represented = int(mask.sum())+size
            ratio = represented/remainder.size
            scans.append(dict(key=key, arm=arm, tolerance=tol, count=int(mask.sum()),
                              represented_slots=represented, represented_fraction=ratio,
                              field_error=field_error, derivative_errors=errors,
                              worst_derivative_error=max(errors.values()),
                              hadamard_errors=herrors_c, worst_hadamard_error=max(herrors_c.values()),
                              full_residual=resid_error,
                              dirichlet_error=relative(estimate['x'][:size//2], sol['x'][:size//2]),
                              flux_error=relative(estimate['x'][size//2:], sol['x'][size//2:]),
                              passed=bool(qualified and field_error <= 1e-6
                                          and max(errors.values()) <= 1e-3 and ratio <= .5)))
    passing = [r for r in scans if r['arm']=='common' and r['passed']]
    winner = min(passing, key=lambda r: r['represented_slots']) if passing else None
    thresholds = []
    for obj, array in [('forward', remainder)]+[(n, derivatives[n][0]) for n in physical]:
        for tol in TAILS:
            counts = [int(np.count_nonzero(np.abs(b) > tol*np.max(np.abs(b)))) for b in blocks(array)]
            thresholds.append(dict(object=obj, threshold=tol, counts=dict(zip(BLOCK_NAMES, counts))))
    case = dict(name=name, kd=kd, ko=ko, ki=ki, cutoff=cutoff, grid=1024,
                qualified=qualified, coefficients=serialize(c),
                directions={n: serialize(v) for n, v in dm.items()},
                physical_directions=physical, dimension=size, full_slots=size*size,
                identity_slots=size, oracle_field_refinement=oracle_error,
                oracle_derivative_refinement=oracle_dy, ladder=ladder, finite_differences=fd_rows,
                projected_operator_error=projected_error, full_hadamard_errors=herrors,
                tangent_data_norm=float(np.linalg.norm(dy['tangent'])),
                curves=curves, thresholds=thresholds, scans=scans, winner=winner,
                seconds=time.monotonic()-started)
    folder.mkdir()
    dump(folder/'case.json', case)
    np.savez_compressed(folder/'arrays.npz', a=system.a, b=system.b, c=system.c,
                        receiver_rhs=system.receiver_rhs, state=sol['x'],
                        receiver_state=sol['rx'], oracle_y=n2['y'],
                        oracle_dy=np.stack([n2['derivatives'][n] for n in physical]),
                        da=np.stack([derivatives[n][0] for n in dm]),
                        db=np.stack([derivatives[n][1] for n in dm]),
                        dc=np.stack([derivatives[n][2] for n in dm]),
                        sources=src, receivers=rec, **{f'mask_{k}': v for k, v in masks.items()})
    print(f'  K={cutoff} qualified={qualified}; common-mask winner: '
          f'{winner["represented_fraction"]:.1%}' if winner else
          f'  K={cutoff} qualified={qualified}; no common-mask pass', flush=True)
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    budget = Budget()
    source_hashes = hashes()
    shapes = fixtures()
    src, rec = acquisition()
    config = dict(stage='A', electrical_sizes=[2., 10., 30.], cutoff_ladder=LADDER,
                  tail_tolerances=TAILS, coefficients={n: serialize(c) for n, c in shapes.items()},
                  sources=src.tolist(), receivers=rec.tolist(), material_ratio=1/np.sqrt(2),
                  matrix_reference_cutoff=128, grids=[512, 1024], nodal_nodes=[384, 512],
                  release='at least 2 noncircles pass both kD 2 and 10 at <=50% slots',
                  sources_sha256=source_hashes, python=platform.python_version(),
                  revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  blas_threads={k: os.environ.get(k) for k in
                                ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
                  host_load_start=list(os.getloadavg()))
    dump(args.output/'config.json', config)
    cases = []
    failure = None
    try:
        for name, c in shapes.items():
            for kd in config['electrical_sizes']:
                cases.append(run_case(args.output/f'{name}_kd{kd:g}', name, c, kd,
                                      src, rec, budget))
                dump(args.output/'progress.json', dict(cases=[dict(name=x['name'], kd=x['kd'],
                          qualified=x['qualified'], winner=x['winner']) for x in cases], work=budget.record()))
                failed_low = [x for x in cases if x['name'] != 'circle' and x['kd'] in (2, 10)
                              and not x['qualified']]
                if len(failed_low) >= 2:
                    raise RuntimeError('Two noncircular low-frequency qualification failures')
    except Exception as error:
        failure = repr(error)
        print(f'STOP: {failure}', flush=True)
    drift = [p for p, h in source_hashes.items()
             if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
    qualified_shapes = [name for name in shapes if name != 'circle'
                        and all(any(c['name']==name and c['kd']==kd and c['winner']
                                    for c in cases) for kd in (2, 10))]
    summary = dict(stage='A', status='COMPLETE' if failure is None else 'STOPPED',
                   failure=failure, source_drift=drift, cases=len(cases),
                   qualified_cases=sum(c['qualified'] for c in cases),
                   qualifying_noncircles=qualified_shapes,
                   stage_b_released=bool(failure is None and not drift and len(qualified_shapes)>=2),
                   work=budget.record(), host_load_end=list(os.getloadavg()))
    dump(args.output/'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
