"""Kress/Nyström Müller solver for one :class:`PeriodicCurve2D`.

This package is a numerical sibling of :mod:`gpr_bem_mod`, not one of its
backends.  It intentionally accepts ordered periodic geometry instead of an
implicit boundary cloud and remains direct-import only while its comparison
and adjoint acceptance evidence is established.
"""

from ._kernels import (
    MullerKernelEvaluation,
    PairGeometry,
    evaluate_muller_kernel_differences,
    pair_geometry,
)
from .conventions import MullerConvention, PROJECT_MULLER_CONVENTION
from .forward import (
    ExteriorReceiverOperator,
    ExteriorRepresentationResult,
    KressSolveConfig,
    KressTMzForwardResult,
    KressTMzMultiFrequencyForwardResult,
    build_exterior_receiver_operator,
    evaluate_exterior_representation,
    kress_incident_trace_on_boundary,
    solve_kress_tmz_frequency_response,
    solve_kress_tmz_total_field_batch,
)
from .geometry import PeriodicCurveAdapter, adapt_periodic_curve
from .operators import (
    MullerAssemblyConfig,
    MullerDifferenceBlocks,
    build_muller_difference_blocks,
)
from .system import (
    KressTMzFrequencySystem,
    build_kress_tmz_frequency_system,
    build_muller_system,
)
from .materials import Material

__all__ = [
    "ExteriorReceiverOperator",
    "ExteriorRepresentationResult",
    "KressSolveConfig",
    "KressTMzForwardResult",
    "KressTMzFrequencySystem",
    "KressTMzMultiFrequencyForwardResult",
    "Material",
    "MullerAssemblyConfig",
    "MullerConvention",
    "MullerDifferenceBlocks",
    "MullerKernelEvaluation",
    "PROJECT_MULLER_CONVENTION",
    "PairGeometry",
    "PeriodicCurveAdapter",
    "adapt_periodic_curve",
    "build_exterior_receiver_operator",
    "build_kress_tmz_frequency_system",
    "build_muller_difference_blocks",
    "build_muller_system",
    "evaluate_exterior_representation",
    "evaluate_muller_kernel_differences",
    "kress_incident_trace_on_boundary",
    "pair_geometry",
    "solve_kress_tmz_frequency_response",
    "solve_kress_tmz_total_field_batch",
]
