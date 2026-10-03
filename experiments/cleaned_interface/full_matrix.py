"""Compatibility import for :mod:`bem_inverse.full_matrix`; edit the maintained module there."""
import sys
from importlib import import_module

sys.modules[__name__] = import_module('bem_inverse.full_matrix')
