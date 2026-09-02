"""Solver-neutral inverse tools for smooth single-component Torch implicits.

The public seam deliberately separates implicit geometry, forward prediction,
and low-dimensional numerical optimization.  Both MOD and Kress therefore see
the same ordered boundary and the same inverse objective.
"""

from .forward import (
    MaterialSpec,
    PairedForwardProblem,
    PairedForwardResult,
    predict_paired_response,
)
from .geometry import (
    OrderedSDFGeometryBuild,
    OrderedSDFGeometryConfig,
    build_ordered_sdf_geometry,
    ordered_curve_to_mod_boundary,
)
from .models import (
    CircleSDF2D,
    EllipseLevelSet2D,
    RadialRandomFeatureImplicit2D,
    TorchParameterController,
    build_circle_parameter_controller,
    build_ellipse_parameter_controller,
    build_radial_random_feature_parameter_controller,
    circle_parameter_controller,
)
from .optimization import (
    ComplexScatteredData,
    ParameterFDConfig,
    ParameterFDInverseResult,
    ParameterFDIteration,
    normalized_complex_residual,
    run_parameter_fd_inverse,
)

__all__ = [
    "CircleSDF2D",
    "ComplexScatteredData",
    "EllipseLevelSet2D",
    "MaterialSpec",
    "OrderedSDFGeometryBuild",
    "OrderedSDFGeometryConfig",
    "PairedForwardProblem",
    "PairedForwardResult",
    "ParameterFDConfig",
    "ParameterFDInverseResult",
    "ParameterFDIteration",
    "RadialRandomFeatureImplicit2D",
    "TorchParameterController",
    "build_circle_parameter_controller",
    "build_ellipse_parameter_controller",
    "build_ordered_sdf_geometry",
    "build_radial_random_feature_parameter_controller",
    "circle_parameter_controller",
    "normalized_complex_residual",
    "ordered_curve_to_mod_boundary",
    "predict_paired_response",
    "run_parameter_fd_inverse",
]
