"""Independent, bounded verification of the supplied Chebyshev PDF.

Run from the repo root with PYTHONPATH=solvers:. and one BLAS thread.
This is review code, not a registered backend. Native production files are
imported read-only. Scalar Chebyshev abscissae are not boundary nodes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
from scipy.fft import dct
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh
from scipy.special import hankel1, iv, jv

from experiments.modal_muller_research.coefficient_operator import (
    CoefficientGeometry, LaurentGeometry, add, conjugate, dense_product,
    embed, multiply, sparse_product, times,
)
from experiments.modal_muller_research.modal import ModalSystem
from experiments.shape_continuation.geometry import FourierCurve
from gpr_bem_kress.execution import execution
from gpr_bem_kress.system import build_muller_system

OUTPUT = Path(__file__).resolve().parent


def relative(a, b):
    return float(np.linalg.norm(a-b)/np.linalg.norm(b))


def scalar_radials(r2, ko, ki):
    """PDF equation (10), with a local series only for max(|k|)*r < 2."""
    r2 = np.asarray(r2)
    r = np.sqrt(r2)
    jo, ji = jv(0, ko*r), jv(0, ki*r)
    po, pi = -jo/(4*np.pi), -ji/(4*np.pi)
    qo = .25j*hankel1(0, ko*r)-po*np.log(r2)
    qi = .25j*hankel1(0, ki*r)-pi*np.log(r2)
    dj = ko*jv(1, ko*r)-ki*jv(1, ki*r)
    dh = ko*hankel1(1, ko*r)-ki*hankel1(1, ki*r)
    out = np.array([po-pi, qo-qi, dj/(8*np.pi*r),
                    -1j*dh/(8*r)-np.log(r2)*dj/(8*np.pi*r),
                    ko*ko*po-ki*ki*pi, ko*ko*qo-ki*ki*qi])
    near = max(abs(ko), abs(ki))*r < 2
    rr = r2[near]
    local = np.zeros((6, len(rr)), complex)
    ao = ai = 1.
    harmonic = 0.
    for p in range(24):
        if p:
            ao *= -ko*ko/(4*p*p)
            ai *= -ki*ki/(4*p*p)
            harmonic += 1/p
        pko, pki = -ao/(4*np.pi), -ai/(4*np.pi)
        qko = ao*(.25j+(harmonic-np.euler_gamma-np.log(ko/2))/(2*np.pi))
        qki = ai*(.25j+(harmonic-np.euler_gamma-np.log(ki/2))/(2*np.pi))
        local[0] += (pko-pki)*rr**p
        local[1] += (qko-qki)*rr**p
        local[4] += (ko*ko*pko-ki*ki*pki)*rr**p
        local[5] += (ko*ko*qko-ki*ki*qki)*rr**p
        if p:
            local[2] += p*(pko-pki)*rr**(p-1)
            local[3] += (pko-pki+p*(qko-qki))*rr**(p-1)
    out[:, near] = local
    return out


def compose(poly, coefficients, bandwidth):
    coefficients = np.atleast_2d(coefficients)
    previous = embed({(0, 0): 1}, bandwidth)
    total = coefficients[:, 0, None, None]*previous
    current = sparse_product(previous, poly)
    for n in range(1, coefficients.shape[1]):
        total += coefficients[:, n, None, None]*current
        if n+1 < coefficients.shape[1]:
            previous, current = current, 2*sparse_product(current, poly)-previous
    return total


class ChebyshevGeometry(CoefficientGeometry):
    def radial(self, ko, ki, terms):
        # Both expressions are genuine upper bounds, unlike the RMS heuristic.
        upper = min((2*sum(abs(v) for v in self.geometry.coefficients.values()))**2,
                    sum(abs(v) for v in self.radius_squared.values()))
        count = max(128, 2*(terms+1))
        x = np.cos(np.pi*(np.arange(count)+.5)/count)
        coeff = dct(scalar_radials(upper*(x+1)/2, ko, ki), type=2, axis=1)/count
        coeff[:, 0] *= .5
        ell = add(times(self.radius_squared, 2/upper), {(0, 0): -1})
        return compose(ell, coeff[:, :terms+1], self.bandwidth)


def general_geometry(geometry, bandwidth, beta=.05, degree=260):
    """Independent |W|^2 log implementation; beta is an experimental assumption.

    It is intentionally not called certified. No finite RMS check can prove it.
    """
    tick = perf_counter()
    obj = ChebyshevGeometry.__new__(ChebyshevGeometry)
    obj.geometry, obj.bandwidth = geometry, bandwidth
    z = geometry.coefficients
    delta = add({(j, 0): v for j, v in z.items()}, {(0, j): v for j, v in z.items()}, -1)
    nt, ns = {(j, 0): j*v for j, v in z.items()}, {(0, j): j*v for j, v in z.items()}
    def dot(a, b):
        return times(add(multiply(a, conjugate(b)), multiply(conjugate(a), b)), .5)
    obj.radius_squared = multiply(delta, conjugate(delta))
    obj.source_dot, obj.target_dot, obj.normal_dot = dot(delta, ns), dot(delta, nt), dot(nt, ns)
    quotient = {}
    for j, value in z.items():
        if j > 0:
            for r in range(j):
                quotient[j-1-r, r] = quotient.get((j-1-r, r), 0)+value
        elif j < 0:
            for r in range(-j):
                quotient[-1-r, j+r] = quotient.get((-1-r, j+r), 0)-value
    obj.quotient = quotient
    ww = multiply(quotient, conjugate(quotient))
    upper = sum(abs(v) for v in ww.values())
    ratio = (np.sqrt(upper)-np.sqrt(beta))/(np.sqrt(upper)+np.sqrt(beta))
    n = np.arange(1, degree+1)
    coeff = np.r_[2*np.log((np.sqrt(upper)+np.sqrt(beta))/2), 2*(-1.)**(n+1)*ratio**n/n]
    mapped = add(times(ww, 2/(upper-beta)), {(0, 0): -(upper+beta)/(upper-beta)})
    obj.log_quotient = compose(mapped, coeff, bandwidth)[0]
    obj.log_order, obj.log_series_bound = degree, float(2*ratio**(degree+1)/((degree+1)*(1-ratio)))
    obj.log_rectangle = dict(assumed_lower=beta, coefficient_upper=upper, lower_certified=False)
    obj.seconds = perf_counter()-tick
    return obj


def oracle(curve, ko, ki, cutoff, count=1024):
    nodes = curve.nodes(count)
    with execution(kernels='real_bessel' if not np.iscomplexobj(ko) else 'complex_hankel'):
        a = build_muller_system(nodes, ko, ki).system_matrix
    modal = ModalSystem.from_nodal(a, np.zeros((2*count, 1)), np.zeros((1, 2*count)), [nodes])
    idx = np.r_[np.arange(-cutoff, cutoff+1)%count, count+np.arange(-cutoff, cutoff+1)%count]
    return modal.a[np.ix_(idx, idx)]


def matrix_errors(a, exact):
    n = a.shape[0]//2
    ident = np.eye(n)
    return dict(matrix_error=relative(a, exact), blocks={
        'K': relative(ident-a[:n, :n], ident-exact[:n, :n]),
        'V': relative(a[:n, n:], exact[:n, n:]),
        'T': relative(a[n:, :n], exact[n:, :n]),
        'Kp': relative(a[n:, n:]-ident, exact[n:, n:]-ident)})


def star_check():
    geo = LaurentGeometry.star(radius=1., amplitude=.25, rotation=0.)
    curve = FourierCurve(np.array([geo.coefficients.get(j, 0) for j in range(-6, 7)]))
    prep = CoefficientGeometry(geo, 160)
    cheb = ChebyshevGeometry(geo, 160)
    # Physical constants used by the repository's prior modal stress fixture.
    ko = 128.34377208884936*.05
    rows = []
    for contrast in [.5, 4., 13.3]:
        ki = ko*np.sqrt(contrast)
        exact = oracle(curve, ko, ki, 64)
        for kind, prepared, degrees in [('monomial', prep, [28, 48, 80, 120]),
                                        ('chebyshev', cheb, [40, 60, 80])]:
            for degree in degrees:
                tick = perf_counter()
                a, _ = prepared.assemble(ko, ki, 64, degree)
                row = dict(shape='SC_star', contrast=contrast, method=kind, degree_or_terms=degree,
                           bandwidth=160, cutoff=64, seconds=perf_counter()-tick, **matrix_errors(a, exact))
                rows.append(row)
                print(json.dumps(row), flush=True)
    return rows


def c_check():
    from experiments.shape_continuation.atlas_cases import c_shape_curve
    curve = c_shape_curve()
    geo = LaurentGeometry.from_coefficients(dict(zip(curve.modes, curve.coefficients)))
    ko = 128.34377208884936*.05
    rows = []
    for contrast in [.5, 13.3]:
        ki = ko*np.sqrt(contrast)
        exact = oracle(curve, ko, ki, 64)
        refined = oracle(curve, ko, ki, 64, 2048)
        for band in [96, 128, 192]:
            prep = general_geometry(geo, band)
            a, _ = prep.assemble(ko, ki, 64, 100)
            row = dict(shape='rebuilt_C', contrast=contrast, bandwidth=band, cutoff=64,
                       oracle_1024_2048=relative(exact, refined), log_interval=prep.log_rectangle,
                       **matrix_errors(a, refined))
            rows.append(row)
            print(json.dumps(row), flush=True)
    return rows


def counterexample():
    # Regular self-crossing curve z(w)=w+w^2: z(exp(+-2pi i/3))=-1,
    # |z'(t)| >= 1. W=1+w+v and |W|^2 is the polynomial below.
    band = 16
    size = 2*band+1
    ww = {(0, 0): 3, (1, 0): 1, (-1, 0): 1, (0, 1): 1,
          (0, -1): 1, (1, -1): 1, (-1, 1): 1}
    rows, cols, vals = [], [], []
    for (da, db), value in ww.items():
        for a in range(size):
            for b in range(size):
                if 0 <= a+da < size and 0 <= b+db < size:
                    rows.append((a+da)*size+b+db)
                    cols.append(a*size+b)
                    vals.append(value)
    matrix = coo_matrix((vals, (rows, cols)), shape=(size**2, size**2)).tocsr().astype(float)
    minimum = float(eigsh(matrix, k=1, which='SA', return_eigenvectors=False, v0=np.ones(size**2))[0])
    maximum = float(eigsh(matrix, k=1, which='LA', return_eigenvectors=False, v0=np.ones(size**2))[0])
    beta, upper = minimum/2, 9.
    poly = add(times(ww, 2/(upper-beta)), {(0, 0): -(upper+beta)/(upper-beta)})
    previous = embed({(0, 0): 1}, band)
    current = sparse_product(previous, poly)
    norms = [float(np.linalg.norm(current))]
    for _ in range(2, 1001):
        previous, current = current, 2*sparse_product(current, poly)-previous
        norms.append(float(np.linalg.norm(current)))
    return dict(curve='z(w)=w+w^2', bandwidth=band, beta=beta,
                exact_W_squared_minimum=0., compressed_minimum=minimum, compressed_maximum=maximum,
                max_norm_degrees_1_to_1000=max(norms), selected_norms={str(n): norms[n-1] for n in [50,100,200,1000]},
                conclusion='Positive beta passes at every tested degree on a regular self-intersecting curve.')


def identities():
    rows = []
    for alpha in [29.25, 10+2.4j, 20+4.75j, 40+11.9j]:
        n = np.arange(161)
        c = (2-(n==0))*(-1.)**n*jv(n, alpha)**2
        x = np.linspace(-1, 1, 1001)
        direct = jv(0, 2*alpha*np.sqrt((1+x)/2))
        rows.append(dict(alpha=str(alpha), coefficient_sum=float(np.sum(abs(c))),
                         predicted_sum=float(iv(0, 2*abs(np.imag(alpha)))),
                         evaluation_relative=relative(np.polynomial.chebyshev.chebval(x, c), direct)))
    # Forced local errors at A=1 accumulate quadratically, not linearly.
    previous = current = 0.
    for _ in range(1, 101):
        previous, current = current, 2*current-previous+1.
    return dict(bessel=rows, recurrence_degree=101, recurrence_unit_error_accumulation=current,
                comment='100 identical local errors at endpoint A=1 accumulate to 5050.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('part', choices=['star', 'c', 'claims'])
    args = parser.parse_args()
    result = {'star': star_check, 'c': c_check, 'claims': lambda: dict(
        identities=identities(), parseval_counterexample=counterexample())}[args.part]()
    source = Path('docs/iterations/cleaned_interfaces/node_free_modal_muller_summary.pdf')
    record = dict(part=args.part, git_head=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                  pdf_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), result=result)
    (OUTPUT/(args.part+'.json')).write_text(json.dumps(record, indent=2)+'\n')
    if args.part == 'claims':
        print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
