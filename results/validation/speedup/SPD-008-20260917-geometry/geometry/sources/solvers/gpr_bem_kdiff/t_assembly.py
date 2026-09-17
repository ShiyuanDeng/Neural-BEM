"""Pluggable assembly contract for the Muller hypersingular difference block.

Every implementation returns ``dT = T_exterior - T_interior``.  The Muller
system builder, not an assembler, applies the lower-left ``-dT`` sign.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import numpy as np
import torch


@dataclass(frozen=True)
class TAssemblyContext:
    """Geometry and already-evaluated legacy data available to a T assembler."""

    points: np.ndarray
    normals: np.ndarray
    weights: np.ndarray
    k_exterior: complex
    k_interior: complex
    direct_kernel: np.ndarray
    legacy_diagonal: np.ndarray
    merge_distance: float
    bounds: tuple[tuple[float, float], tuple[float, float]]
    level: float
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None


@dataclass(frozen=True)
class TAssemblyReport:
    method: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TAssemblyResult:
    matrix: np.ndarray
    report: TAssemblyReport


@runtime_checkable
class TAssembler(Protocol):
    """Structural interface accepted by the shared kdiff solve path."""

    name: str

    def assemble(self, context: TAssemblyContext) -> TAssemblyResult:
        ...


@dataclass(frozen=True)
class LegacyLocalT:
    """Current kdiff T: direct off-diagonals plus osculating self entries."""

    name: str = "legacy_local"

    def assemble(self, context: TAssemblyContext) -> TAssemblyResult:
        matrix = np.asarray(context.direct_kernel * context.weights[None, :], dtype=complex)
        np.fill_diagonal(matrix, context.legacy_diagonal)
        return TAssemblyResult(
            matrix=matrix,
            report=TAssemblyReport(method=self.name),
        )


def resolve_t_assembler(value: TAssembler | None) -> TAssembler:
    assembler: TAssembler = LegacyLocalT() if value is None else value
    if not isinstance(assembler, TAssembler):
        raise TypeError("t_assembly must implement assemble(TAssemblyContext) and expose a name.")
    return assembler


__all__ = [
    "LegacyLocalT",
    "TAssembler",
    "TAssemblyContext",
    "TAssemblyReport",
    "TAssemblyResult",
    "resolve_t_assembler",
]
