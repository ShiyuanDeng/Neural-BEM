"""QBX Muller solver on the real compressed IBIM boundary.

A fourth solver package, forked from ``gpr_bem_kdiff`` (which was itself
forked from ``gpr_bem_mod``). Geometry/SDF machinery (``ibim_geometry``,
``neural_sdf``, ``waveforms``, ``cylinder_reference``, ``materials``,
``scan_paths``, ``signal_processing``, ``validation``, ``geometry``) is
byte-identical all the way back to ``gpr_bem_mod`` -- only ``ibim_tmz_forward.py``
changes versus ``gpr_bem_kdiff``, plus one new file, ``qbx_kernels.py``.
``ibim_tmz_system.py`` is untouched.

Forward only. No ``ibim_tmz_adjoint`` or ``ibim_inverse`` here, same
reasoning as ``gpr_bem_kdiff``.

See ``ibim_tmz_forward.py``'s and ``qbx_kernels.py``'s module docstrings for
what changed and why: ``gpr_bem_kdiff`` handles the exact diagonal via a
local-osculating-circle Richardson limit and leaves the off-diagonal-but-near
log-singular behaviour of the hypersingular block uncorrected (flagged in its
own docstring, measured in ``docs/validation_change_log.md``); this package
replaces both with Quadrature by Expansion (Klockner, Barnett, Greengard,
O'Neil, 2013) over a band of near-diagonal entries.
"""

from .cylinder_reference import (
    cylinder_series_mode_numbers,
    line_source_incident_field,
    penetrable_cylinder_frequency_response,
    penetrable_cylinder_scattered_field,
    penetrable_cylinder_scattering_coefficient_ratio,
    penetrable_cylinder_total_field,
)
from .ibim_geometry import (
    ImplicitBoundaryBand2D,
    ImplicitBoundarySamples2D,
    build_implicit_boundary_band,
    build_implicit_boundary_samples,
    cartesian_grid_points,
    compress_implicit_boundary_band,
    perfect_circle_boundary_samples,
    project_points_to_level_set,
    regularized_cosine_delta,
)
from .ibim_tmz_forward import (
    KdiffOperatorBlocks,
    boundary_points_normals_weights,
    build_kdiff_operator_blocks,
)
from .ibim_tmz_system import (
    ImplicitTMzForwardResult,
    ImplicitTMzFrequencySystem,
    ImplicitTMzMultiFrequencyForwardResult,
    build_ibim_tmz_frequency_system,
    ibim_incident_trace_on_boundary,
    solve_ibim_tmz_frequency_response,
    solve_ibim_tmz_total_field_batch,
)
from .materials import Material
from .neural_sdf import (
    circle_signed_distance,
    circles_union_signed_distance,
    rectangle_signed_distance,
)
from .scan_paths import RectangularLoopScan2D, build_rectangular_bistatic_scan, subset_rectangular_loop_scan
from .signal_processing import bscan_from_frequency_response, inverse_frequency_transform_matrix, trapz_weights
from .validation import bscan_error_metrics, frequency_response_error_metrics
from .waveforms import gprmax_gaussian_spectrum, gprmax_gaussian_time_signal

__all__ = [
    "ImplicitBoundaryBand2D",
    "ImplicitBoundarySamples2D",
    "ImplicitTMzForwardResult",
    "ImplicitTMzFrequencySystem",
    "ImplicitTMzMultiFrequencyForwardResult",
    "KdiffOperatorBlocks",
    "Material",
    "RectangularLoopScan2D",
    "boundary_points_normals_weights",
    "build_ibim_tmz_frequency_system",
    "build_implicit_boundary_band",
    "build_implicit_boundary_samples",
    "build_kdiff_operator_blocks",
    "build_rectangular_bistatic_scan",
    "bscan_error_metrics",
    "bscan_from_frequency_response",
    "cartesian_grid_points",
    "circle_signed_distance",
    "circles_union_signed_distance",
    "compress_implicit_boundary_band",
    "cylinder_series_mode_numbers",
    "frequency_response_error_metrics",
    "gprmax_gaussian_spectrum",
    "gprmax_gaussian_time_signal",
    "ibim_incident_trace_on_boundary",
    "inverse_frequency_transform_matrix",
    "line_source_incident_field",
    "penetrable_cylinder_frequency_response",
    "penetrable_cylinder_scattered_field",
    "penetrable_cylinder_scattering_coefficient_ratio",
    "penetrable_cylinder_total_field",
    "perfect_circle_boundary_samples",
    "project_points_to_level_set",
    "rectangle_signed_distance",
    "regularized_cosine_delta",
    "solve_ibim_tmz_frequency_response",
    "solve_ibim_tmz_total_field_batch",
    "subset_rectangular_loop_scan",
    "trapz_weights",
]
