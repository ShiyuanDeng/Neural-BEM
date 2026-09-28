"""MA-001 part A driver: frontier, resonance and linearization horizon on the exact circle.

PYTHONPATH=. python -m experiments.modal_atlas.circle_study --output <file.json>
"""
import argparse
import json
import warnings

import numpy as np
from scipy.special import h1vp, hankel1, jv, jvp

from . import circle as c

RHO = 10.0                                   # iteration 04's receiver radius, unit circle
PHI = np.linspace(0, 2 * np.pi, 12, endpoint=False)


def frontier(k, contrast, tau, amplitude=0.01 * np.sqrt(2)):
    """Highest p whose RMS-0.01 cosine perturbation moves the monostatic datum by tau |d|."""
    ki = k * np.sqrt(contrast)
    cutoff = int(1.5 * ki + 2 * k) + 80
    U = c.trace_coefficients(k, contrast, RHO, [0.0], cutoff)
    d = abs(c.scattered(k, contrast, RHO, [0.0], RHO, [0.0], int(1.3 * max(k, ki)) + 40)[0])
    P = np.arange(0, 2 * cutoff)
    J = np.array([abs(c.sensitivity(U, U, p, k, contrast)[0]) for p in P])
    profile = np.abs(U[0])
    n = c.orders(cutoff)
    return dict(k=k, contrast=contrast, tau=tau, frontier=int(P[amplitude * J >= tau * d].max()),
                twice_trace_support={f'{e:g}': int(2 * np.abs(n[profile >= e * profile.max()]).max())
                                     for e in (1e-1, 1e-2)})


def horizon(k, contrast, target=0.1):
    """Largest dilation eps at which the linear prediction errs by < target (relative)."""
    cutoff = int(1.5 * k * np.sqrt(contrast)) + 30
    U = c.trace_coefficients(k, contrast, RHO, PHI, cutoff + 40)
    J = c.sensitivity(U, U, 0, k, contrast)
    d0 = c.scattered(k, contrast, RHO, PHI, RHO, PHI, cutoff)
    for eps in np.logspace(-8, -0.3, 160):
        change = c.scattered(k, contrast, RHO, PHI, RHO, PHI, cutoff, 1 + eps) - d0
        if np.linalg.norm(change - eps * J) > target * np.linalg.norm(change):
            return float(eps), float(np.linalg.norm(J) / np.linalg.norm(d0))
    return float('nan'), float(np.linalg.norm(J) / np.linalg.norm(d0))


def pole(n, k0, contrast):
    """Newton on the order-n Mie denominator from a real start near a trapped resonance."""
    def D(k):
        ki = k * np.sqrt(contrast)
        return k * jv(n, ki) * h1vp(n, k) - ki * jvp(n, ki) * hankel1(n, k)
    k = complex(k0, -1e-4)
    for _ in range(100):
        step = D(k) / ((D(k + 1e-7) - D(k - 1e-7)) / 2e-7)
        k -= step
        if abs(step) < 1e-14:
            break
    return k


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    warnings.simplefilter('ignore', RuntimeWarning)
    result = dict(frontier=[], poles=[], horizon_distribution={})
    for contrast in (0.33, 0.5, 10.0):
        for k in (1, 2, 4, 8, 12, 16, 20, 32, 48, 64):
            if contrast == 10.0 and k > 20:
                continue
            for tau in (1e-2, 1e-3):
                result['frontier'].append(frontier(k, contrast, tau))
    # Trapped (whispering-gallery) poles at contrast 10 located from the real-axis sweep.
    for n, k0 in ((5, 2.362), (6, 2.740), (4, 3.016), (8, 3.478), (10, 5.416)):
        ks = pole(n, k0, 10.0)
        rows = []
        for detune in (0.0, 0.3, 1.0, 3.0, 10.0, 30.0):
            k = ks.real + detune * abs(ks.imag)
            eps, gain = horizon(k, 10.0)
            rows.append(dict(detuning_linewidths=detune, k=k, horizon=eps, relative_sensitivity=gain,
                             horizon_times_abs_pole_over_distance=eps * abs(ks) / abs(k - ks)))
        result['poles'].append(dict(order=n, pole_real=ks.real, pole_imag=ks.imag,
                                    quality=ks.real / (-2 * ks.imag), rows=rows))
    ks = np.sort(np.random.default_rng(0).uniform(1, 8, 200))
    for contrast in (0.33, 0.5, 3.0, 10.0):
        hk = np.array([horizon(k, contrast)[0] * k for k in ks])
        result['horizon_distribution'][f'{contrast:g}'] = dict(
            percentiles_10_50_90=[float(x) for x in np.nanpercentile(hk, [10, 50, 90])],
            fraction_below_0_01=float(np.mean(hk < 0.01)), samples=len(ks), k_range=[1, 8])
    with open(args.output, 'w') as handle:
        json.dump(result, handle, indent=1)


if __name__ == '__main__':
    main()
