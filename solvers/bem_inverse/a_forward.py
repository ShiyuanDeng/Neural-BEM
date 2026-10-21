"""Compatibility import for the modal Müller functions and fit-local context."""
import sys
from .forward_solvers import modal_muller as _implementation
sys.modules[__name__] = _implementation
