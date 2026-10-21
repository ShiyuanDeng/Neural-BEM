"""Compatibility import for the similarity geometry-update method."""
import sys
from .geometry_update_methods import similarity as _implementation
sys.modules[__name__] = _implementation
