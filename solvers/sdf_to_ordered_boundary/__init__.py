"""Isolated implicit-field to smooth ordered-boundary research pipeline.

This package produces the existing :mod:`ordered_boundary` geometry objects.
It is intentionally not imported by any active forward, adjoint, or inverse
solver pipeline.
"""

from .arclength import ArcLengthConfig, reparameterize_by_arclength
from .artifacts import (
    plot_boundary_diagnostics,
    plot_run_record,
    write_metrics_csv,
    write_npz,
    write_strict_json,
)
from .experiment import (
    ComparisonExperimentResult,
    ComparisonProfile,
    ComparisonShape,
    ExperimentRunRecord,
    analytic_comparison_shapes,
    comparison_profile,
    run_comparison_experiment,
)
from .fields import (
    CallableImplicitField2D,
    CircleSDF,
    CountedImplicitField2D,
    EllipseLevelSet,
    FieldEvaluationCounts,
    ImplicitField2D,
    RadialFourierLevelSet,
    TorchImplicitField2D,
)
from .frontend import (
    BoundaryTouchingContourError,
    ComponentCountError,
    ContourExtractionError,
    FrontendComponent,
    FrontendConfig,
    FrontendError,
    FrontendResult,
    OpenContourError,
    PolygonDiagnostics,
    PolygonValidationError,
    ProjectionConfig,
    ProjectionError,
    ProjectionResult,
    extract_frontend_components,
    prepare_single_component,
    project_to_zero_set,
    resample_closed_polygon,
)
from .method_a import MethodAConfig, fit_method_a, fit_method_a_from_samples
from .method_b import MethodBConfig, fit_method_b, fit_method_b_from_samples
from .method_c import (
    MethodCConfig,
    RefinementStage,
    RefinementWeights,
    fit_method_c,
)
from .metrics import (
    BoundaryMetricConfig,
    BoundaryMetrics,
    FrozenCurveSamplingMetrics,
    compute_boundary_metrics,
    frozen_curve_sampling_metrics,
)
from .representations import (
    FourierBoundary,
    FourierLeastSquaresResult,
    PeriodicSplineBoundary,
    fit_fourier_least_squares,
)
from .results import (
    ArcLengthDiagnostics,
    ArcLengthReparameterizationResult,
    BoundaryMethodResult,
    LeastSquaresDiagnostics,
    MethodResult,
    ResidualDiagnostics,
)

__all__ = [
    "ArcLengthConfig",
    "ArcLengthDiagnostics",
    "ArcLengthReparameterizationResult",
    "BoundaryMethodResult",
    "BoundaryMetricConfig",
    "BoundaryMetrics",
    "BoundaryTouchingContourError",
    "CallableImplicitField2D",
    "CircleSDF",
    "ComponentCountError",
    "ComparisonExperimentResult",
    "ComparisonProfile",
    "ComparisonShape",
    "ContourExtractionError",
    "CountedImplicitField2D",
    "EllipseLevelSet",
    "ExperimentRunRecord",
    "FieldEvaluationCounts",
    "FourierBoundary",
    "FourierLeastSquaresResult",
    "FrozenCurveSamplingMetrics",
    "FrontendComponent",
    "FrontendConfig",
    "FrontendError",
    "FrontendResult",
    "ImplicitField2D",
    "LeastSquaresDiagnostics",
    "MethodAConfig",
    "MethodBConfig",
    "MethodCConfig",
    "MethodResult",
    "OpenContourError",
    "PeriodicSplineBoundary",
    "PolygonDiagnostics",
    "PolygonValidationError",
    "ProjectionConfig",
    "ProjectionError",
    "ProjectionResult",
    "RadialFourierLevelSet",
    "RefinementStage",
    "RefinementWeights",
    "ResidualDiagnostics",
    "TorchImplicitField2D",
    "analytic_comparison_shapes",
    "comparison_profile",
    "extract_frontend_components",
    "compute_boundary_metrics",
    "fit_fourier_least_squares",
    "fit_method_a",
    "fit_method_a_from_samples",
    "fit_method_b",
    "fit_method_b_from_samples",
    "fit_method_c",
    "frozen_curve_sampling_metrics",
    "plot_boundary_diagnostics",
    "plot_run_record",
    "prepare_single_component",
    "project_to_zero_set",
    "reparameterize_by_arclength",
    "resample_closed_polygon",
    "run_comparison_experiment",
    "write_metrics_csv",
    "write_npz",
    "write_strict_json",
]
