"""Askham et al. (arXiv:2308.00559v1), Section 3, reflected biased walk."""
import numpy as np


def scif_path(frequencies, *, seed, upward_probability=.603, max_visits=1000):
    """Visit index 0, then i+1 with probability p, else max(0,i-1).

    Stop on FIRST arrival at the highest frequency, as in the paper. The
    operational cap produces an explicitly incomplete path, never a forced
    upward suffix. Downward steps at zero repeat zero.
    """
    values = tuple(frequencies)
    if not values or np.any(np.diff(values) <= 0):
        raise ValueError("Frequencies must be nonempty and strictly increasing.")
    if not 0 < upward_probability <= 1 or max_visits < 1:
        raise ValueError("Invalid probability or visit cap.")
    rng, indices = np.random.default_rng(seed), [0]
    while indices[-1] != len(values) - 1 and len(indices) < max_visits:
        index = indices[-1]
        indices.append(index + 1 if rng.random() < upward_probability else max(0, index - 1))
    return dict(indices=indices, frequencies=[values[i] for i in indices],
                completed=indices[-1] == len(values) - 1, seed=seed,
                upward_probability=upward_probability, max_visits=max_visits)


def recursive_modes(wavenumber, radius, factor=1.):
    if min(wavenumber, radius, factor) <= 0:
        raise ValueError("Wavenumber, estimated radius, and factor must be positive.")
    return max(1, int(np.ceil(factor * wavenumber * radius)))
