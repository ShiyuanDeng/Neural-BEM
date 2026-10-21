"""Compatibility exports for geometry methods; maintained maths lives in their own files."""
from .geometry_update_methods import control_step
from .geometry_update_methods.spectral import (
    CONSTRUCTION, SpectralProjectedUpdate, arclength_quadrature, push_and_refit, sample_grid,
)
from .geometry_update_methods.certified_spectral import (
    CertifiedSpace, CertifiedSpectralUpdate, WINDOW, FULL_WINDOWS, SPEED_FACTOR,
    ROLES, TIERS, ORDERS, VALIDITY, VALIDITY_SAMPLED_FIRST, pad,
)
from .geometry_update_methods.certificates import regularity_floor, increment_bound
