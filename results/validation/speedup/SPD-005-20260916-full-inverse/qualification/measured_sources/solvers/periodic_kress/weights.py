"""Kress weights for the canonical periodic logarithm.

The normalization is

``L(theta) = log(4 sin(theta / 2)**2)``.

The returned weights approximate ``integral L(t-s) f(s) ds`` on an even,
endpoint-free, uniform ``2*pi`` grid.  This module deliberately knows nothing
about a boundary, Helmholtz kernels, or a transmission formulation.
"""

from __future__ import annotations

import operator

import numpy as np

TWO_PI = 2.0 * np.pi


def _validated_node_count(num_nodes: int) -> int:
    if isinstance(num_nodes, (bool, np.bool_)):
        raise TypeError("num_nodes must be an integer, not bool.")
    try:
        count = operator.index(num_nodes)
    except TypeError as exc:
        raise TypeError("num_nodes must be an integer.") from exc
    if count < 4 or count % 2:
        raise ValueError("num_nodes must be an even integer at least 4.")
    return count


def kress_log_weights(num_nodes: int) -> np.ndarray:
    """Return the circulant weight vector for the full canonical logarithm.

    Entry ``(i-j) % N`` weights source node ``j`` at target node ``i``.  The
    finite Fourier sum includes the special Nyquist term.  FFT construction is
    both faster and less roundoff-prone than evaluating the dense cosine sum.
    """

    count = _validated_node_count(num_nodes)
    half = count // 2
    modes = np.arange(1, half, dtype=np.int64)
    reciprocal_spectrum = np.zeros(count, dtype=np.complex128)
    reciprocal_spectrum[modes] = 0.5 / modes
    reciprocal_spectrum[count - modes] = 0.5 / modes
    cosine_sum = np.fft.fft(reciprocal_spectrum).real
    nyquist_cosine = np.where(np.arange(count) % 2 == 0, 1.0, -1.0)
    weights = -(TWO_PI / half) * cosine_sum - (np.pi / half**2) * nyquist_cosine
    weights.setflags(write=False)
    return weights


def kress_log_weight_matrix(num_nodes: int) -> np.ndarray:
    """Return the dense circulant matrix associated with :func:`kress_log_weights`."""

    count = _validated_node_count(num_nodes)
    indices = np.arange(count, dtype=np.int64)
    matrix = kress_log_weights(count)[
        (indices[:, None] - indices[None, :]) % count
    ]
    matrix.setflags(write=False)
    return matrix
