"""Compatibility import for the Gaussian Lipschitz geometry-update method."""
import sys
from .geometry_update_methods import gaussian_lipschitz as _implementation
sys.modules[__name__] = _implementation
