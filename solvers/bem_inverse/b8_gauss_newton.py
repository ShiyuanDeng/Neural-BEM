"""B8. Complex data Jacobian → real J → gradient g and curvature H_GN.

Data blocks have axes (receiver, coordinate), one block per frequency. J has
axes (real measurement, coordinate). Separate functions preserve the original
time of each calculation: J/g after a state evaluation, H_GN at iteration entry.
"""
import numpy as np
from .b5_residual import normalize


def residual_jacobian(blocks, observed, weights, residual_floor):
    """Apply exactly the B5 map to each complex data derivative column."""
    J_data = np.stack(blocks, axis=1)  # (receiver, frequency, coordinate)
    return normalize(J_data, observed, weights, residual_floor)


def gradient(J, r):
    """Ordinary least-squares gradient; alternate objectives supply their own."""
    return J.T @ r


def curvature(J):
    """Gauss–Newton curvature, evaluated only when the stage starts an iteration."""
    return J.T @ J
