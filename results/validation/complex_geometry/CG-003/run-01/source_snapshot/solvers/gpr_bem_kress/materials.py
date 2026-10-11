"""Material values owned by the Kress/Nyström solver package."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Material:
    """Homogeneous isotropic material.

    The value object is package-local for the same reason each existing
    ``gpr_bem_*`` sibling owns its material type: no solver depends on another
    solver's package identity.  Comparison orchestration constructs equivalent
    values from one solver-neutral scene specification.
    """

    epsr: float
    sigma: float = 0.0
    mur: float = 1.0

    def wavenumber(self, angular_frequency: float, eps0: float, mu0: float) -> complex:
        epsilon = eps0 * self.epsr - 1j * self.sigma / angular_frequency
        mu = mu0 * self.mur
        return angular_frequency * np.sqrt(mu * epsilon)


__all__ = ["Material"]
