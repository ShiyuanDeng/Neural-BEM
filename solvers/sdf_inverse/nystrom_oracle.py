"""Independent Nystrom observations for a parameterized target curve.

``nystrom_ref`` is an oracle, not a production solver: it re-implements the
geometry, kernels, quadrature, assembly and evaluation of the same Muller
transmission problem from scratch and shares only the problem definition with
the packages under test.  Using it here keeps the inverse observations
independent of both compared forwards, which analytic Mie data already does
for a circle and which no self-generated data could do for a star.

The remaining caveat is stated rather than hidden: Kress and this oracle
belong to the same Nystrom/Muller method family, so a shared *formulation*
error would not be exposed by this comparison, only a shared implementation
error would be.  MOD's compressed-cloud discretisation has no such kinship.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
from time import perf_counter
from typing import Any, Callable

import numpy as np

from .forward import MaterialSpec, PairedForwardProblem


Parameterization = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]


def _readonly(values: Any, *, dtype: Any) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _even_node_count(value: Any, *, name: str, minimum: int = 16) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    if result % 2:
        raise ValueError(f"{name} must be even for the Kress log rule.")
    return int(result)


def _material_wavenumbers(
    spec: MaterialSpec, angular_frequencies: np.ndarray, *, eps0: float, mu0: float
) -> np.ndarray:
    """Complex wavenumbers under the shared problem definition.

    The material model is deliberately imported from ``gpr_bem_ref`` rather
    than re-derived: it is part of the problem statement both the oracle and
    the solvers under test agree on, not part of the numerics being judged.
    """

    from gpr_bem_ref import Material

    material = Material(epsr=spec.epsr, sigma=spec.sigma, mur=spec.mur)
    return np.asarray(
        [
            material.wavenumber(float(angular_frequency), eps0, mu0)
            for angular_frequency in angular_frequencies
        ],
        dtype=np.complex128,
    )


@dataclass(frozen=True)
class NystromObservations:
    """Paired complex scattered fields and the oracle's own diagnostics."""

    scattered_response: np.ndarray
    num_nodes: int
    wavenumbers_exterior: np.ndarray
    wavenumbers_interior: np.ndarray
    linear_system_relative_residuals: np.ndarray
    incident_consistencies: np.ndarray
    total_seconds: float

    def __post_init__(self) -> None:
        scattered = np.asarray(self.scattered_response, dtype=np.complex128)
        if scattered.ndim != 2 or scattered.shape[0] < 1 or scattered.shape[1] < 1:
            raise ValueError(
                "scattered_response must have non-empty shape "
                "(num_pairs, num_frequencies)."
            )
        if not np.all(np.isfinite(scattered)):
            raise ValueError("scattered_response must contain only finite values.")
        num_frequencies = scattered.shape[1]
        for name in (
            "linear_system_relative_residuals",
            "incident_consistencies",
        ):
            values = np.asarray(getattr(self, name), dtype=np.float64)
            if values.shape != (num_frequencies,):
                raise ValueError(f"{name} must have shape (num_frequencies,).")
            if not np.all(np.isfinite(values)) or np.any(values < 0.0):
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, _readonly(values, dtype=np.float64))
        for name in ("wavenumbers_exterior", "wavenumbers_interior"):
            values = np.asarray(getattr(self, name), dtype=np.complex128)
            if values.shape != (num_frequencies,) or not np.all(np.isfinite(values)):
                raise ValueError(
                    f"{name} must contain one finite wavenumber per frequency."
                )
            object.__setattr__(self, name, _readonly(values, dtype=np.complex128))
        seconds = float(self.total_seconds)
        if not math.isfinite(seconds) or seconds < 0.0:
            raise ValueError("total_seconds must be finite and non-negative.")
        object.__setattr__(
            self, "scattered_response", _readonly(scattered, dtype=np.complex128)
        )
        object.__setattr__(
            self, "num_nodes", _even_node_count(self.num_nodes, name="num_nodes")
        )
        object.__setattr__(self, "total_seconds", seconds)

    @property
    def maximum_linear_system_relative_residual(self) -> float:
        return float(np.max(self.linear_system_relative_residuals))

    @property
    def maximum_incident_consistency(self) -> float:
        return float(np.max(self.incident_consistencies))

    def diagnostics(self) -> dict[str, Any]:
        """Return a JSON-ready record of how well the oracle solved."""

        return {
            "num_nodes": self.num_nodes,
            "maximum_linear_system_relative_residual": (
                self.maximum_linear_system_relative_residual
            ),
            "maximum_incident_consistency": self.maximum_incident_consistency,
            "total_seconds": self.total_seconds,
        }


