"""Discrete parameter-grid Fourier algebra; no quadrature or kernel formulas."""
import numpy as np
from scipy.linalg import block_diag


def modes(count, fraction=1.0):
    if count % 2 or count < 4:
        raise ValueError('An even native grid is required.')
    if fraction == 1:
        return np.arange(-count // 2, count // 2)
    if fraction not in (.25, .5, .75):
        raise ValueError('Only frozen fractions are supported.')
    retained = int(count * fraction)
    retained -= 1 - retained % 2
    return np.arange(-(retained // 2), retained // 2 + 1)


def synthesis(curves, fraction=1.0):
    blocks, labels, components = [], [], []
    for index, curve in enumerate(curves):
        m = modes(curve.num_nodes, fraction)
        theta = 2 * np.pi * (curve.parameters - curve.parameters[0]) / curve.period
        blocks.append(np.exp(1j * theta[:, None] * m) / np.sqrt(curve.num_nodes))
        labels.extend(m)
        components.extend([index] * len(m))
    one_trace = block_diag(*blocks)
    return (block_diag(one_trace, one_trace), np.tile(labels, 2),
            np.tile(components, 2))


def scale_maps(a, b, c, ell):
    s = np.r_[np.ones(a.shape[0] // 2), np.full(a.shape[0] // 2, ell)]
    return a * s[:, None] / s[None, :], b * s[:, None], c / s, s


def project(a, b, c, p):
    return p.conj().T @ a @ p, p.conj().T @ b, c @ p


def centered_mask(labels, components, width):
    """Ordinary integer mode distance; cross-component interactions stay dense."""
    return ((np.abs(labels[:, None] - labels[None, :]) <= width)
            | (components[:, None] != components[None, :]))


def mask_operator(a, mask):
    identity = np.eye(a.shape[0])
    return identity + (a - identity) * mask


def oracle_retention(block, tail):
    energy = np.sort(np.abs(block.ravel()) ** 2)[::-1]
    total = float(energy.sum())
    if total == 0:
        return 0
    return min(len(energy), int(np.searchsorted(np.cumsum(energy),
                                               (1 - tail ** 2) * total)) + 1)
