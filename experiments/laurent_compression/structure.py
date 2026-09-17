"""Predicted versus measured support of the Laurent remainder (gate G1b).

Every nonidentity block is kernel_matrix(P, S, K_u) for coefficient arrays P, S:

    block[m,n] = 2*pi*( S[m,-n] + sum_l L_l * P[m-l, l-n] ),  L_l = -1/|l|

If P vanishes outside a beta_P box and S outside a beta_S box then the block is
EXACTLY zero outside

    log part     |m-n| <= 2*beta_P
    smooth part  |m| <= beta_S and |n| <= beta_S

so the support is an algebraic consequence of the argument bandwidths, not a
magnitude threshold on the block. Two tiers are reported:

  formula   beta from (Laurent half-degree d, effective Bessel order p*,
            log-series order): radius_squared = delta * conj(delta) has half
            degree 2d, so R^p has 2dp; the dot polynomials add 2d; the log
            quotient adds about d per retained series power.
  measured  the actual argument arrays' support at roundoff.

The deployed ANALYTIC_SUPPORT mask uses the MEASURED argument support, which is
exact. The formula is the scientific claim, scored by how loose it is.
"""
import numpy as np

from .adapters import BLOCK_NAMES, forward_arguments

ROUNDOFF = 1e-15


def laurent_half_degree(geometry):
    return max(abs(j) for j in geometry.coefficients)


def bessel_weights(ko_scaled, ki_scaled, terms):
    ao = ai = 1.0
    harmonic = 0.0
    dp, dq = [], []
    for p in range(terms):
        if p:
            ao *= -(ko_scaled * ko_scaled / 4) / (p * p)
            ai *= -(ki_scaled * ki_scaled / 4) / (p * p)
            harmonic += 1 / p
        po, pi = -ao / (4 * np.pi), -ai / (4 * np.pi)
        qo = ao * (.25j + (harmonic - np.euler_gamma - np.log(ko_scaled / 2)) / (2 * np.pi))
        qi = ai * (.25j + (harmonic - np.euler_gamma - np.log(ki_scaled / 2)) / (2 * np.pi))
        dp.append(abs(po - pi))
        dq.append(abs(qo - qi))
    return np.array(dp), np.array(dq)


def effective_bessel_order(ko_scaled, ki_scaled, terms, floor):
    dp, dq = bessel_weights(ko_scaled, ki_scaled, terms)
    weight = np.maximum(dp, dq)
    significant = np.flatnonzero(weight > floor * weight.max())
    return int(significant[-1]) + 1 if significant.size else 1


def formula_beta(half_degree, order, log_order, bandwidth):
    """Predicted argument half-bandwidths for the P and S arguments."""
    p_side = 2 * half_degree * order + 2 * half_degree
    s_side = 2 * half_degree * order + half_degree * log_order
    return int(min(bandwidth, p_side)), int(min(bandwidth, s_side))


def argument_half_support(array, tol=ROUNDOFF):
    """Smallest beta with |array| <= tol*peak outside the beta box."""
    peak = np.abs(array).max()
    if peak == 0:
        return 0
    bandwidth = (array.shape[0] - 1) // 2
    significant = np.abs(array) > tol * peak
    index = np.arange(-bandwidth, bandwidth + 1)
    rows, cols = np.meshgrid(index, index, indexing='ij')
    reach = np.maximum(np.abs(rows), np.abs(cols))[significant]
    return int(reach.max()) if reach.size else 0


def measured_betas(operator, tol=ROUNDOFF):
    """(beta_P, beta_S) per block from the actual assembly arguments."""
    p_args, s_args = forward_arguments(operator)
    order = dict(V=0, K=1, Kp=1, T=2)
    return ({name: argument_half_support(p_args[order[name]], tol) for name in BLOCK_NAMES},
            {name: argument_half_support(s_args[order[name]], tol) for name in BLOCK_NAMES})


