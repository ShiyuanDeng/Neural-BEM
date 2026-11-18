"""Standalone A3 feasibility probe, not a solver implementation or a fit."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import threading
import time
import traceback

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import numpy as np
import psutil
from scipy.special import gammaln, i0e, jv
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'solvers'), str(ROOT)]
from bem_inverse.a3_waves import graf_order, plane_wave_order
from bem_inverse.a2_muller import radial_coefficients
from experiments.baselines.brg.brg_data import true_curve, observation

OUT = ROOT/'results/bem/baseline_data/series_limit_proposal/2026-11-18'


def provenance():
    return dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                solver_dirty=subprocess.check_output(['git', 'status', '--porcelain', '--',
                    'solvers/bem_inverse'], text=True),
                source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted((ROOT/'solvers/bem_inverse').rglob('*.py'))})


def waves(curve, k, order, count, band):
    center = curve.coefficients[curve.band]
    z = curve.values(count)-center
    normal = -1j*curve.values(count, derivative=1)
    rho = np.sum(np.abs(np.delete(curve.coefficients, curve.band)))
    orders = np.arange(-order-1, order+2)
    # Integer parity avoids the second-kind term in negative-order identities.
    values = jv(abs(orders)[:, None], k*abs(z)[None, :])
    values *= np.where(orders < 0, (-1.)**abs(orders), 1.)[:, None]
    values = values*np.exp(1j*orders[:, None]*np.angle(z)[None, :])
    flux = k/2*(normal*values[:-2]-normal.conj()*values[2:])
    modes = np.arange(-band, band+1)
    scale = np.exp(abs(orders[1:-1])*np.log(k*rho/2)-gammaln(abs(orders[1:-1])+1))
    value_coeff = (np.fft.fft(values[1:-1], axis=-1)/count)[:, modes % count]/scale[:, None]
    flux_coeff = (np.fft.fft(flux, axis=-1)/count)[:, modes % count]/scale[:, None]
    theta = np.array([.2, 1.3, 2.7])
    angles = orders[1:-1]
    phase = np.exp(1j*k*(np.cos(theta)*center.real+np.sin(theta)*center.imag))
    weights = (scale*(1j)**angles)[:, None]*np.exp(-1j*angles[:, None]*theta)*phase
    reconstructed = value_coeff.T@weights
    reconstructed_flux = flux_coeff.T@weights
    full_z = z+center
    plane = np.exp(1j*k*(np.cos(theta)[:, None]*full_z.real+np.sin(theta)[:, None]*full_z.imag))
    plane_flux = 1j*k*(np.cos(theta)[:, None]*normal.real+np.sin(theta)[:, None]*normal.imag)*plane
    direct = (np.fft.fft(plane, axis=-1)/count)[:, modes % count].T
    direct_flux = (np.fft.fft(plane_flux, axis=-1)/count)[:, modes % count].T
    error = lambda a, b: float(np.linalg.norm(a-b)/np.linalg.norm(b))
    tail = {str(cutoff): float(np.linalg.norm(direct[abs(modes)>cutoff])/np.linalg.norm(direct))
            for cutoff in (64, 96, 128, 192)}
    return value_coeff, flux_coeff, dict(samples=count, plane_value_error=error(reconstructed, direct),
        plane_flux_error=error(reconstructed_flux, direct_flux), incident_tail_relative_l2=tail)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT/'probe.json'
    assert not target.exists(), 'Keep every run; no overwrite.'
    assert psutil.virtual_memory().available >= 18*1024**3, 'Reserve 16 GiB plus 2 GiB estimate.'
    record = dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  command=[sys.executable, *sys.argv], start=provenance(), cases=[],
                  minimum_available_bytes=psutil.virtual_memory().available)
    target.write_text(json.dumps(record, indent=2)+'\n')
    def stop(signum, frame):
        raise RuntimeError('900 s probe limit or 14 GiB memory reserve reached')
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGUSR1, stop)
    signal.alarm(900)
    finished = threading.Event()
    def guard():
        while not finished.wait(.5):
            available = psutil.virtual_memory().available
            record['minimum_available_bytes'] = min(record['minimum_available_bytes'], available)
            if available < 14*1024**3:
                os.kill(os.getpid(), signal.SIGUSR1)
                return
    threading.Thread(target=guard, daemon=True).start()
    started = time.monotonic()
    try:
        loss = lambda x: float(np.finfo(float).eps*i0e(x)*np.exp(x))
        record['legacy_limits'] = {str(tol): brentq(lambda x: loss(x)-tol, 1., 60.) for tol in [1e-9, 1e-6]}
        for shape, argument in [('star', None), ('cavity', None), ('cavity', 45.), ('cavity', 65.)]:
            curve = true_curve(shape)
            rho = float(np.sum(abs(np.delete(curve.coefficients, curve.band))))
            k = 15. if argument is None else argument/rho
            speed_bound = float(np.sum(abs(curve.modes*curve.coefficients)))
            order, tail = plane_wave_order(k, rho, speed_bound, 1e-16)
            obs, _, _ = observation('star_full' if shape == 'star' else 'cavity_2', 15.)
            center = curve.coefficients[curve.band]
            distance = abs(obs.acquisition.receivers[:, 0]+1j*obs.acquisition.receivers[:, 1]-center)
            graf, ratio = graf_order(k, rho, distance, 1e-16)
            row = dict(shape=shape, geometry_band=curve.band, k=k, rho=rho, argument=k*rho,
                       legacy_loss=loss(k*rho), plane_order=order, plane_tail_bound=tail,
                       graf_order=graf, graf_ratio=ratio, receiver_min_distance=float(min(distance)), grids=[])
            previous = None
            for count in (1024, 2048, 4096):
                tick = time.monotonic()
                a, b, info = waves(curve, k, max(order, graf), count, 256)
                info['seconds'] = time.monotonic()-tick
                if previous is not None:
                    info['value_grid_relative_l2'] = float(np.linalg.norm(a-previous[0])/np.linalg.norm(a))
                    info['flux_grid_relative_l2'] = float(np.linalg.norm(b-previous[1])/np.linalg.norm(b))
                previous = a, b
                row['grids'].append(info)
            record['cases'].append(row)
        # Conservative diameter bound: alpha <= k_i*rho; scalar A2 only.
        curve = true_curve('cavity')
        rho = float(np.sum(abs(np.delete(curve.coefficients, curve.band))))
        _, radial = radial_coefficients(45/rho, 65/rho, 4*rho*rho)
        record['radial_conservative_45_65'] = radial
        record['status'] = 'completed; feasibility only, no forward or inverse solve'
    except BaseException:
        record['failure'] = traceback.format_exc()
        raise
    finally:
        finished.set()
        signal.alarm(0)
        record.update(wall_seconds=time.monotonic()-started, end=provenance(),
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        target.write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
