"""Compatibility entry point; maintained API: :mod:`bem_inverse`."""
from bem_inverse import Observation, Problem, Execution, make_backend, register_backend, CumulativePolicy

__all__ = ['Observation', 'Problem', 'Execution', 'make_backend', 'register_backend', 'CumulativePolicy']
