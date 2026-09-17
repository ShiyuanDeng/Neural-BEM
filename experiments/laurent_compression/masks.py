"""Retention rules on the remainder of the modal Muller operator.

A mask is a boolean array on the full 2M x 2M system, assembled from four
independent M x M block masks in the layout [[K, V], [T, Kp]] used by
adapters.assemble_blocks. Blocks are allocated independently: a flattened
matrix would let the numerically largest block absorb the whole budget.

No Hermitian symmetry or conjugate-symmetric structure is imposed. Kp is
constructed as flip(K).T by the solver, so its mask is allowed to come out
related to K's by the data rather than by assumption.
"""
import numpy as np

from .adapters import BLOCK_NAMES


def stack(block_masks):
    return np.block([[block_masks['K'], block_masks['V']],
                     [block_masks['T'], block_masks['Kp']]])


def _top_fraction(score, fraction):
    """Deterministic top-`fraction` selection; ties broken by flat index."""
    size = score.size
    keep = int(np.floor(fraction * size + 0.5))
    keep = max(0, min(size, keep))
    if keep == 0:
        return np.zeros(score.shape, bool)
    if keep >= size:
        return np.ones(score.shape, bool)
    flat = score.reshape(-1)
    order = np.lexsort((np.arange(size), -flat))
    mask = np.zeros(size, bool)
    mask[order[:keep]] = True
    return mask.reshape(score.shape)


def full(case, label, **_):
    blocks = case.remainder_blocks(label)
    return stack({n: np.ones(blocks[n].shape, bool) for n in BLOCK_NAMES})


def band(case, label, width, **_):
    cutoff = case.cutoff
    modes = np.arange(-cutoff, cutoff + 1)
    m, n = np.meshgrid(modes, modes, indexing='ij')
    inside = np.abs(m - n) <= width
    return stack({name: inside.copy() for name in BLOCK_NAMES})


def forward(case, label, fraction, **_):
    blocks = case.remainder_blocks(label)
    return stack({n: _top_fraction(np.abs(blocks[n]), fraction) for n in BLOCK_NAMES})


def derivative_aware(case, label, fraction, derivatives, floor, **_):
    """Score each entry by forward and training-derivative magnitude together."""
    blocks = case.remainder_blocks(label)
    derivative_blocks = [case.derivative_remainder_blocks(d, label) for d in derivatives]
    norms = [np.linalg.norm(blocks[n]) for n in BLOCK_NAMES]
    norms += [np.linalg.norm(db[n]) for db in derivative_blocks for n in BLOCK_NAMES]
    reference = max(norms) if norms else 1.0
    chosen = {}
    for name in BLOCK_NAMES:
        denominator = max(np.linalg.norm(blocks[name]), floor * reference)
        score = np.abs(blocks[name]) / denominator
        for db in derivative_blocks:
            d_denominator = max(np.linalg.norm(db[name]), floor * reference)
            score = np.maximum(score, np.abs(db[name]) / d_denominator)
        chosen[name] = _top_fraction(score, fraction)
    return stack(chosen)


def analytic_support(case, label, **_):
    """Exact argument-derived support; no magnitude thresholding on the block."""
    from .structure import analytic_masks
    log, smooth, _, _ = analytic_masks(case)
    if label == 'VERIFIED_SINGULAR_SPLIT':
        chosen = smooth
    else:
        chosen = {n: log[n] | smooth[n] for n in BLOCK_NAMES}
    return stack({n: chosen[n].copy() for n in BLOCK_NAMES})


def retention(mask, case, label):
    """Per-block and total retained fraction of the candidate pool."""
    size = mask.shape[0] // 2
    quadrants = dict(K=mask[:size, :size], V=mask[:size, size:],
                     T=mask[size:, :size], Kp=mask[size:, size:])
    report = {f'retained_{n}': float(quadrants[n].mean()) for n in BLOCK_NAMES}
    report['retained_total'] = float(mask.mean())
    report['retained_count'] = int(np.count_nonzero(mask))
    report['candidate_count'] = int(mask.size)
    return report


def derivative_support_union(mask, case, derivatives, label, floor):
    """Charge the union of the mask with entries any training derivative needs."""
    blocks = [case.derivative_remainder_blocks(d, label) for d in derivatives]
    size = mask.shape[0] // 2
    union = mask.copy()
    for db in blocks:
        needed = {}
        for name in BLOCK_NAMES:
            peak = np.abs(db[name]).max()
            needed[name] = np.abs(db[name]) > floor * max(peak, 1e-300)
        union = union | stack(needed)
    return float(union.mean())
