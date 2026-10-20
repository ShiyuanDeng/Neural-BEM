"""Compatibility import: frequency-independent Laurent geometry. Canonical code: ``bem_inverse.a1_geometry``."""
import sys
from bem_inverse import a1_geometry as _implementation
sys.modules[__name__] = _implementation
