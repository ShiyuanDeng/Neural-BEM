"""Opt-in Kress/Nyström Müller backend for one :class:`PeriodicCurve2D`.

This candidate is intentionally not re-exported by :mod:`gpr_bem_mod` and is
not registered with ``solver_select``.  Import it explicitly while its block,
system, and physical convergence evidence is being established.
"""

from ._kernels import (
    MullerKernelEvaluation,
    PairGeometry,
    evaluate_muller_kernel_differences,
    pair_geometry,
)
from .conventions import MullerConvention, PROJECT_MULLER_CONVENTION
from .forward import (
    ExteriorRepresentationResult,
    OrderedSolveConfig,
    OrderedTMzForwardResult,
    OrderedTMzMultiFrequencyForwardResult,
    evaluate_exterior_representation,
    ordered_incident_trace_on_boundary,
    solve_ordered_tmz_frequency_response,
    solve_ordered_tmz_total_field_batch,
)
from .geometry import PeriodicCurveAdapter, adapt_periodic_curve
from .operators import (
    MullerAssemblyConfig,
    MullerDifferenceBlocks,
    build_muller_difference_blocks,
)
from .system import (
    OrderedTMzFrequencySystem,
    build_muller_system,
    build_ordered_tmz_frequency_system,
)

__all__ = [
    "ExteriorRepresentationResult",
    "MullerAssemblyConfig",
    "MullerConvention",
    "MullerDifferenceBlocks",
    "MullerKernelEvaluation",
    "OrderedSolveConfig",
    "OrderedTMzForwardResult",
    "OrderedTMzFrequencySystem",
    "OrderedTMzMultiFrequencyForwardResult",
    "PROJECT_MULLER_CONVENTION",
    "PairGeometry",
    "PeriodicCurveAdapter",
    "adapt_periodic_curve",
    "build_muller_difference_blocks",
    "build_muller_system",
    "build_ordered_tmz_frequency_system",
    "evaluate_exterior_representation",
    "evaluate_muller_kernel_differences",
    "ordered_incident_trace_on_boundary",
    "pair_geometry",
    "solve_ordered_tmz_frequency_response",
    "solve_ordered_tmz_total_field_batch",
]
