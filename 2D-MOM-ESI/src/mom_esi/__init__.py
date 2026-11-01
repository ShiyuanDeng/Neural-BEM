"""Two-dimensional TM electromagnetic forward simulation."""

from .io import save_result
from .solver import SimulationResult, make_domain, points_on_circle, simulate

__all__ = ["SimulationResult", "make_domain", "points_on_circle", "save_result", "simulate"]
