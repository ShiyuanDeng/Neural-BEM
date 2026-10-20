"""Compatibility import: stage API and optimizer. Canonical code: ``bem_inverse.fit_stage``."""
import sys
from bem_inverse import fit_stage as _implementation
sys.modules[__name__] = _implementation
