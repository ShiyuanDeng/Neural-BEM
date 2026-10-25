"""Standalone forward solvers: one file per physics, owning its context and ``forward_solve``.

Importing this package registers ``nodal_kress``, the default solver. ``modal_muller``
registers through ``modal_muller.register()``.
"""
from . import nodal_kress
