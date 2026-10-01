"""Diagnose the two modal-only failure classes in CI-001-modal.

1. ``graf``: the seven original-start refusals. Record the Graf ratio, the
   order the service's own bound requires (evaluated in log space), and the order
   at which the unscaled H_l(k d) factor overflows float64.
2. ``resolution``: the two NUMERICAL_FAILURE stages. At the archived stage-start
   curve, compare modal K_trace 96/128/160/192 and nodal 512 with 1024-node CPU
   Kress at the four highest frequencies.

Usage: python diagnose.py graf|resolution  (writes diagnostics_<mode>.json)
"""
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import numpy as np
from scipy.special import gammaln, hankel1

from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.io import curve_from
from experiments.cleaned_interface.modal_muller import ModalMuller, token
from experiments.cleaned_interface.physics import Execution, NodalKress

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent/'CI-001-modal'/'runs'
REFUSED = ('far__development_c', 'far__opposite_c', 'modal__c2__development_c', 'modal__c4__development_c',
           'modal__c13.3__development_c', 'modal__c4__opposite_c', 'modal__c13.3__opposite_c')
STOPPED = (('modal__c13.3__shifted_star', 'fixed_M49'), ('modal__c13.3__new_asymmetric', 'fixed_M61'))


def problem(case):
    return b.fitting_problem(next(r for r in b.descriptors() if r['id'] == case), b.DEFAULT_OUTPUT)


def relative(a, reference):
    return np.linalg.norm(a-reference, axis=0)/np.linalg.norm(reference, axis=0)


def log_hankel(order, x):
    """log|H_l(x)| for l=0..order by the forward ratio recurrence (stable for growing H_l)."""
    h0, h1 = hankel1(0, x), hankel1(1, x)
    q = np.empty(order, complex)
    q[0] = h1/h0
    for l in range(1, order):
        q[l] = 2*l/x-1/q[l-1]
    return np.log(abs(h0))+np.r_[0, np.cumsum(np.log(np.abs(q)))]


def required_order(k, radius, distance, tolerance=1e-16, maximum=4000):
    """The service's Graf bound evaluated in log space (no overflow): last kept order L."""
    orders = np.arange(maximum+1)
    logs = log_hankel(maximum, k*distance)
    terms = np.log(2)+logs-logs[0]+orders*np.log(abs(k)*radius/2)+abs(np.imag(k))*radius-gammaln(orders+1)
    tail = np.logaddexp.accumulate(terms[::-1])[::-1]
    return int(np.flatnonzero(tail <= np.log(tolerance))[0])-1, logs


def graf():
    """Required Graf order vs the order at which H_l(k d) overflows float64."""
    nodal = NodalKress(Execution(device='cpu', frequency_threads=4))
    rows = []
    for case in REFUSED:
        p = problem(case)
        curve = p.initial
        service = ModalMuller(Execution(device='cpu', frequency_threads=4))
        try:
            service.evaluate(curve, p.real[-1], p.contrast, token(64))
            refusal = None
        except ValueError as exc:
            refusal = str(exc)
        z = curve.coefficients
        center, radius = complex(z[len(z)//2]), float(np.abs(z).sum()-abs(z[len(z)//2]))
        acquisition = p.real[0].acquisition
        points = np.concatenate((acquisition.sources, acquisition.receivers))
        points = points[:, 0]+1j*points[:, 1]
        t = 2*np.pi*np.arange(4096)/4096
        boundary = np.exp(1j*np.outer(t, np.arange(-(len(z)//2), len(z)//2+1)))@z
        clearance = float(np.abs(points[None, :]-boundary[:, None]).min())
        distance = np.abs(points-center)
        frequencies = []
        for o in (p.real[0], p.real[-1]):
            k = float(np.real(o.wavenumber))
            order, logs = required_order(k, radius, np.array([distance.min()]).item())
            overflow = int(np.flatnonzero(logs > np.log(np.finfo(float).max))[0])
            frequencies.append(dict(frequency_hz=o.frequency_hz, required_order=order,
                                    hankel_overflow_order=overflow, cap=128))
        reference = nodal.evaluate(curve, p.real[-1], p.contrast, 512).prediction
        fine = nodal.evaluate(curve, p.real[-1], p.contrast, 1024).prediction
        rows.append(dict(case=case, contrast=p.contrast, center=[center.real, center.imag], radius=radius,
                         minimum_point_distance_from_center=float(distance.min()),
                         graf_ratio=radius/float(distance.min()), clearance_from_curve=clearance,
                         refusal=refusal, frequencies=frequencies,
                         kress_512_vs_1024_at_2p5GHz=float(relative(reference, fine).max())))
        print(case, refusal, frequencies, flush=True)
    return dict(rows=rows)


def resolution():
    nodal = NodalKress(Execution(device='cpu', frequency_threads=4))
    rows = []
    for case, stage in STOPPED:
        p = problem(case)
        record = json.loads((RUNS/case/f'{stage}.json').read_text())
        curve = curve_from(record['curve'])
        service = ModalMuller(Execution(device='cpu', frequency_threads=4))
        for o in p.real[-4:]:
            reference = nodal.evaluate(curve, o, p.contrast, 1024).prediction
            row = dict(case=case, stage=stage, frequency_hz=o.frequency_hz, K=curve.band,
                       nodal_512=float(relative(nodal.evaluate(curve, o, p.contrast, 512).prediction,
                                                reference).max()))
            for cutoff in (96, 128, 160, 192):
                started = perf_counter()
                prediction = service.evaluate(curve, o, p.contrast, token(cutoff)).prediction
                row[f'modal_{cutoff}'] = float(relative(prediction, reference).max())
                row[f'modal_{cutoff}_seconds'] = perf_counter()-started
            rows.append(row)
            print({k: (f'{v:.2e}' if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
    return dict(production_refined=dict(K192=[96, 128]), rows=rows)


if __name__ == '__main__':
    mode = sys.argv[1]
    result = dict(graf=graf, resolution=resolution)[mode]()
    result['git_head'] = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    (HERE/f'diagnostics_{mode}.json').write_text(json.dumps(result, indent=1))
