"""Compatibility import: complete-trial coefficient velocities. Canonical code: ``bem_inverse.b6_geometry_derivatives``."""
import sys
from bem_inverse import b6_geometry_derivatives as _implementation
sys.modules[__name__] = _implementation
