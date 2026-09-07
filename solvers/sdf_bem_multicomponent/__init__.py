"""Automatic multi-component ordered-boundary/Kress experiment.

This sibling package deliberately does not import :mod:`sdf_inverse`, so its
geometry and forward paths remain usable without coupling to that package.
Nothing here is imported by an established solver dispatcher.
"""

from .circle_union import CircleUnionSDF2D
from .geometry import (
    GridParityConfirmationDiagnostics,
    MultiComponentGeometryDiagnostics,
    MultiComponentOrderedSDFGeometryBuild,
    MultiComponentOrderedSDFGeometryConfig,
    MultiComponentOrderedSDFGeometryError,
    build_multicomponent_ordered_sdf_geometry,
)
from .forward import (
    MaterialSpec,
    MultiComponentBoundaryPairedForwardResult,
    MultiComponentPairedForwardResult,
    PairedForwardProblem,
    predict_multicomponent_kress_paired_boundary_response,
    predict_multicomponent_kress_paired_response,
)
from .split_fixture import (
    CassiniSplitConfig,
    CassiniSplitFrame,
    CassiniSplitGeometryBuild,
    CassiniSplitSDF2D,
    CassiniSplitStage,
    CassiniSplitTopology,
    CassiniSplitTrajectory2D,
    CassiniSplitTransitionError,
    build_cassini_split_geometry,
)
from .trajectory import (
    BoundaryTrajectoryFrame,
    FRAME_STATUSES,
    INVALID,
    RaggedBoundaryTrajectory,
    SOLVER_READY,
    TOPOLOGY_TRANSITION,
)

__all__ = [
    "BoundaryTrajectoryFrame",
    "CassiniSplitConfig",
    "CassiniSplitFrame",
    "CassiniSplitGeometryBuild",
    "CassiniSplitSDF2D",
    "CassiniSplitStage",
    "CassiniSplitTopology",
    "CassiniSplitTrajectory2D",
    "CassiniSplitTransitionError",
    "CircleUnionSDF2D",
    "FRAME_STATUSES",
    "GridParityConfirmationDiagnostics",
    "INVALID",
    "MaterialSpec",
    "MultiComponentBoundaryPairedForwardResult",
    "MultiComponentGeometryDiagnostics",
    "MultiComponentOrderedSDFGeometryBuild",
    "MultiComponentOrderedSDFGeometryConfig",
    "MultiComponentOrderedSDFGeometryError",
    "MultiComponentPairedForwardResult",
    "PairedForwardProblem",
    "RaggedBoundaryTrajectory",
    "SOLVER_READY",
    "TOPOLOGY_TRANSITION",
    "build_cassini_split_geometry",
    "build_multicomponent_ordered_sdf_geometry",
    "predict_multicomponent_kress_paired_boundary_response",
    "predict_multicomponent_kress_paired_response",
]
