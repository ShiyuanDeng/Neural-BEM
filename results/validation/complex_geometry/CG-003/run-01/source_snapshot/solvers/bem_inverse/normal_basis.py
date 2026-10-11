"""Arclength-normalized shape directions shared with the research atlas."""
import numpy as np
from .continuation.geometry import arclength_angles, integer


def orthonormal_normal_basis(curve, band):
    """Arclength harmonics scaled to unit `L^2(ds)` norm on this curve.

    Columns are ordered `[1, cos(s), sin(s), ..., cos(band s), sin(band s)]`
    in the normalized arclength angle, matching `geometry.normal_basis` up to
    the scaling `1/sqrt(L)` and `sqrt(2/L)`. That scaling is what makes a
    column norm comparable between harmonics, between wavenumbers and between
    iterates with different perimeters.
    """
    band = integer(band, "atlas band", minimum=0)
    angles, length = arclength_angles(curve)
    phase = angles[:, None] * np.arange(1, band + 1)
    raw = np.column_stack((np.ones(len(angles)), np.cos(phase), np.sin(phase)))
    scale = np.concatenate(([1.0 / np.sqrt(length)],
                            np.repeat(np.sqrt(2.0 / length), 2 * band)))
    # Interleave cos/sin so column p+1 pairs with p for a harmonic, as the
    # reordering below expects; keep the flat layout the solver already uses.
    order = np.empty(2 * band + 1, int)
    order[0] = 0
    order[1::2] = np.arange(1, band + 1)
    order[2::2] = np.arange(band + 1, 2 * band + 1)
    return raw[:, order] * scale[order]

