"""Solver-neutral ordered, node-based smooth-boundary geometry for 2-D BIEs."""

from .analytic import circle, ellipse, fourier_curve, star
from .boundary import OrderedBoundary2D
from .boundary_parameterization import OrderedBoundaryParameterization2D
from .curve import PeriodicCurve2D
from .parameterization import (
    CurveEvaluation2D,
    CurveEvaluator2D,
    CurveProvenance2D,
    PeriodicParameterization2D,
)
from .validation import (
    BoundaryValidationConfig,
    CurveGeometryReport,
    OrderedBoundaryReport,
    OrderedBoundaryValidationError,
    validate_ordered_parameterization,
    validate_periodic_parameterization,
)

__all__ = [
    "BoundaryValidationConfig",
    "CurveEvaluation2D",
    "CurveEvaluator2D",
    "CurveGeometryReport",
    "CurveProvenance2D",
    "OrderedBoundary2D",
    "OrderedBoundaryParameterization2D",
    "OrderedBoundaryReport",
    "OrderedBoundaryValidationError",
    "PeriodicCurve2D",
    "PeriodicParameterization2D",
    "circle",
    "ellipse",
    "fourier_curve",
    "star",
    "validate_ordered_parameterization",
    "validate_periodic_parameterization",
]
