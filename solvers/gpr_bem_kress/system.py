"""Müller system composition for the Kress/Nyström solver."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np

from ordered_boundary import PeriodicCurve2D

from .materials import Material
from .conventions import PROJECT_MULLER_CONVENTION
from .operators import (
    MullerAssemblyConfig,
    MullerDifferenceBlocks,
    build_muller_difference_blocks,
)


def _positive_finite(value: float, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not bool.")
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _validate_supported_materials(exterior: Material, interior: Material) -> None:
    if not isinstance(exterior, Material) or not isinstance(interior, Material):
        raise TypeError("exterior and interior must be gpr_bem_kress.Material objects.")
    if not np.isclose(exterior.mur, 1.0, rtol=0.0, atol=1.0e-14) or not np.isclose(
        interior.mur,
        1.0,
        rtol=0.0,
        atol=1.0e-14,
    ):
        raise ValueError(
            "The initial ordered Müller formulation supports nonmagnetic media only; "
            "unequal/permeable media require a scaled-flux derivation."
        )
    if exterior.sigma != 0.0 or interior.sigma != 0.0:
        raise ValueError(
            "The high-level ordered Müller pipeline currently supports lossless "
            "materials only. Reconcile the repository phasor/conductivity sign and "
            "validate a passive lossy reference before enabling sigma != 0; the "
            "lower-level complex-wavenumber API remains available for numerical tests."
        )


@dataclass(frozen=True)
class KressTMzFrequencySystem:
    """One directly solvable ``2N x 2N`` ordered Müller system."""

    geometry: PeriodicCurve2D
    angular_frequency: float | None
    k_exterior: complex
    k_interior: complex
    assembly_config: MullerAssemblyConfig
    difference_blocks: MullerDifferenceBlocks
    system_matrix: np.ndarray
    condition_number: float
    assembly_seconds: float
    diagnostics: Mapping[str, object]

    @property
    def num_nodes(self) -> int:
        return self.geometry.num_nodes

    @property
    def a11(self) -> np.ndarray:
        return self.system_matrix[: self.num_nodes, : self.num_nodes]

    @property
    def a12(self) -> np.ndarray:
        return self.system_matrix[: self.num_nodes, self.num_nodes :]

    @property
    def a21(self) -> np.ndarray:
        return self.system_matrix[self.num_nodes :, : self.num_nodes]

    @property
    def a22(self) -> np.ndarray:
        return self.system_matrix[self.num_nodes :, self.num_nodes :]


def build_muller_system(
    curve: PeriodicCurve2D,
    k_exterior: complex,
    k_interior: complex,
    *,
    angular_frequency: float | None = None,
    config: MullerAssemblyConfig | None = None,
    compute_condition_number: bool = False,
) -> KressTMzFrequencySystem:
    """Assemble the accepted ``[I-dK,dV;-dT,I+dKp]`` convention."""

    started = perf_counter()
    if not isinstance(compute_condition_number, (bool, np.bool_)):
        raise TypeError("compute_condition_number must be boolean.")
    frequency = (
        None
        if angular_frequency is None
        else _positive_finite(angular_frequency, name="angular_frequency")
    )
    blocks = build_muller_difference_blocks(
        curve,
        k_exterior,
        k_interior,
        config=config,
    )
    count = blocks.num_nodes
    matrix_started = perf_counter()
    matrix = np.empty((2 * count, 2 * count), dtype=np.complex128)
    matrix[:count, :count] = -blocks.delta_k
    matrix[:count, count:] = blocks.delta_v
    matrix[count:, :count] = -blocks.delta_t
    matrix[count:, count:] = blocks.delta_kp
    diagonal = np.arange(count)
    matrix[diagonal, diagonal] += 1.0
    matrix[count + diagonal, count + diagonal] += 1.0
    if not np.all(np.isfinite(matrix)):
        raise FloatingPointError("Müller system composition produced non-finite entries.")
    matrix_seconds = float(perf_counter() - matrix_started)
    matrix.setflags(write=False)
    condition_started = perf_counter()
    condition = (
        float(np.linalg.cond(matrix)) if compute_condition_number else float("nan")
    )
    condition_seconds = float(perf_counter() - condition_started)
    elapsed = float(perf_counter() - started)
    diagnostics = MappingProxyType(
        {
            "geometry_id": blocks.diagnostics["geometry_id"],
            "num_nodes": count,
            "unknown_order": ("u_D", "u_N"),
            "system_formula": "[[I-DeltaK, DeltaV], [-DeltaT, I+DeltaKp]]",
            "jump_terms_added": "identity_once_in_A11_and_A22",
            "solve_form": "direct_unsquared",
            "condition_number_computed": bool(compute_condition_number),
            "condition_number_kind": "raw_mixed_unit_nodal_2_norm",
            "condition_number_scale_invariant": False,
            "retained_system_matrix_bytes": int(matrix.nbytes),
            "timings_seconds": MappingProxyType(
                {
                    "difference_blocks": blocks.build_seconds,
                    "matrix_composition": matrix_seconds,
                    "condition_estimate": condition_seconds,
                }
            ),
            "conventions": PROJECT_MULLER_CONVENTION.as_mapping(),
        }
    )
    return KressTMzFrequencySystem(
        geometry=curve,
        angular_frequency=frequency,
        k_exterior=blocks.k_exterior,
        k_interior=blocks.k_interior,
        assembly_config=blocks.config,
        difference_blocks=blocks,
        system_matrix=matrix,
        condition_number=condition,
        assembly_seconds=elapsed,
        diagnostics=diagnostics,
    )


def build_kress_tmz_frequency_system(
    curve: PeriodicCurve2D,
    angular_frequency: float,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    config: MullerAssemblyConfig | None = None,
    compute_condition_number: bool = False,
) -> KressTMzFrequencySystem:
    """Build one nonmagnetic TMz system from package-owned material values."""

    _validate_supported_materials(exterior, interior)
    omega = _positive_finite(angular_frequency, name="angular_frequency")
    epsilon_zero = _positive_finite(eps0, name="eps0")
    mu_zero = _positive_finite(mu0, name="mu0")
    k_exterior = complex(exterior.wavenumber(omega, epsilon_zero, mu_zero))
    k_interior = complex(interior.wavenumber(omega, epsilon_zero, mu_zero))
    return build_muller_system(
        curve,
        k_exterior,
        k_interior,
        angular_frequency=omega,
        config=config,
        compute_condition_number=compute_condition_number,
    )


__all__ = [
    "KressTMzFrequencySystem",
    "build_kress_tmz_frequency_system",
    "build_muller_system",
]
