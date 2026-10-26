"""HB-001: direct checks of original document sections 8--11, no fits."""
import math
import os
from pathlib import Path
import resource
import subprocess
from time import perf_counter

import numpy as np
from scipy.fft import fftn, ifftn, next_fast_len
from scipy.signal import fftconvolve

from bem_inverse import a1_geometry as g, a2_muller as a
from bem_inverse.io import read, write, curve_from, digest
from experiments.benchmark.campaign import problem

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'results/validation/cleaned_interfaces/HB-001-kernels'
SOURCE = ROOT/'results/validation/cleaned_interfaces/PS-003/H3/runs/hook__c13.3/accepted.json'


def primitives(z):
    k = (len(z)-1)//2
    difference = np.zeros((2*k+1,)*2, dtype=z.dtype)
    difference[:, k] += z
    difference[k, :] -= z
    w = np.zeros_like(difference)
    for j in range(1, k+1):
        r = np.arange(j)
        w[k+j-1-r, k+r] += z[k+j]
        w[k-1-r, k-j+r] -= z[k-j]
    return difference, w, g.real_product(difference, difference, 2), g.real_product(w, w, 2)


def psi(j, n):
    """Low modes by recurrence; high modes by cancellation-free closed form."""
    n = np.asarray(n)
    if j == 0:
        return np.where(n == 0, 0., -1/np.maximum(np.abs(n), 1))
    out = 2*psi(j-1, n)-psi(j-1, n-1)-psi(j-1, n+1)
    high = np.abs(n) > j
    nh = np.abs(n[high]).astype(float)
    den = nh.copy()
    for ell in range(1, j+1):
        den *= nh*nh-ell*ell
    out[high] = (-1)**(j+1)*math.factorial(2*j)/den
    return out


def weighted_matrix(qpower, j, cutoff):
    b = g.half(qpower)
    modes = np.arange(-cutoff, cutoff+1)
    m, n = np.meshgrid(modes, modes, indexing='ij')
    out = np.zeros(m.shape, complex)
    for s in range(-b, b+1):
        r = m-n-s
        out += np.where(abs(r) <= b, qpower[np.clip(r+b, 0, 2*b), s+b], 0)*psi(j, n+s)
    return 2*np.pi*out


def ranks(matrix, reference_norm):
    s = np.linalg.svd(matrix, compute_uv=False)
    return {str(t): int(np.count_nonzero(s > t*reference_norm)) for t in (1e-3, 1e-6)}


def singular_case(name, curve, observations):
    cutoff = 64
    geom = g.ModalGeometry(curve, cutoff+64)
    _, _, radius, q = primitives(curve.coefficients)
    rp, qp = radius, q
    blocks, rows = [], []
    modes = np.arange(-cutoff, cutoff+1)
    for j in (1, 2):
        if j == 2:
            rp = fftconvolve(radius, radius)
            qp = fftconvolve(q, q)
        started = perf_counter()
        block = weighted_matrix(qp, j, cutoff)
        seconds = perf_counter()-started
        window = max(g.half(rp), cutoff)
        reference = a.kernel_matrix(g.crop(rp, window, 2), np.zeros((2*window+1,)*2, complex), cutoff)
        mask = abs(modes[:, None]-modes[None, :]) > 2*j*curve.band
        rows.append(dict(state=name, K=curve.band, N=cutoff, j=j,
            relative_equivalence=float(np.linalg.norm(block-reference)/np.linalg.norm(reference)),
            off_band_relative=float(np.linalg.norm(block[mask])/np.linalg.norm(block)),
            structural_occupancy=float(np.mean(~mask)), prototype_seconds=seconds))
        blocks.append(block)
    remainder_rows = []
    for label, obs in observations.items():
        ko, ki = obs.wavenumber, obs.wavenumber*np.sqrt(13.3)
        matrix, _ = a.muller_matrix(geom, ko, ki, cutoff)
        size = 2*cutoff+1
        v = matrix[:size, size:]
        norm = float(np.linalg.norm(v, 2))
        extracted = np.zeros_like(v)
        for j, block in enumerate(blocks, 1):
            coefficient = -((-1)**j*(ko**(2*j)-ki**(2*j))/(4**j*math.factorial(j)**2))/(4*np.pi)
            extracted += coefficient*block
            remainder = v-extracted
            remainder_rows.append(dict(state=name, frequency=label, Ps=j,
                extraction_norm_over_V=float(np.linalg.norm(extracted, 2)/norm),
                remainder_norm_over_V=float(np.linalg.norm(remainder, 2)/norm),
                remainder_absolute_threshold_ranks=ranks(remainder, norm),
                original_absolute_threshold_ranks=ranks(v, norm), size=size))
    return rows, remainder_rows


def direct(mapped, band, coefficients):
    basis = g.ChebyshevArrays(mapped, band)
    return basis.combine(coefficients)


def incremental(mapped, dx, band, coefficients, anchors):
    multiply = g.RealMultiplier(mapped+dx, band)
    delta_multiply = g.RealMultiplier(dx, band)
    previous = np.zeros((2*band+1,)*2, complex)
    current = delta_multiply(g.delta(band, 2))
    out = coefficients[:, 1, None, None]*current
    for j in range(1, coefficients.shape[1]-1):
        previous, current = current, 2*multiply(current)+2*delta_multiply(anchors[j])-previous
        out += coefficients[:, j+1, None, None]*current
    return out


