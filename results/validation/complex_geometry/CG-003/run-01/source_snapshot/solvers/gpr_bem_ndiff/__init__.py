"""EXPERIMENT: normal-offset differenced Muller solver on the real compressed IBIM boundary.

Forked from ``gpr_bem_kdiff``. Only ``build_kdiff_operator_blocks`` in
``ibim_tmz_forward.py`` differs: it drops the osculating-circle Richardson
diagonal and instead recovers every operator entry the ``gpr_bem_mod`` way --
whole-row evaluation at normal-offset targets ``x_i +- d n_i``, two-side
averaged, Richardson-extrapolated over ``d`` and ``2d``, applied to the
already-differenced Muller kernels. See that file's docstring. Reversible:
``rm -rf solvers/gpr_bem_ndiff``.

Geometry/SDF machinery
(``ibim_geometry``, ``neural_sdf``, ``waveforms``, ``cylinder_reference``,
``materials``, ``scan_paths``, ``signal_processing``, ``validation``,
``geometry``) is byte-identical to ``gpr_bem_mod`` -- only the formulation
files change (``ibim_tmz_forward.py``, ``ibim_tmz_system.py``), same
convention that already separates ``gpr_bem_ref``/``gpr_bem_mod``.

Forward only. No ``ibim_tmz_adjoint`` or ``ibim_inverse`` here -- porting the
adjoint is explicitly out of scope until this forward formulation itself is
validated (see ``docs/legacy/ibim_error_mitigation_literature_codex.md`` Section 0
and Issue 8), and this one is not validated yet.

See ``docs/validation_change_log.md`` ("Plan: kernel-differenced quadrature
on the real (compressed) boundary") for why this exists and
``solvers/gpr_bem_kdiff/ibim_tmz_forward.py`` for what is and is not proven
about the local diagonal treatment.
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
