"""Compatibility import: modal physics service. Canonical code: ``bem_inverse.a_forward``."""
import sys
from bem_inverse import a_forward as _implementation
sys.modules[__name__] = _implementation
