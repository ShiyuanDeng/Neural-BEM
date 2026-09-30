"""Independent FFT-array implementation and SC field/Jacobian checks.

No optimizer or production backend is modified. The log lower endpoint .05
is an experimental assumption on these known valid fixtures, not a certificate.
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.fft import dct, fft2, ifft2, next_fast_len
from scipy.linalg import lu_factor, lu_solve
from scipy.signal import fftconvolve

from verify import OUTPUT, scalar_radials, relative, oracle, matrix_errors
from experiments.modal_muller_research.coefficient_operator import LaurentGeometry, kernel_matrix
from experiments.modal_muller_research.coefficient_fields import RegularWaves
from experiments.cleaned_interface.geometry import ProjectedUpdate, resize
from experiments.cleaned_interface.io import curve_from
from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas_cases import observations, c_shape_curve
from gpr_bem_kress.execution import execution


def crop(array, band):
    old = (len(array)-1)//2
    if old >= band:
        return array[old-band:old+band+1, old-band:old+band+1].copy()
    return np.pad(array, ((band-old, band-old),)*2)


class Multiplier:
    def __init__(self, poly, band):
        poly = crop(poly, min((len(poly)-1)//2, 2*band))
        self.offset = (len(poly)-1)//2
        self.size = 2*band+1
        side = next_fast_len(self.size+len(poly)-1)
        self.shape = (side, side)
        self.transform = fft2(poly, self.shape)

    def __call__(self, array):
        result = ifft2(fft2(array, self.shape)*self.transform)
        j, n = self.offset, self.size
        return result[j:j+n, j:j+n]


class ArrayGeometry:
    def __init__(self, curve, band, log_degree=260, radial_degree=100):
        started = perf_counter()
        self.curve, self.band = curve, band
        self.geometry = LaurentGeometry.from_coefficients(dict(zip(curve.modes, curve.coefficients)))
        k = curve.band
        z = np.array([self.geometry.coefficients.get(j, 0) for j in curve.modes])
        target = np.zeros((2*k+1, 2*k+1), complex)
        target[:, k] = z
        delta = target-target.T
        nt = np.zeros_like(target)
        nt[:, k] = curve.modes*z
        ns = nt.T
        def dot(a, b):
            prod = fftconvolve(a, b[::-1, ::-1].conj())
            return (prod+prod[::-1, ::-1].conj())/2
        radius = dot(delta, delta)
        self.source = Multiplier(dot(delta, ns), band)
        self.target = Multiplier(dot(delta, nt), band)
        self.normal = Multiplier(dot(nt, ns), band)
        quotient = np.zeros_like(target)
        for j, value in self.geometry.coefficients.items():
            if j > 0:
                for r in range(j):
                    quotient[j-1-r+k, r+k] += value
            elif j < 0:
                for r in range(-j):
                    quotient[-1-r+k, j+r+k] -= value
        ww = dot(quotient, quotient)
        upper, beta = float(np.sum(abs(ww))), .05
        ratio = (np.sqrt(upper)-np.sqrt(beta))/(np.sqrt(upper)+np.sqrt(beta))
        mapped = 2*ww/(upper-beta)
        mapped[2*k, 2*k] -= (upper+beta)/(upper-beta)
        one = np.zeros((2*band+1, 2*band+1), complex)
        one[band, band] = 1
        previous = one
        multiplier = Multiplier(mapped, band)
        current = multiplier(one)
        log = 2*np.log((np.sqrt(upper)+np.sqrt(beta))/2)*one
        for n in range(1, log_degree+1):
            log += (2*(-1.)**(n+1)*ratio**n/n)*current
            if n < log_degree:
                previous, current = current, 2*multiplier(current)-previous
        self.log = Multiplier(log, band)
        self.rmax = min((2*np.sum(abs(z)))**2, np.sum(abs(radius)))
        mapped = 2*radius/self.rmax
        mapped[2*k, 2*k] -= 1
        multiplier = Multiplier(mapped, band)
        # Frequency independent arrays: exact linear convolution, projected after each step.
        terms = [one, multiplier(one)]
        for n in range(2, radial_degree+1):
            terms.append(2*multiplier(terms[-1])-terms[-2])
        self.terms = np.stack(terms)
        self.seconds = perf_counter()-started

    def assemble(self, ko, ki, cutoff):
        count = 256
        x = np.cos(np.pi*(np.arange(count)+.5)/count)
        c = dct(scalar_radials(self.rmax*(x+1)/2, ko*self.geometry.scale,
                              ki*self.geometry.scale), type=2, axis=1)/count
        c[:, 0] *= .5
        p, q, dp, dq, hp, hq = np.einsum('ap,pij->aij', c[:, :len(self.terms)], self.terms)
        q += self.log(p)
        dq += self.log(dp)
        hq += self.log(hp)
        v = kernel_matrix(p, q, cutoff)
        k = kernel_matrix(-2*self.source(dp), -2*self.source(dq), cutoff)
        kp = kernel_matrix(2*self.target(dp), 2*self.target(dq), cutoff)
        modes = np.arange(-cutoff, cutoff+1)
        t = -modes[:, None]*modes[None, :]*v+kernel_matrix(self.normal(hp), self.normal(hq), cutoff)
        eye = np.eye(len(modes))
        return np.block([[eye-k, v], [-t, eye+kp]])


def native(prepared, ko, contrast, acq, cutoff, space=None):
    tick = perf_counter()
    ki = ko*np.sqrt(contrast)
    a = prepared.assemble(ko, ki, cutoff)
    factors = lu_factor(a)
    waves = RegularWaves(prepared.geometry, ko, prepared.band, 64, 48)
    rhs = waves.rhs(acq.sources, acq.strength, cutoff)
    state = lu_solve(factors, rhs)
    prediction = np.diag(waves.receiver(acq.receivers, cutoff)@state)
    jac = None
    if space is not None:
        count = 2*cutoff+1
        reciprocal = lu_solve(factors, waves.rhs(acq.receivers, 1., cutoff))[:count]
        moments = fftconvolve(state[:count], reciprocal, axes=0)
        curve = prepared.curve
        normal = curve.modes*curve.coefficients
        # Complex coefficients of Re(V*conj(N)); no conjugation of the traces.
        weight = fftconvolve(space.derivatives, normal[::-1, None].conj(), axes=0)
        weight = (weight+weight[::-1].conj())/2
        n = min(2*curve.band, 2*cutoff)
        weight = weight[2*curve.band-n:2*curve.band+n+1]
        prod = moments[2*cutoff-n:2*cutoff+n+1]
        jac = 2*np.pi*(ki*ki-ko*ko)*prod[::-1].T@weight
    return prediction, jac, dict(seconds=perf_counter()-tick,
                                 discrete_residual=relative(a@state, rhs))


def load_curve(path):
    record = json.loads(Path(path).read_text())
    return curve_from(record.get('curve', record))


def nodal_state(curve, ko, contrast, acq, count):
    if np.imag(ko) == 0:
        return F.solve(curve, float(np.real(ko)), contrast, acq, count, execution_backend='cpu')
    # F.solve's public real-frequency guard does not accept Python complex k.
    nodes = curve.nodes(count)
    ki = ko*np.sqrt(contrast)
    with execution(kernels='reference'):
        a = F.build_muller_system(nodes, ko, ki).system_matrix
        values, flux = F.kress_incident_trace_on_boundary(nodes, acq.sources, ko, acq.strength)
        rhs = np.vstack((values.T, flux.T))
        factors = lu_factor(a)
        traces = lu_solve(factors, rhs)
        receiver = F.build_exterior_receiver_operator(nodes, acq.receivers, ko)
        prediction = np.diag(receiver.apply_state(traces))
    return F.ForwardState(nodes, ko, ki, acq, a, factors, traces, prediction, relative(a@traces, rhs))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['c', 'endpoint', 'damped', 'scalar'])
    args = parser.parse_args()
    if args.part == 'scalar':
        import mpmath as mp
        mp.mp.dps = 60
        r2 = np.r_[1e-12, 1e-8, np.geomspace(.001, 16, 20)]
        rows = []
        for damping in [0., .25]:
            ko = 6.417188604442469*(1+1j*damping)
            ki = ko*np.sqrt(13.3)
            values = scalar_radials(r2, ko, ki)
            exact = []
            for r in r2:
                rr = mp.mpf(float(r))
                def split(k):
                    k = mp.mpc(k)
                    P = -mp.besselj(0, k*mp.sqrt(rr))/(4*mp.pi)
                    Q = .25j*mp.hankel1(0, k*mp.sqrt(rr))-P*mp.log(rr)
                    DP = k*mp.besselj(1, k*mp.sqrt(rr))/(8*mp.pi*mp.sqrt(rr))
                    DQ = -1j*k*mp.hankel1(1, k*mp.sqrt(rr))/(8*mp.sqrt(rr))-DP*mp.log(rr)-P/rr
                    return P, Q, DP, DQ
                po, qo, dp, dq = split(ko)
                pi, qi, dpi, dqi = split(ki)
                exact.append([complex(v) for v in [po-pi, qo-qi, dp-dpi, dq-dqi+(po-pi)/rr,
                                                   mp.mpc(ko)**2*po-mp.mpc(ki)**2*pi,
                                                   mp.mpc(ko)**2*qo-mp.mpc(ki)**2*qi]])
            exact = np.array(exact).T
            rows.append(dict(damping=damping, all_relative=relative(values, exact),
                             each_function_relative=[relative(v, e) for v, e in zip(values, exact)]))
    else:
        if args.part == 'endpoint':
            path = 'results/validation/modal_atlas/MA-005/runs/DF/c13.3/shifted_rotated_c/fixed_M67.json'
            curve = load_curve(path)
            frequencies, cutoffs, bands, update_band = [1.25e9, 2.5e9], [64,96,128], [160], 67
        else:
            path = 'results/validation/shape_continuation/SC-050-localization-robustness/inputs/development_c/truth.json'
            curve = load_curve(path)
            if args.part == 'c':
                curve = resize(curve, 24)
                frequencies, cutoffs, bands, update_band = [1e9, 2.5e9], [32,48,64,96], [128], 24
            else:
                frequencies, cutoffs, bands, update_band = [.5e9,1e9,2.5e9], [64,96], [128], 12
        acq = observations(np.zeros((24, 1)), [1e9])[0].acquisition
        update = ProjectedUpdate(.05)
        space = update.prepare(curve, update_band, curve.band) if args.part != 'damped' else None
        rows = []
        for band in bands:
            prepared = ArrayGeometry(curve, band)
            print(json.dumps(dict(part=args.part, setup_seconds=prepared.seconds, band=band,
                                  rmax=float(prepared.rmax))), flush=True)
            for frequency in frequencies:
                ko = 6.417188604442469*frequency/2.5e9
                if args.part == 'damped':
                    ko *= 1+.25j
                ref = nodal_state(curve, ko, 13.3, acq, 2048)
                check = nodal_state(curve, ko, 13.3, acq, 1024)
                jref = F.shape_jacobian(ref, update.velocities(space, ref.curve)) if space is not None else None
                for cutoff in cutoffs:
                    prediction, jac, diag = native(prepared, ko, 13.3, acq, cutoff, space)
                    row = dict(part=args.part, frequency_hz=frequency, bandwidth=band, cutoff=cutoff,
                               data_error=relative(prediction, ref.prediction),
                               oracle_1024_2048=relative(check.prediction, ref.prediction), **diag)
                    if jac is not None:
                        row.update(jacobian_error=relative(jac, jref), worst_column=float(np.max(
                            np.linalg.norm(jac-jref, axis=0)/np.linalg.norm(jref, axis=0))))
                    rows.append(row)
                    print(json.dumps(row), flush=True)
    result = dict(part=args.part, source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [Path(__file__), OUTPUT/'verify.py']}, rows=rows)
    (OUTPUT/('integration_'+args.part+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    if args.part == 'scalar':
        print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
