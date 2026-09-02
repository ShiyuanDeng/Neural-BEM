"""Immutable node-based representation of one smooth periodic component."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._array_utils import cross2d, readonly_float_array
from .parameterization import CurveEvaluation2D, CurveProvenance2D


@dataclass(frozen=True)
class PeriodicCurve2D:
    """One ordered periodic component stored explicitly at ``N`` nodes.

    The authoritative geometry is the parameter grid and its node jets:
    positions, first derivatives, second derivatives, and optional third
    derivatives. Speed, tangent, outward normal, curvature, and ordinary
    arc-length weights are derived and made read-only during construction.

    There is deliberately no hidden continuous evaluator. Off-node evaluation
    and changing ``N`` belong to ``PeriodicParameterization2D``.
    """

    component_id: str
    parameters: np.ndarray
    points: np.ndarray
    first_derivatives: np.ndarray
    second_derivatives: np.ndarray
    third_derivatives: np.ndarray | None = None
    name: str = "curve"
    period: float = 2.0 * np.pi
    parameter_origin: float = 0.0
    provenance: CurveProvenance2D = CurveProvenance2D()
    parameter_step: float = field(init=False)
    speeds: np.ndarray = field(init=False)
    tangents: np.ndarray = field(init=False)
    normals: np.ndarray = field(init=False)
    curvatures: np.ndarray = field(init=False)
    arc_length_weights: np.ndarray = field(init=False)
    signed_area: float = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        if not isinstance(self.provenance, CurveProvenance2D):
            raise TypeError("provenance must be a CurveProvenance2D object.")

        parameters = readonly_float_array(self.parameters, name="parameters", ndim=1)
        count = int(parameters.size)
        if count < 3:
            raise ValueError("A periodic curve needs at least three nodes.")

        node_arrays = {}
        for name in ("points", "first_derivatives", "second_derivatives"):
            value = readonly_float_array(getattr(self, name), name=name, ndim=2)
            if value.shape != (count, 2):
                raise ValueError(f"{name} must have shape (num_nodes, 2).")
            node_arrays[name] = value

        third_derivatives = None
        if self.third_derivatives is not None:
            third_derivatives = readonly_float_array(
                self.third_derivatives,
                name="third_derivatives",
                ndim=2,
            )
            if third_derivatives.shape != (count, 2):
                raise ValueError("third_derivatives must have shape (num_nodes, 2).")

        period = float(self.period)
        parameter_origin = float(self.parameter_origin)
        if not np.isfinite(period) or period <= 0.0:
            raise ValueError("period must be finite and positive.")
        if not np.isfinite(parameter_origin):
            raise ValueError("parameter_origin must be finite.")
        parameter_step = period / count
        expected_parameters = parameter_origin + parameter_step * np.arange(count, dtype=np.float64)
        if not np.allclose(parameters, expected_parameters, rtol=0.0, atol=1.0e-13 * period):
            raise ValueError(
                "parameters must be the canonical uniform periodic grid with no repeated endpoint."
            )

        points = node_arrays["points"]
        first = node_arrays["first_derivatives"]
        second = node_arrays["second_derivatives"]
        speeds_values = np.linalg.norm(first, axis=1)
        if np.any(speeds_values <= 0.0):
            raise ValueError("first_derivatives must define a regular node grid with positive speed.")
        tangents_values = first / speeds_values[:, None]
        normals_values = np.column_stack((tangents_values[:, 1], -tangents_values[:, 0]))
        curvatures_values = cross2d(first, second) / speeds_values**3
        weights_values = parameter_step * speeds_values
        signed_area = 0.5 * parameter_step * float(np.sum(cross2d(points, first)))
        if not np.isfinite(signed_area) or signed_area <= 0.0:
            raise ValueError(
                "Node-based solver geometry must be counterclockwise so normals are outward. "
                "Reverse the continuous parameterization before discretizing."
            )

        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "parameter_origin", parameter_origin)
        object.__setattr__(self, "parameters", parameters)
        for name, value in node_arrays.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "third_derivatives", third_derivatives)
        object.__setattr__(self, "parameter_step", parameter_step)
        object.__setattr__(
            self,
            "speeds",
            readonly_float_array(speeds_values, name="speeds", ndim=1),
        )
        object.__setattr__(
            self,
            "tangents",
            readonly_float_array(tangents_values, name="tangents", ndim=2),
        )
        object.__setattr__(
            self,
            "normals",
            readonly_float_array(normals_values, name="normals", ndim=2),
        )
        object.__setattr__(
            self,
            "curvatures",
            readonly_float_array(curvatures_values, name="curvatures", ndim=1),
        )
        object.__setattr__(
            self,
            "arc_length_weights",
            readonly_float_array(weights_values, name="arc_length_weights", ndim=1),
        )
        object.__setattr__(self, "signed_area", signed_area)

    @classmethod
    def from_evaluation(
        cls,
        *,
        component_id: str,
        name: str,
        evaluation: CurveEvaluation2D,
        period: float,
        parameter_origin: float,
        provenance: CurveProvenance2D,
    ) -> "PeriodicCurve2D":
        """Construct a node curve from one uniform parameterization evaluation."""

        if evaluation.parameters.ndim != 1:
            raise ValueError("Curve discretization requires a one-dimensional parameter grid.")
        return cls(
            component_id=component_id,
            parameters=evaluation.parameters,
            points=evaluation.points,
            first_derivatives=evaluation.first_derivatives,
            second_derivatives=evaluation.second_derivatives,
            third_derivatives=evaluation.third_derivatives,
            name=name,
            period=period,
            parameter_origin=parameter_origin,
            provenance=provenance,
        )

    @property
    def num_nodes(self) -> int:
        return int(self.parameters.size)

    @property
    def perimeter(self) -> float:
        return float(np.sum(self.arc_length_weights))

    @property
    def orientation(self) -> str:
        return "counterclockwise"

    @property
    def maximum_derivative_order(self) -> int:
        return 3 if self.third_derivatives is not None else 2