def nystrom_paired_response(
    problem: PairedForwardProblem,
    parameterization: Parameterization,
    *,
    num_nodes: int = 512,
    curve_name: str = "target",
) -> NystromObservations:
    """Solve the exact target curve with ``nystrom_ref`` and pair the diagonal.

    The oracle is solved once per frequency with unit source strength and then
    scaled by that frequency's complex strength.  The transmission problem is
    linear in the source, so this is exact and keeps the oracle's own API on
    the real-strength path its tests cover.
    """

    if not isinstance(problem, PairedForwardProblem):
        raise TypeError("problem must be a PairedForwardProblem.")
    if not callable(parameterization):
        raise TypeError("parameterization must be callable on an array of parameters.")
    nodes = _even_node_count(num_nodes, name="num_nodes")

    from nystrom_ref import build_curve, solve_transmission

    exterior = _material_wavenumbers(
        problem.exterior,
        problem.angular_frequencies,
        eps0=problem.eps0,
        mu0=problem.mu0,
    )
    interior = _material_wavenumbers(
        problem.interior,
        problem.angular_frequencies,
        eps0=problem.eps0,
        mu0=problem.mu0,
    )

    started = perf_counter()
    curve = build_curve(parameterization, nodes, curve_name)
    columns: list[np.ndarray] = []
    residuals: list[float] = []
    consistencies: list[float] = []
    for index, strength in enumerate(problem.source_strengths):
        solution = solve_transmission(
            curve,
            problem.source_points,
            problem.receiver_points,
            complex(exterior[index]),
            complex(interior[index]),
        )
        scattered = np.asarray(solution.scattered, dtype=np.complex128)
        expected = (problem.num_pairs, problem.num_pairs)
        if scattered.shape != expected:
            raise RuntimeError(
                f"The Nystrom oracle returned {scattered.shape}; expected {expected}."
            )
        if not np.all(np.isfinite(scattered)):
            raise FloatingPointError(
                "The Nystrom oracle returned non-finite scattered fields."
            )
        columns.append(complex(strength) * np.diag(scattered))
        residuals.append(float(solution.relative_residual))
        consistencies.append(float(solution.incident_consistency))

    return NystromObservations(
        scattered_response=np.stack(columns, axis=1),
        num_nodes=nodes,
        wavenumbers_exterior=exterior,
        wavenumbers_interior=interior,
        linear_system_relative_residuals=np.asarray(residuals, dtype=np.float64),
        incident_consistencies=np.asarray(consistencies, dtype=np.float64),
        total_seconds=float(perf_counter() - started),
    )


def nystrom_self_convergence(
    problem: PairedForwardProblem,
    parameterization: Parameterization,
    *,
    num_nodes: int = 512,
    coarse_num_nodes: int | None = None,
    curve_name: str = "target",
) -> dict[str, Any]:
    """Compare the oracle against a coarser solve of the same exact curve.

    A spectrally convergent Nystrom solution on a smooth curve should agree
    with its half-resolution sibling to near machine precision.  When it does
    not, the observations are not trustworthy enough to gate an inverse
    against, and the driver must say so instead of reporting a small inverse
    residual with respect to unresolved data.
    """

    fine_nodes = _even_node_count(num_nodes, name="num_nodes")
    coarse_nodes = _even_node_count(
        fine_nodes // 2 if coarse_num_nodes is None else coarse_num_nodes,
        name="coarse_num_nodes",
    )
    if coarse_nodes >= fine_nodes:
        raise ValueError("coarse_num_nodes must be smaller than num_nodes.")

    fine = nystrom_paired_response(
        problem, parameterization, num_nodes=fine_nodes, curve_name=curve_name
    )
    coarse = nystrom_paired_response(
        problem, parameterization, num_nodes=coarse_nodes, curve_name=curve_name
    )
    difference = np.linalg.norm(
        fine.scattered_response - coarse.scattered_response, axis=0
    )
    reference = np.maximum(
        np.linalg.norm(fine.scattered_response, axis=0), np.finfo(np.float64).tiny
    )
    per_frequency = difference / reference
    return {
        "num_nodes": fine.num_nodes,
        "coarse_num_nodes": coarse.num_nodes,
        "per_frequency_relative_difference": [
            float(value) for value in per_frequency
        ],
        "maximum_relative_difference": float(np.max(per_frequency)),
        "fine": fine.diagnostics(),
        "coarse": coarse.diagnostics(),
    }


__all__ = [
    "NystromObservations",
    "nystrom_paired_response",
    "nystrom_self_convergence",
]
