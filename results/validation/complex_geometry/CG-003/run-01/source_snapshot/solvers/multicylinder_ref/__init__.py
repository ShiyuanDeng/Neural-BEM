"""Independent cylindrical-harmonic reference for multiple circles."""

from .solver import (
    CircularCylinder2D,
    ConvergedFieldResult,
    MultiCylinderSolution,
    MultiCylinderSystem,
    TruncationConfig,
    TruncationConvergenceError,
    TruncationRecord,
    build_multicylinder_system,
    converge_multicylinder_scattered_field,
    line_source_incident_field_matrix,
    multicylinder_scattered_field,
    multicylinder_total_field,
    recommended_mode_order,
    solve_multicylinder_line_sources,
)

__all__ = [
    "CircularCylinder2D",
    "ConvergedFieldResult",
    "MultiCylinderSolution",
    "MultiCylinderSystem",
    "TruncationConfig",
    "TruncationConvergenceError",
    "TruncationRecord",
    "build_multicylinder_system",
    "converge_multicylinder_scattered_field",
    "line_source_incident_field_matrix",
    "multicylinder_scattered_field",
    "multicylinder_total_field",
    "recommended_mode_order",
    "solve_multicylinder_line_sources",
]
