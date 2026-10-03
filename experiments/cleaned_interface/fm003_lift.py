"""FM-003 lifting check: can paired data be completed to the full 24 x 24 matrix using only
reciprocity and energy conservation of the scattering matrix (no shape model)?

Evaluation only. The truth is used to generate data and to score lifts, never to select one.

Model (cylindrical waves about the ring centre, ring radius 6 units > object):
    X[r, s] = c * sum_{m,n} PR[r, m] T[m, n] PS[s, n],  c = strength * i/4
    PR[r, m] = H_m(k R_r) exp(i m theta_r),  PS[s, n] = H_n(k R_s) exp(-i n theta_s)
    S = I + 2T,  Q = S P D  with P: n -> -n,  D = diag((-1)^n)
Reciprocity  <=> Q symmetric;  lossless object  <=> Q unitary.
Symmetric unitary Q = expm(i H) with H real symmetric, so the lift unknowns are the
(2N+1)(2N+2)/2 entries of H for wave orders |n| <= N. Paired data give 48 real numbers.

Usage (repository root, PYTHONPATH=solvers:.):
    python -m experiments.cleaned_interface.fm003_lift [--nodes 384] [--starts 24] [--output DIR]
"""
import argparse, json
from pathlib import Path
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor, lu_solve, expm, logm
from scipy.optimize import least_squares
from scipy.special import hankel1

from experiments.shape_continuation import forward as F
from experiments.shape_continuation.geometry import FourierCurve
from . import benchmark as b
from .io import curve_from

CASE = 'modal__c13.3__development_c'
FREQUENCIES_HZ = (0.25e9, 0.5e9, 0.75e9)
ORDERS = (2, 3, 4)
FIT_ORDER = 9                      # full-data T fit; checked by its residual


def wavenumber(f):
    return 2*np.pi*f*np.sqrt((4*np.pi*1e-7)*8.854187817e-12*6.)*.05


def full_matrix(curve, k, contrast, acq, nodes):
    pts = curve.nodes(nodes)
    assemble, receivers, incident = F._operators(pts)
    A = np.asarray(assemble(pts, k, k*np.sqrt(contrast)).system_matrix)
    C = receivers(pts, acq.receivers, k).state_rows
    field, normal = incident(pts, acq.sources, k, acq.strength)
    return C @ lu_solve(lu_factor(A), np.vstack((field.T, normal.T)))      # X[receiver, source]


class Rings:
    def __init__(self, acq):
        self.Rs, self.ts = np.hypot(*acq.sources.T), np.arctan2(acq.sources[:, 1], acq.sources[:, 0])
        self.Rr, self.tr = np.hypot(*acq.receivers.T), np.arctan2(acq.receivers[:, 1], acq.receivers[:, 0])
        self.c = complex(acq.strength)*0.25j

    def bases(self, k, N):
        n = np.arange(-N, N+1)
        PR = hankel1(n[None, :], k*self.Rr[:, None])*np.exp(1j*n[None, :]*self.tr[:, None])
        PS = hankel1(n[None, :], k*self.Rs[:, None])*np.exp(-1j*n[None, :]*self.ts[:, None])
        return n, PR, PS


def fit_T(rings, X, k, N):
    _, PR, PS = rings.bases(k, N)
    M = np.kron(PS, PR)*rings.c                                            # vec(PR T PS^T), column-major
    scale = np.linalg.norm(M, axis=0)
    T = (np.linalg.lstsq(M/scale, X.flatten('F'), rcond=1e-13)[0]/scale).reshape(2*N+1, 2*N+1, order='F')
    residual = np.linalg.norm(M @ T.flatten('F') - X.flatten('F'))/np.linalg.norm(X)
    return T, float(residual)


def constraint_errors(T):
    m = T.shape[0]; N = m//2; n = np.arange(-N, N+1)
    Q = (np.eye(m) + 2*T) @ np.fliplr(np.eye(m)) @ np.diag((-1.0)**n)
    return float(np.linalg.norm(Q.conj().T @ Q - np.eye(m))), float(np.linalg.norm(Q - Q.T))


