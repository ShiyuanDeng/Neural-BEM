"""Compatibility import; implementation lives in forward_solvers/modal_muller.py."""
import sys
from .forward_solvers import modal_muller as _implementation
sys.modules[__name__] = _implementation
