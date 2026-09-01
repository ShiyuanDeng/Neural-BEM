"""Material models shared by the Neural-SDF/IBIM pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Material:
    """Homogeneous isotropic material."""

    epsr: float
    sigma: float = 0.0
    mur: float = 1.0

    def wavenumber(self, angular_frequency: float, eps0: float, mu0: float) -> complex:
        epsilon = eps0 * self.epsr - 1j * self.sigma / angular_frequency
        mu = mu0 * self.mur
        return angular_frequency * np.sqrt(mu * epsilon)