def lift(rings, X, k, N, T_full, starts, seed):
    """Paired data -> H -> T -> full matrix. Returns per-start records and reference floors."""
    n, PR, PS = rings.bases(k, N); m = 2*N+1
    d = np.diag(X).copy()                              # receiver s is the paired receiver of source s
    PDi = np.diag((-1.0)**n) @ np.fliplr(np.eye(m))    # (P D)^{-1}
    iu = np.triu_indices(m)

    def T_of(h):
        H = np.zeros((m, m)); H[iu] = h; H = H + H.T - np.diag(np.diag(H))
        return (expm(1j*H) @ PDi - np.eye(m))/2

    def paired(T):
        return np.einsum('sm,mn,sn->s', PR, T, PS)*rings.c

    def residual(h):
        r = (paired(T_of(h)) - d)/np.linalg.norm(d)
        return np.r_[r.real, r.imag]

    lifted = lambda T: rings.c*PR @ T @ PS.T
    off = ~np.eye(len(d), dtype=bool)
    c0 = T_full.shape[0]//2
    T_cut = T_full[c0-N:c0+N+1, c0-N:c0+N+1]
    floors = dict(paired=float(np.linalg.norm(paired(T_cut)-d)/np.linalg.norm(d)),
                  full=float(np.linalg.norm(lifted(T_cut)-X)/np.linalg.norm(X)))
    A = np.stack([np.outer(PR[s], PS[s]).flatten() for s in range(len(d))])*rings.c
    T_lin = np.linalg.lstsq(A, d, rcond=None)[0].reshape(m, m)
    linear = float(np.linalg.norm(lifted(T_lin)-X)/np.linalg.norm(X))
    h0 = np.real(logm(np.fliplr(np.eye(m)) @ np.diag((-1.0)**n))/1j)[iu]   # S = I (no scattering)
    rng = np.random.default_rng(seed); records = []
    for t in range(starts):
        spread = (0.0, 0.3, 1.0, 3.0)[t % 4]
        sol = least_squares(residual, h0 + spread*rng.standard_normal(h0.size), method='lm',
                            xtol=1e-14, ftol=1e-14, max_nfev=4000)
        T = T_of(sol.x); Xl = lifted(T)
        records.append(dict(start=t, spread=spread, paired_residual=float(np.linalg.norm(sol.fun)),
                            full_error=float(np.linalg.norm(Xl-X)/np.linalg.norm(X)),
                            offdiagonal_error=float(np.linalg.norm((Xl-X)[off])/np.linalg.norm(X[off])),
                            lifted=Xl))
    best = min(r['paired_residual'] for r in records)
    near = [r for r in records if r['paired_residual'] <= 1.01*best + 1e-12]
    # truth-free ambiguity: spread of lifted matrices among the best-fitting starts
    ambiguity = max((np.linalg.norm(a['lifted']-c['lifted'])/np.linalg.norm(c['lifted'])
                     for a in near for c in near), default=0.)
    for r in records:
        r.pop('lifted')
    chosen = min(records, key=lambda r: r['paired_residual'])
    return dict(N=N, unknowns_real=int(h0.size), data_real=2*len(d), floors=floors, linear_lift_error=linear,
                best_paired_residual=best, chosen_full_error=chosen['full_error'],
                chosen_offdiagonal_error=chosen['offdiagonal_error'], best_fit_starts=len(near),
                ambiguity_among_best=float(ambiguity),
                full_error_range_among_best=[min(r['full_error'] for r in near), max(r['full_error'] for r in near)],
                starts=records)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nodes', type=int, default=384); p.add_argument('--starts', type=int, default=24)
    p.add_argument('--seed', type=int, default=20261004)
    p.add_argument('--output', default=str(b.ROOT/'results/validation/cleaned_interfaces/FM-003/lift'))
    a = p.parse_args()
    out = Path(a.output); out.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    row = next(r for r in b.descriptors() if r['id'] == CASE)
    acq, rings = b.acquisition(), Rings(b.acquisition())
    contrast = float(row['contrast'])
    truth = curve_from(json.loads((b.ROOT/row['truth']).read_text()))
    report = dict(case=CASE, nodes=a.nodes, starts=a.starts, seed=a.seed, orders=ORDERS, fit_order=FIT_ORDER)
    # gate 1: calibration on a centred disk, |S_nn| = 1 and T diagonal
    k = wavenumber(0.5e9)
    T, res = fit_T(rings, full_matrix(FourierCurve.circle(1.0, 0j), k, contrast, acq, a.nodes), k, 8)
    diag = np.diag(T)
    report['disk'] = dict(fit_residual=res, max_abs_S_nn_minus_1=float(np.max(abs(abs(1+2*diag)-1))),
                          offdiagonal_over_diagonal=float(abs(T-np.diag(diag)).max()/abs(diag).max()))
    report['frequencies'] = []
    for f in FREQUENCIES_HZ:
        k = wavenumber(f)
        X = full_matrix(truth, k, contrast, acq, a.nodes)
        X2 = full_matrix(truth, k, contrast, acq, 2*a.nodes)
        T_full, res = fit_T(rings, X, k, FIT_ORDER)
        unitary, symmetric = constraint_errors(T_full)
        c0 = FIT_ORDER
        energy = {str(N): float(np.linalg.norm(T_full[c0-N:c0+N+1, c0-N:c0+N+1])/np.linalg.norm(T_full)) for N in range(1, 7)}
        entry = dict(frequency_hz=f, resolution_change=float(np.linalg.norm(X2-X)/np.linalg.norm(X2)),
                     full_fit_residual=res, unitarity_error=unitary, symmetry_error=symmetric,
                     T_norm_fraction_by_order=energy,
                     lifts=[lift(rings, X, k, N, T_full, a.starts, a.seed) for N in ORDERS])
        report['frequencies'].append(entry)
        print(f'{f/1e9:.2f} GHz: fit {res:.1e}, unitarity {unitary:.1e}, symmetry {symmetric:.1e}', flush=True)
        for L in entry['lifts']:
            print(f'   N={L["N"]} ({L["unknowns_real"]} unknowns): floor full {L["floors"]["full"]:.2e}, '
                  f'chosen lift error {L["chosen_full_error"]:.2e}, best-fit starts {L["best_fit_starts"]}/{a.starts}, '
                  f'ambiguity among best {L["ambiguity_among_best"]:.2e}, linear lift {L["linear_lift_error"]:.2f}', flush=True)
    report['seconds'] = perf_counter() - started
    (out/'lift.json').write_text(json.dumps(report, indent=1))
    print(f'wrote {out/"lift.json"} in {report["seconds"]:.0f} s')


if __name__ == '__main__':
    main()