def extended_difference(mapped, dx, band, coefficients):
    """Independent complex256 FFT, both complete recurrences then subtraction."""
    poly0 = g.crop(mapped.astype(np.clongdouble), min(g.half(mapped), 2*band), 2)
    polyd = g.crop(dx.astype(np.clongdouble), min(g.half(dx), 2*band), 2)
    shape = (next_fast_len(2*band+poly0.shape[-1]),)*2
    transforms = np.stack([fftn(poly0, shape), fftn(poly0+polyd, shape)])
    offset = g.half(poly0)
    previous = np.zeros((2, 2*band+1, 2*band+1), np.clongdouble)
    previous[:, band, band] = 1
    def multiply(x):
        full = ifftn(fftn(x, shape, axes=(-2, -1))*transforms, axes=(-2, -1))
        return full[:, offset:offset+2*band+1, offset:offset+2*band+1]
    current = multiply(previous)
    out = coefficients[:, 0, None, None, None]*previous + coefficients[:, 1, None, None, None]*current
    for j in range(1, coefficients.shape[1]-1):
        previous, current = current, 2*multiply(current)-previous
        out += coefficients[:, j+1, None, None, None]*current
    return out[:, 1]-out[:, 0]


def increment_case(z0, z1, observations):
    band = 128
    dz = z1-z0
    zbase, wbase, r0, q0 = primitives(z0)
    zd, wd, _, _ = primitives(dz)
    _, _, r1, q1 = primitives(z1)
    dr = 2*g.real_product(zbase, zd, 2)+g.real_product(zd, zd, 2)
    dq = 2*g.real_product(wbase, wd, 2)+g.real_product(wd, wd, 2)
    upper = 1.1*max(np.sum(abs(r0)), np.sum(abs(r1)))
    mapped = 2*r0/upper
    mapped[g.half(mapped), g.half(mapped)] -= 1
    receipt = dict(radial_upper=float(upper),
        endpoint_R_l1=[float(np.sum(abs(r0))), float(np.sum(abs(r1)))],
        delta_R_relative=float(np.linalg.norm(dr-(r1-r0))/np.linalg.norm(dr)),
        delta_q_relative=float(np.linalg.norm(dq-(q1-q0))/np.linalg.norm(dq)),
        frozen_interval_scope='R only, exact-arithmetic coefficient l1 sufficient bound; no full geometry certificate',
        longdouble_mantissa=int(np.finfo(np.longdouble).nmant), cases=[])
    for label, obs in observations.items():
        coeff, info = a.radial_coefficients(obs.wavenumber, obs.wavenumber*np.sqrt(13.3), upper)
        started = perf_counter()
        basis = g.ChebyshevArrays(mapped, band)
        anchors = basis.ensure(coeff.shape[1]-1)
        base = basis.combine(coeff)
        anchor_seconds = perf_counter()-started
        for scale in (0., 1e-8, 1.):
            dR = scale*2*g.real_product(zbase, zd, 2)+scale*scale*g.real_product(zd, zd, 2)
            dx = 2*dR/upper
            direct_times, increment_times = [], []
            for repeat in range(3):
                started = perf_counter(); target = direct(mapped+dx, band, coeff); direct_times.append(perf_counter()-started)
                started = perf_counter(); change = incremental(mapped, dx, band, coeff, anchors); increment_times.append(perf_counter()-started)
            difference = target-base
            row = dict(frequency=label, scale=scale, degree=coeff.shape[1]-1,
                anchor_seconds=anchor_seconds, anchor_bytes=anchors.nbytes,
                direct_seconds=direct_times, increment_seconds=increment_times,
                increment_over_direct=float(np.median(increment_times)/np.median(direct_times)),
                relative_target_agreement=float(np.linalg.norm(base+change-target)/np.linalg.norm(target)),
                absolute_delta_agreement=float(np.linalg.norm(change-difference)),
                delta_norm=float(np.linalg.norm(change)), zero_exact=bool(np.all(change==0)) if scale==0 else None,
                candidate_R_l1_upper=float(np.sum(abs(r0+dR))), interval_contains=bool(np.sum(abs(r0+dR)) <= upper))
            if scale == 1e-8:
                started = perf_counter(); reference = extended_difference(mapped, dx, band, coeff)
                row.update(reference_seconds=perf_counter()-started,
                    delta_increment_relative_error=float(np.linalg.norm(change-reference)/np.linalg.norm(reference)),
                    delta_subtraction_relative_error=float(np.linalg.norm(difference-reference)/np.linalg.norm(reference)))
            receipt['cases'].append(row)
            write(OUT/'incremental.json', receipt)
            print('increment', label, scale, row['increment_over_direct'], flush=True)
    return receipt


def main():
    if (OUT/'manifest.json').exists():
        raise FileExistsError('Preserve previous run')
    states = read(SOURCE)['states']
    release = [s for s in states if s['stage']=='release_M11']
    p = problem('hook__c13.3')
    observations = dict(low_real=p.real[0], high_real=p.real[-1], low_damped=p.damped[0], high_damped=p.damped[-1])
    manifest = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=digest(SOURCE),
        code_sha256=digest(Path(__file__)), revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        affinity=sorted(os.sched_getaffinity(0)), load=os.getloadavg(),
        memory=Path('/proc/meminfo').read_text(),
        blas={k:os.getenv(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        original_sections=[8,9,10,11], item_numbers=[2,4])
    write(OUT/'manifest.json', manifest)
    rows, remainders = [], []
    for name, state in [('early_K4', states[0]), ('release_K24', release[-1])]:
        rs, rem = singular_case(name, curve_from(state['curve']), observations)
        rows.extend(rs); remainders.extend(rem)
        write(OUT/'singular.json',dict(primitives=rows, remainders=remainders))
        print('singular', name, flush=True)
    increment_case(curve_from(release[0]['curve']).coefficients,
                   curve_from(release[1]['curve']).coefficients,
                   {k:v for k,v in observations.items() if k.startswith('high')})
    write(OUT/'completion.json',dict(load=os.getloadavg(),peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))


if __name__ == '__main__':
    main()
