"""MA-001 part B analysis: qualification, field support, frontier, truncation law, cancellation."""
import argparse
import json
from pathlib import Path

import numpy as np

from .noncircular import NMAX, PMAX, pair_sum


def tails(E):
    """T(m) = sqrt(sum_{|n|>m} |c_n|^2) for m = 0..NMAX; E has shape (columns, 2NMAX+1)."""
    n = np.abs(np.arange(-NMAX, NMAX + 1))
    energy = np.abs(E) ** 2
    return np.sqrt(np.array([energy[:, n > m].sum(axis=1) for m in range(NMAX + 1)]).T)   # (columns, NMAX+1)


def support(E, eps):
    n = np.arange(-NMAX, NMAX + 1)
    profile = np.sqrt((np.abs(E) ** 2).sum(axis=0))
    return int(np.abs(n[profile >= eps * profile.max()]).max())


def analyze(path):
    z = np.load(path)
    F = len(z['wavenumbers'])
    L = float(z['length_512'])
    delta = z['wavenumbers'] ** 2 * (z['contrast'] - 1)
    P = np.arange(-PMAX, PMAX + 1)
    out = dict(qualification={}, per_frequency=[])
    m512, n512, m1024, n1024 = z['modal_512'], z['nodal_512'], z['modal_1024'], z['nodal_1024']
    scale = lambda a: np.linalg.norm(a, axis=(1, 2))
    out['qualification']['modal_vs_nodal_512'] = float(np.max(scale(m512 - n512) / scale(n512)))
    out['qualification']['modal_vs_nodal_1024'] = float(np.max(scale(m1024 - n1024) / scale(n1024)))
    out['qualification']['grid_512_vs_1024'] = float(np.max(scale(n512 - n1024) / scale(n1024)))
    # production shape_jacobian on [1, cos 1..P, sin 1..P]; ours: cos = (J_p + J_-p)/2, sin = (J_p - J_-p)/(2i)
    prod = z['production_512']                                      # (F, pairs, 1+2P)
    mine = np.concatenate([n512[:, PMAX:PMAX + 1],
                           (n512[:, PMAX + 1:] + n512[:, PMAX - 1::-1]) / 2,
                           (n512[:, PMAX + 1:] - n512[:, PMAX - 1::-1]) / 2j], axis=1).transpose(0, 2, 1)
    out['qualification']['nodal_vs_production'] = float(np.max(scale(mine - prod) / scale(prod)))
    bound_ok = True
    for f in range(F):
        U, V, J = z['U_1024'][f], z['V_1024'][f], z['modal_1024'][f]          # (pairs, n), (P, pairs)
        cp = np.sqrt((np.linalg.norm(J[PMAX:], axis=1) ** 2 + np.linalg.norm(J[PMAX::-1], axis=1) ** 2) / 2)
        row = dict(k=float(z['wavenumbers'][f]), kL_2pi=float(z['wavenumbers'][f] * L / (2 * np.pi)))
        for eps in (1e-1, 1e-2, 1e-3):
            row[f'K_U_{eps:g}'], row[f'K_V_{eps:g}'] = support(U, eps), support(V, eps)
        for tau in (1e-2, 1e-3, 1e-4):
            row[f'frontier_{tau:g}'] = int(np.arange(PMAX + 1)[cp >= tau * cp.max()].max())
        TU, TV = tails(U), tails(V)
        Jmax = np.linalg.norm(J, axis=1).max()
        needed = {}
        for tol in (1e-3, 1e-6):
            need = []
            for p in range(0, PMAX + 1):
                exact = J[PMAX + p]
                for K in range(0, NMAX + 1):
                    Ut = np.where(np.abs(np.arange(-NMAX, NMAX + 1)) <= K, U, 0)
                    Vt = np.where(np.abs(np.arange(-NMAX, NMAX + 1)) <= K, V, 0)
                    approx = delta[f] * L * pair_sum(Ut, Vt, p).sum(axis=1)
                    err = np.linalg.norm(approx - exact)
                    if K >= p:
                        b = abs(delta[f]) * L * np.linalg.norm(TU[:, K] * TV[:, K - p] + TU[:, K - p] * TV[:, K])
                        bound_ok &= bool(err <= b * (1 + 1e-9) + 1e-14 * Jmax)
                    if err <= tol * Jmax:
                        need.append(K)
                        break
                else:
                    need.append(None)
            needed[tol] = need
            n = np.arange(-NMAX, NMAX + 1)
            trace_rel = lambda C, t: int(min(m for m in range(NMAX + 1)
                                             if np.all(tails(C)[:, m] <= t * np.linalg.norm(C, axis=1))))
            row[f'trace_K_{tol:g}'] = max(trace_rel(U, tol), trace_rel(V, tol))
            row[f'trace_K_sqrt_{tol:g}'] = max(trace_rel(U, np.sqrt(tol)), trace_rel(V, np.sqrt(tol)))
            row[f'J_needed_K_{tol:g}'] = need
        # cancellation and brightness decomposition, p = 0..frontier(1e-3)
        kappa, avail = [], []
        for p in range(0, PMAX + 1):
            terms = pair_sum(U, V, p)
            a = np.linalg.norm(np.abs(terms).sum(axis=1)) * abs(delta[f]) * L
            avail.append(a)
            kappa.append(a / max(np.linalg.norm(J[PMAX + p]), 1e-300))
        row['kappa'] = [float(x) for x in kappa]
        row['available'] = [float(x) for x in avail]
        row['column_norm'] = [float(x) for x in np.linalg.norm(J[PMAX:], axis=1)]
        out['per_frequency'].append(row)
    out['qualification']['truncation_bound_holds'] = bound_ok
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    data = Path(args.data)
    result = {}
    for path in sorted(data.glob('*.npz')):
        result[path.stem.replace('__', '/')] = analyze(path)
        q = result[path.stem.replace('__', '/')]['qualification']
        print(path.stem, json.dumps(q), flush=True)
    Path(args.output).write_text(json.dumps(result))


if __name__ == '__main__':
    main()
