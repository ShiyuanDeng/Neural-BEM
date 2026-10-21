"""Compatibility import; implementation lives in forward_solvers/nodal_kress.py."""
import sys
from .forward_solvers import nodal_kress as _implementation
sys.modules[__name__] = _implementation
