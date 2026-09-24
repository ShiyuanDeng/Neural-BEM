"""Stage controls kept separate from optimization and observations."""
from dataclasses import dataclass
import numpy as np
from .geometry import integer


@dataclass(frozen=True)
class Stage:
    wavenumber: float
    update_modes: int
    curve_modes: int
    nodes: int
    curvature_modes: int

    def __post_init__(self):
        if not np.isfinite(self.wavenumber) or self.wavenumber <= 0:
            raise ValueError("Stage wavenumber must be positive.")
        for name in ("update_modes", "curve_modes", "nodes", "curvature_modes"):
            object.__setattr__(self, name, integer(getattr(self, name), name))
        if self.nodes % 2 or self.nodes <= 2 * max(self.curve_modes, self.update_modes):
            raise ValueError("Even Kress nodes must resolve both curve and update modes.")
        if self.curve_modes < self.update_modes:
            raise ValueError("Curve storage must accommodate the normal update band.")


def paper_wavenumbers():
    return 1.0 + 0.25 * np.arange(117)


def paper_stage(wavenumber, contrast, perimeter, *, previous_curve_modes=1,
                points_per_wavelength=20, minimum_nodes=64, curvature_factor=2):
    """§4 update band; §2.1 curvature band. k and L must be nondimensionalized.

    Curve storage uses max(k,ki) conservatively. Nodes also satisfy the Fourier
    Nyquist constraint, so 'points_per_wavelength' is a lower bound, not an
    assertion of the paper's exact discretization count. Default 20 is a pilot
    setting; the paper reports 70 for inversion and 100 for observations.
    """
    for name, value in (("wavenumber", wavenumber), ("contrast", contrast),
                         ("perimeter", perimeter), ("points_per_wavelength", points_per_wavelength),
                         ("curvature_factor", curvature_factor)):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive.")
    largest = wavenumber * max(1, np.sqrt(contrast))
    update = max(1, int(np.floor(3 * largest)))
    storage = max(integer(previous_curve_modes, "previous_curve_modes"), update,
                  int(np.ceil(points_per_wavelength * perimeter * largest / (2 * np.pi))))
    nodes = max(integer(minimum_nodes, "minimum_nodes"), 2 * (storage + 1))
    nodes += nodes % 2
    return Stage(wavenumber, update, storage, nodes, max(1, int(np.ceil(curvature_factor * wavenumber))))
