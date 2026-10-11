"""CVX-001 analytic formulation controls; no inverse solve or truth data.

Run with EMNerf Python from the repository root. The output directory must
not exist. Predictions and gates are in docs/iterations/convexification/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import scipy
from scipy.special import hankel1, h1vp


ROOT = Path(__file__).resolve().parents[2]


def scalar(z):
    return dict(real=float(np.real(z)), imag=float(np.imag(z)))


def log_jets(k, contrast, interior):
    """Spatial derivatives 0..3 of v=log(u/exp(ikx))/k² at x=0.

    Compute from independent exact incident/reflected/transmitted field jets,
    rather than insert the predicted log jump formulas.
    """
    s = np.sqrt(contrast)
    reflection, transmission = (1-s)/(1+s), 2/(1+s)
    if interior:
        jets = np.array([transmission*(1j*k*s)**j for j in range(4)])
    else:
        jets = np.array([(1j*k)**j+reflection*(-1j*k)**j for j in range(4)])
    a, b, c = jets[1:]/jets[0]
    log = np.array([np.log(jets[0]), a, b-a*a, c-3*a*b+2*a**3])
    log[1] -= 1j*k  # incident normalization
    return log/k**2, jets


def interface_check():
    rows = []
    for contrast in (.5, 4., 13.3):
        for k in (.5, 2., 5.):
            left, ul = log_jets(k, contrast, False)
            right, ur = log_jets(k, contrast, True)
            jump = right-left
            predicted = np.array([0, 0, -(contrast-1),
                                  2j*k*np.sqrt(contrast)*(contrast-1)])
            algebra_error = float(np.max(np.abs(jump-predicted)
                                         / np.maximum(1, np.abs(predicted))))
            continuity = float(np.max(np.abs(ul[:2]-ur[:2])))
            derivative_errors, q_jumps = [], []
            for relative_step in (1e-3, 5e-4):
                h = relative_step*k
                jp = log_jets(k+h, contrast, True)[0]-log_jets(k+h, contrast, False)[0]
                jm = log_jets(k-h, contrast, True)[0]-log_jets(k-h, contrast, False)[0]
                q_jump = (jp-jm)/(2*h)
                expected = np.array([0, 0, 0, 2j*np.sqrt(contrast)*(contrast-1)])
                derivative_errors.append(float(np.max(np.abs(q_jump-expected)
                                                       / np.maximum(1, np.abs(expected)))))
                q_jumps.append(q_jump)
            rows.append(dict(contrast=contrast, k=k, continuity_error=continuity,
                             normalized_algebra_error=algebra_error,
                             frequency_fd_errors=derivative_errors,
                             v_xx_jump=scalar(jump[2]),
                             q_xx_jump_fine=scalar(q_jumps[-1][2]),
                             q_xxx_jump_fine=scalar(q_jumps[-1][3])))
    return rows


def paired_check():
    theta = 2*np.pi*np.arange(24)/24
    receiver = theta+.2
    basis = lambda a: np.column_stack([np.ones_like(a), np.cos(a), np.sin(a)])
    bs, br = basis(theta), basis(receiver)
    coefficient = np.diag([-np.cos(.2), 1., 1.])
    full = br@coefficient@bs.T  # receiver, source
    columns = []
    for a in range(3):
        for b in range(a, 3):
            entry = np.outer(br[:, a], bs[:, b])
            if a != b:
                entry += np.outer(br[:, b], bs[:, a])
            columns.append(entry)
    full_map = np.stack(columns, axis=-1).reshape(-1, 6)
    pair_map = np.stack([np.diag(c) for c in columns], axis=-1)
    ps, fs = np.linalg.svd(pair_map, compute_uv=False), np.linalg.svd(full_map, compute_uv=False)
    # Reciprocity is K(r,s)=K(s,r) for arbitrary angles, not symmetry of a
    # matrix whose receiver and source grids are shifted from one another.
    angles = np.linspace(.031, 6.12, 101)
    reciprocal = np.cos(angles[:, None]-theta)-np.cos(.2)
    reverse = (np.cos(theta[:, None]-angles)-np.cos(.2)).T
    return dict(paired_max=float(np.abs(np.diag(full)).max()),
                full_rms=float(np.sqrt(np.mean(full**2))),
                full_max=float(np.abs(full).max()),
                reciprocity_error=float(np.max(np.abs(reciprocal-reverse))),
                paired_singular_values=ps.tolist(), full_singular_values=fs.tolist(),
                paired_rank=int(np.sum(ps>ps[0]*1e-12)),
                full_rank=int(np.sum(fs>fs[0]*1e-12)),
                unknown_symmetric_coefficients=6), full


def alias_check():
    radius, inner, theta0 = .30, .15, .2
    angles = theta0+2*np.pi*np.arange(24)/24
    dense_angles = theta0+2*np.pi*np.arange(2400)/2400
    rows, amplifications = [], []
    for ghz in (.25, 1., 2.5):
        # SI constants and epsilon_background=6 agree with frozen benchmark.
        k = 2*np.pi*ghz*1e9*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6)
        sample = np.exp(24j*(angles-theta0))-1
        dense = np.exp(24j*(dense_angles-theta0))-1
        normal = k*(h1vp(24, k*radius)/hankel1(24, k*radius)
                    -h1vp(0, k*radius)/hankel1(0, k*radius))
        amps = [float(abs(hankel1(n, k*inner)/hankel1(n, k*radius)))
                for n in (0, 12, 24, 36)]
        amplifications.append(amps)
        rows.append(dict(frequency_ghz=ghz, k_per_m=float(k),
                         sample_max=float(np.max(np.abs(sample))),
                         off_grid_max=float(np.max(np.abs(dense))),
                         sampled_normal_derivative_abs_per_m=float(abs(normal)),
                         inward_amplification=dict(zip(('0', '12', '24', '36'), amps))))
    return rows, np.array(amplifications)


def weight_check():
    with localcontext() as ctx:
        ctx.prec = 70
        log_max = Decimal(12)/Decimal(81)**10
        log_min = Decimal(12)/Decimal(122)**10
        span = log_max-log_min
        high_precision = dict(log_min=str(log_min), log_max=str(log_max),
                              log_dynamic_range=str(span),
                              weight_ratio_minus_one=str(span.exp()-1))
    x = np.linspace(-1, 1, 129)
    xx, yy = np.meshgrid(x, x)
    weights = np.exp(12*(xx**2+(yy+10)**2)**(-10))
    return dict(printed_parameters=dict(x0=[0, -10], beta=20, lam=6),
                high_precision=high_precision,
                float64_weight_min=float(weights.min()),
                float64_weight_max=float(weights.max()),
                float64_unique_weights=int(np.unique(weights).size),
                generic_log_spans=[dict(span=t, ratio=float(np.exp(t))) for t in (10, 40, 100)])


def plot(out, full, amps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    image = axes[0].imshow(full, cmap='coolwarm', vmin=-2, vmax=2)
    axes[0].plot(np.arange(24), np.arange(24), 'k.', ms=3, label='Observed pairs: zero')
    axes[0].set(xlabel='Source index', ylabel='Receiver index',
                title='A reciprocal kernel invisible to all pairs')
    axes[0].legend(loc='upper right', fontsize=8)
    fig.colorbar(image, ax=axes[0], shrink=.8)
    for row, frequency in zip(amps, (.25, 1., 2.5)):
        axes[1].semilogy([0, 12, 24, 36], row, 'o-', label=f'{frequency:g} GHz')
    axes[1].set(xlabel='Angular mode n', ylabel='|Hn(k · 0.15) / Hn(k · 0.30)|',
                title='Inward continuation amplifies missing modes')
    axes[1].legend()
    axes[1].grid(alpha=.25)
    fig.savefig(out/'diagnostics.png', dpi=160)
    fig.savefig(out/'diagnostics.svg')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    source_files = [Path(__file__), ROOT/'docs/iterations/convexification/CVX-001_plan.md',
                    ROOT/'experiments/cleaned_interface/benchmark.py',
                    ROOT/'experiments/benchmark/scenes.py']
    manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                    command=[sys.executable, *sys.argv], python=sys.version,
                    numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform(),
                    threads={k: os.getenv(k) for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                                     'MKL_NUM_THREADS')},
                    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in source_files},
                    scope='Analytic component checks only; no inverse or target data used.')
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    result = {}
    try:
        result['interface'] = interface_check()
        result['paired'], full = paired_check()
        result['sampling'], amps = alias_check()
        result['weight'] = weight_check()
        gates = dict(
            interface_algebra=all(r['normalized_algebra_error']<=1e-11
                                 and r['continuity_error']<=1e-11 for r in result['interface']),
            interface_fd=all(r['frequency_fd_errors'][-1]<=1e-6 for r in result['interface']),
            paired_nullspace=result['paired']['paired_max']<=1e-12
                             and result['paired']['full_rms']>.1
                             and result['paired']['reciprocity_error']<=1e-12
                             and result['paired']['paired_rank']==5
                             and result['paired']['full_rank']==6,
            fixed_source_alias=all(r['sample_max']<=1e-12 and r['off_grid_max']>1
                                   and np.isfinite(r['sampled_normal_derivative_abs_per_m'])
                                   and r['sampled_normal_derivative_abs_per_m']>1e-6
                                   for r in result['sampling']),
            literal_weight=result['weight']['float64_unique_weights']==1
                           and result['weight']['float64_weight_min']==1.)
        result['validation'] = gates
        np.savez(args.output/'arrays.npz', paired_null_kernel=full, inward_amplification=amps)
        plot(args.output, full, amps)
        if not all(gates.values()):
            raise AssertionError(f'Failed validation gates: {gates}')
    except Exception:
        result['failure'] = traceback.format_exc()
        (args.output/'failure.txt').write_text(result['failure'])
        # Preserve partial raw values even if strict JSON rejects nonfinites.
        (args.output/'partial_result.txt').write_text(repr(result)+'\n')
        raise
    finally:
        result['elapsed_seconds'] = time.perf_counter()-start
        (args.output/'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(args.output), validation=gates,
                         elapsed_seconds=result['elapsed_seconds']), indent=2))


if __name__ == '__main__':
    main()
