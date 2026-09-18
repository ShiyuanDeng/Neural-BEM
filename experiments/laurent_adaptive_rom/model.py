"""Protected trace spans and finite-system defect bounds; no reference solve."""
from time import perf_counter

import numpy as np
from scipy.linalg import lu_solve, qr, svd, svdvals

from experiments.laurent_tangent_rom.model import derivative

ARMS = ('JOINT_TANGENT', 'PRIMAL_TANGENT', 'PRIMAL_DUAL_TANGENT')
GUARD_LIMITS = dict(primal_residual=1e-7, field_relative_bound=1e-7,
                    derivative_relative_bound=1e-4)


def normalized(block):
    norm = np.linalg.norm(block)
    return block/norm if norm else block


def span(snapshot):
    u, s, _ = svd(snapshot, full_matrices=False)
    rank = int(np.count_nonzero(s > 1e-12*s[0])) if len(s) and s[0] else 0
    return u[:, :rank], s


def protected_basis(protected, corrections):
    """Every prefix after protected_rank retains the complete protected span."""
    p, _ = span(np.concatenate([normalized(x) for x in protected],axis=1))
    x = np.concatenate([normalized(x) for x in corrections],axis=1)
    # Reorthogonalize to suppress roundoff contamination of the protected span.
    for _ in range(2):
        x -= p @ (p.conj().T @ x)
    u, s, _ = svd(x,full_matrices=False)
    # Absolute threshold relative to unit-norm input blocks, rather than to
    # a possibly all-roundoff residual's largest singular value.
    keep = min(int(np.count_nonzero(s>1e-12)),len(p)-p.shape[1])
    v, _ = qr(np.column_stack((p,u[:, :keep])),mode='economic')
    return dict(v=v,protected_rank=p.shape[1],snapshot_rank=v.shape[1],singular_values=s)


def bases(case, training_derivatives, ledger=None):
    started = perf_counter()
    tangents = []
    for d in training_derivatives:
        if ledger is not None:
            ledger.charge(rhs_batches=1,rhs_columns=case.b.shape[1])
        tangents.append(lu_solve(case.factors,d['db']-d['total']@case.u))
    if ledger is not None:
        ledger.charge(rhs_batches=1,rhs_columns=case.c.shape[0])
    dual = lu_solve(case.factors,case.c.conj().T,trans=2)
    v,s = span(np.concatenate([normalized(x) for x in [case.u,*tangents]],axis=1))
    bank = dict(JOINT_TANGENT=dict(v=v,protected_rank=0,snapshot_rank=v.shape[1],singular_values=s),
        PRIMAL_TANGENT=protected_basis([case.u],tangents),
        PRIMAL_DUAL_TANGENT=protected_basis([case.u,dual],tangents))
    return bank,perf_counter()-started


def rank_ladder(minimum, maximum):
    return sorted({r for r in (8,12,16,24,32,40,48,56,64,80,96,112,128,144,minimum,maximum)
                   if max(minimum,1)<=r<=maximum})


def stability(a, training_derivatives, ledger=None):
    """Expensive stability diagnostic; computed once per candidate for all arms."""
    if ledger is not None:
        ledger.charge(stability_svds=1+len(training_derivatives))
    started = perf_counter()
    sigma = float(svdvals(a)[-1])
    norms = [float(svdvals(d['total'])[0]) for d in training_derivatives]
    return dict(sigma_min=sigma,derivative_operator_norms=norms,seconds=perf_counter()-started)


def relative_bound(absolute, candidate):
    denominator = np.linalg.norm(candidate)-absolute
    if not np.isfinite(absolute) or denominator<=0:
        return float(np.finfo(float).max)
    return float(min(absolute/denominator,np.finfo(float).max))


def guard(a, b, c, solved, training_derivatives, spectrum, ledger=None):
    """Needs matrices and a reduced solve only; cannot inspect full-state truth.

    Exact-arithmetic defect bounds to the finite matrix model. Floating-point
    read-back uses an explicit 1e-10 relative allowance; no interval certification.
    """
    started = perf_counter()
    v,x = solved['v'],solved['state']
    z = v @ solved['transfer'].conj().T
    residual = b-a@x
    dual_residual = c.conj().T-a.conj().T@z
    pairs = min(b.shape[1],c.shape[0])
    rnorm = np.linalg.norm(residual[:, :pairs],axis=0)
    snorm = np.linalg.norm(dual_residual[:, :pairs],axis=0)
    sigma = spectrum['sigma_min']
    if not np.isfinite(sigma) or sigma<=0:
        raise ValueError('A positive finite minimum singular value is required.')
    estate = rnorm/sigma
    dual_term = np.abs(np.sum(z[:, :pairs].conj()*residual[:, :pairs],axis=0))
    field_absolute = float(np.linalg.norm(dual_term+snorm*estate))
    field_relative = relative_bound(field_absolute,np.diag(solved['y']))
    if len(training_derivatives)!=len(spectrum['derivative_operator_norms']):
        raise ValueError('Each training derivative needs its operator norm.')
    absolute,relative,ingredients = [],[],[]
    for d,anorm in zip(training_derivatives,spectrum['derivative_operator_norms']):
        if ledger is not None:
            ledger.charge(rhs_batches=1,rhs_columns=b.shape[1])
        force = d['db']-d['total']@x
        dx = v @ lu_solve(solved['factors'],v.conj().T@force)
        rj = force-a@dx
        c_effective = d['dc']-z.conj().T@d['total']
        pair_bound = (np.linalg.norm(c_effective[:pairs],axis=1)*estate
            +np.abs(np.sum(z[:, :pairs].conj()*rj[:, :pairs],axis=0))
            +snorm/sigma*(np.linalg.norm(rj[:, :pairs],axis=0)+anorm*estate))
        ingredients.append(dict(effective_receiver_norms=np.linalg.norm(c_effective[:pairs],axis=1).tolist(),
            tangent_residual_norms=np.linalg.norm(rj[:, :pairs],axis=0).tolist(),
            dual_tangent_contractions=np.abs(np.sum(z[:, :pairs].conj()*rj[:, :pairs],axis=0)).tolist(),
            derivative_operator_norm=anorm))
        bound = float(np.linalg.norm(pair_bound))
        absolute.append(bound)
        relative.append(relative_bound(bound,np.diag(derivative(solved,d))))
    primal = float(np.linalg.norm(residual)/max(np.linalg.norm(b),1e-300))
    accepted = bool(np.isfinite(primal) and primal<=GUARD_LIMITS['primal_residual']
        and field_relative<=GUARD_LIMITS['field_relative_bound']
        and max(relative,default=np.inf)<=GUARD_LIMITS['derivative_relative_bound'])
    return dict(accepted=accepted,primal_residual=primal,
        field_absolute_bound=field_absolute,field_relative_bound=field_relative,
        derivative_absolute_bounds=absolute,derivative_relative_bounds=relative,
        worst_derivative_relative_bound=max(relative,default=np.finfo(float).max),
        sigma_min=sigma,primal_pair_residual_norms=rnorm.tolist(),
        dual_pair_residual_norms=snorm.tolist(),dual_primal_contractions=dual_term.tolist(),
        derivative_bound_ingredients=ingredients,seconds=perf_counter()-started)