def support_from_beta(cutoff, beta, kind):
    modes = np.arange(-cutoff, cutoff + 1)
    m, n = np.meshgrid(modes, modes, indexing='ij')
    if kind == 'log':
        return np.abs(m - n) <= 2 * beta
    if kind == 'smooth':
        return (np.abs(m) <= beta) & (np.abs(n) <= beta)
    raise ValueError(kind)


def block_support(block, floor):
    peak = np.abs(block).max()
    if peak == 0:
        return np.zeros(block.shape, bool)
    return np.abs(block) > floor * peak


def analytic_masks(case, tol=ROUNDOFF):
    """Per-block exact-support masks for the log and smooth parts."""
    p_beta, s_beta = measured_betas(case.operator, tol)
    log = {n: support_from_beta(case.cutoff, p_beta[n], 'log') for n in BLOCK_NAMES}
    smooth = {n: support_from_beta(case.cutoff, s_beta[n], 'smooth') for n in BLOCK_NAMES}
    # The Maue term folds V's own split into T, so T inherits V's reach as well.
    log['T'] = log['T'] | log['V']
    smooth['T'] = smooth['T'] | smooth['V']
    return log, smooth, p_beta, s_beta


def support_report(case, floor, weight_floor):
    half_degree = laurent_half_degree(case.geometry)
    scale = case.geometry.scale
    order = effective_bessel_order(case.ko * scale, case.ki * scale, case.terms, weight_floor)
    log_order = case.operator.prepared.log_order
    formula_p, formula_s = formula_beta(half_degree, order, log_order, case.bandwidth)
    log_masks, smooth_masks, p_beta, s_beta = analytic_masks(case)
    rows = []
    for kind, blocks, exact, beta, predicted in (
            ('log', case.log_blocks, log_masks, p_beta, formula_p),
            ('smooth', case.smooth_blocks, smooth_masks, s_beta, formula_s)):
        bound = {n: support_from_beta(case.cutoff, predicted, kind) for n in BLOCK_NAMES}
        if kind == 'log':
            bound['T'] = bound['T'] | bound['V']
        for name, block in blocks.items():
            seen = block_support(block, floor)
            rows.append(dict(
                part=kind, block=name, half_degree=half_degree,
                effective_bessel_order=order, log_series_order=log_order,
                formula_beta=predicted, measured_argument_beta=beta[name],
                formula_fraction=float(bound[name].mean()),
                exact_support_fraction=float(exact[name].mean()),
                block_fraction_at_floor=float(seen.mean()),
                exact_violations=int(np.count_nonzero(seen & ~exact[name])),
                formula_violations=int(np.count_nonzero(seen & ~bound[name])),
                exact_holds=bool(not np.any(seen & ~exact[name])),
                formula_holds=bool(not np.any(seen & ~bound[name])),
                exact_looseness=float(exact[name].mean() / max(seen.mean(), 1e-300))))
    summary = dict(half_degree=half_degree, effective_bessel_order=order,
                   log_series_order=log_order, formula_beta_p=formula_p,
                   formula_beta_s=formula_s,
                   measured_beta_p={k: int(v) for k, v in p_beta.items()},
                   measured_beta_s={k: int(v) for k, v in s_beta.items()})
    return rows, summary


def decay_profile(block, cutoff):
    """Mean |entry| by |m-n| and by max(|m|,|n|): the two candidate structures."""
    modes = np.arange(-cutoff, cutoff + 1)
    m, n = np.meshgrid(modes, modes, indexing='ij')
    magnitude = np.abs(block)
    peak = max(magnitude.max(), 1e-300)
    diagonal, box = [], []
    for d in range(2 * cutoff + 1):
        sel = np.abs(m - n) == d
        if sel.any():
            diagonal.append(dict(offset=d, mean=float(magnitude[sel].mean() / peak),
                                 maximum=float(magnitude[sel].max() / peak)))
    for r in range(cutoff + 1):
        sel = np.maximum(np.abs(m), np.abs(n)) == r
        if sel.any():
            box.append(dict(radius=r, mean=float(magnitude[sel].mean() / peak),
                            maximum=float(magnitude[sel].max() / peak)))
    return diagonal, box
