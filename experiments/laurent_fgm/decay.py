"""Decay-law measurement and the literature truncation rules.

Two published rules are tested as written:

* Fang-Jiang-Su 2024, arXiv:2408.02199, section 2: keep (k,l) with
  ``||k-l||_1 <= q ln N``.  On a curve the multi-index is scalar, so this is the
  band ``|m-n| <= q ln N`` with ``N`` the matrix order.  Their Corollary 3.1
  justifies it through ``|K_kl| <= (M/2pi) exp(-b ||l-k||_1)``, ``b < b*``.
* Jiang-Wang-Yu 2021, as already implemented in
  ``experiments/laurent_literature/scalar.py``: keep
  ``(1+(m-n)^2)^mu * min(1+m^2, 1+n^2) <= N^2``.

Both are geometry-blind as published.  The report asks whether a
geometry-dependent interaction set does better; ``fjs_band`` takes the band
half-width directly, so a b*-driven rule can be fed through the same path.
"""
import numpy as np
from scipy.linalg import lu_factor, lu_solve


def band_profile(block):
    """max and rms of |A_mn| on each diagonal offset d = m-n."""
    size = block.shape[0]
    magnitude = np.abs(block)
    offsets = np.arange(-(size - 1), size)
    peak = np.array([np.abs(np.diag(magnitude, k)).max() for k in offsets])
    mean = np.array([np.sqrt((np.diag(magnitude, k)**2).mean()) for k in offsets])
    folded = np.arange(size)
    return dict(offset=folded,
                peak=np.array([max(peak[offsets == d][0], peak[offsets == -d][0])
                               for d in folded]),
                rms=np.array([np.sqrt(.5 * (mean[offsets == d][0]**2
                                            + mean[offsets == -d][0]**2))
                              for d in folded]))


def decay_rate(offset, value, low=None, high=None, floor=1e-13):
    """Least-squares exponential rate of the envelope over a clean window.

    Returns the rate b in |A|_d ~ C exp(-b d), fitted where the profile is
    above the numerical floor and below its own maximum.
    """
    value = np.asarray(value, dtype=float)
    reference = value.max()
    low = 1 if low is None else low
    usable = np.flatnonzero((offset >= low) & (value > floor * reference))
    if usable.size < 4:
        return dict(rate=float('nan'), points=int(usable.size), r2=float('nan'))
    stop = usable[-1] if high is None else min(usable[-1], high)
    window = usable[usable <= stop]
    if window.size < 4:
        return dict(rate=float('nan'), points=int(window.size), r2=float('nan'))
    x, y = offset[window].astype(float), np.log(value[window])
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    total = y - y.mean()
    r2 = 1. - float(residual @ residual) / float(total @ total) if total.any() else 1.
    return dict(rate=float(-slope), points=int(window.size), r2=r2,
                first=int(window[0]), last=int(window[-1]))


def fjs_band(cutoff, halfwidth):
    """Keep |m-n| <= halfwidth, tiled over the 2x2 Muller block structure."""
    modes = np.arange(-cutoff, cutoff + 1)
    inside = np.abs(modes[:, None] - modes[None, :]) <= halfwidth
    return np.block([[inside, inside], [inside, inside]])


def jwy_mask(cutoff, mu=1.2, order=None):
    """Jiang-Wang-Yu 2021 index mask, tiled over the Muller blocks."""
    modes = np.arange(-cutoff, cutoff + 1, dtype=float)
    m, n = np.meshgrid(modes, modes, indexing='ij')
    order = 2 * cutoff + 1 if order is None else order
    inside = (1 + (m - n)**2)**mu * np.minimum(1 + m * m, 1 + n * n) <= order**2
    return np.block([[inside, inside], [inside, inside]])


def truncate(matrix, mask):
    kept = matrix * mask
    dropped = matrix - kept
    return kept, dict(
        matrix_error=float(np.linalg.norm(dropped) / np.linalg.norm(matrix)),
        retained=float(mask.mean()),
        nonzeros=int(mask.sum()))


def pipeline(matrix, rhs, receiver):
    state = lu_solve(lu_factor(matrix), rhs)
    return state, receiver @ state


def relative(value, reference):
    denominator = np.linalg.norm(reference)
    if denominator == 0:
        return float('nan')
    return float(np.linalg.norm(value - reference) / denominator)
