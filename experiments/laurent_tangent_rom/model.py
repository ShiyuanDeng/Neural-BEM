"""Frozen-subspace solves and exact tangents of that reduced model.

The modal state already uses flux coefficients (u, J*d_n u). No nodal
sampling, changing basis, or continuous Hadamard formula enters this tangent.
"""
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve, svd

ARMS = ('FORWARD', 'TANGENT', 'PRIMAL_DUAL')


def bases(case, training_derivatives, ledger=None):
    """Only training derivatives may enter this function; no truth/heldout API."""
    started = perf_counter()
    tangent = []
    for d in training_derivatives:
        if ledger is not None:
            ledger.charge(rhs_batches=1, rhs_columns=case.b.shape[1])
        tangent.append(lu_solve(case.factors, d['db'] - d['total'] @ case.u))
    if ledger is not None:
        ledger.charge(rhs_batches=1, rhs_columns=case.c.shape[0])
    dual = lu_solve(case.factors, case.c.conj().T, trans=2)
    snapshot_blocks = dict(FORWARD=[case.u], TANGENT=[case.u, *tangent],
                           PRIMAL_DUAL=[case.u, dual])
    output = {}
    for arm, blocks in snapshot_blocks.items():
        tic = perf_counter()
        normalized = [b / np.linalg.norm(b) for b in blocks if np.linalg.norm(b) > 0]
        u, s, _ = svd(np.concatenate(normalized, axis=1), full_matrices=False)
        rank = int(np.count_nonzero(s > 1e-12 * s[0]))
        output[arm] = dict(v=u[:, :rank], singular_values=s,
                           snapshot_rank=rank, svd_seconds=perf_counter()-tic)
    return output, perf_counter()-started


def rank_ladder(maximum):
    return sorted({r for r in (8, 12, 16, 24, 32, 48, 64, 96, 128, maximum)
                   if 0 < r <= maximum})


def solve(case, v, ledger=None):
    if v.ndim != 2 or v.shape[0] != case.a.shape[0] or not 0 < v.shape[1] <= v.shape[0]:
        raise ValueError('Basis must have shape (full dimension, positive reduced rank).')
    if ledger is not None:
        ledger.charge(factorizations=1, rhs_batches=2,
                      rhs_columns=case.b.shape[1]+case.c.shape[0])
    started = perf_counter()
    ar, br, cr = v.conj().T @ case.a @ v, v.conj().T @ case.b, case.c @ v
    factors = lu_factor(ar)
    q = lu_solve(factors, br)
    # cr ar^{-1} is a bilinear transfer; conjugation is only used by the
    # adjoint solve. Using an un-conjugated dual here would be incorrect.
    transfer = lu_solve(factors, cr.conj().T, trans=2).conj().T
    return dict(v=v, ar=ar, br=br, cr=cr, factors=factors, q=q,
                state=v @ q, y=cr @ q, transfer=transfer,
                seconds=perf_counter()-started)


def derivative(solved, d):
    v, q = solved['v'], solved['q']
    dar = v.conj().T @ d['total'] @ v
    dbr, dcr = v.conj().T @ d['db'], d['dc'] @ v
    return dcr @ q + solved['transfer'] @ (dbr - dar @ q)


def storage(dimension, rank, sources, receivers, directions=6):
    """Complex scalar slots, including basis and every projected derivative.

    Includes the forward LU separately. Excludes transient full assembly,
    validation and snapshot arrays; these are NOT process-memory savings.
    """
    full = (directions+1)*(dimension**2 + dimension*(sources+receivers)) + dimension**2
    reduced = dimension*rank + (directions+1)*(rank**2 + rank*(sources+receivers)) + rank**2
    return dict(full_model_slots=full, reduced_model_slots=reduced,
                reduced_storage_ratio=reduced/full, basis_slots=dimension*rank,
                reduced_matrix_slots=rank**2, rank_fraction=rank/dimension)
