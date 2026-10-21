"""Compatibility import for the analytic spectral geometry-update method."""
import sys
from .geometry_update_methods import analytic_spectral as _implementation
sys.modules[__name__] = _implementation
