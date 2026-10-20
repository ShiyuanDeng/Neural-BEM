"""Compatibility import: certified finite geometry trials. Canonical code: ``bem_inverse.c10_geometry_trial``."""
import sys
from bem_inverse import c10_geometry_trial as _implementation
sys.modules[__name__] = _implementation
