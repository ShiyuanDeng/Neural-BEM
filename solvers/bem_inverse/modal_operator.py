"""Compatibility import: modal matrix, waves and Hadamard helpers. Canonical code: ``bem_inverse.a2_muller``."""
import sys
from bem_inverse import a2_muller as _implementation
sys.modules[__name__] = _implementation
