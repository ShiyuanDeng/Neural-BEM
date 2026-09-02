"""Continuous smooth parameterizations that produce node-based curves."""

from __future__ import annotations

from dataclasses import dataclass
import operator
from typing import TYPE_CHECKING, Callable

import numpy as np

from ._array_utils import readonly_float_array

CurveEvaluator2D = Callable[[np.ndarray], tuple[np.ndarray, ...]]

if TYPE_CHECKING:
    from .curve import PeriodicCurve2D


@dataclass(frozen=True)
class CurveProvenance2D:
    """Origin metadata carried without coupling geometry to an extractor."""

    source_kind: str = "explicit"
    source_identifier: str | None = None
    projection_residual: float | None = None
    fit_residual: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, str) or not self.source_kind.strip():
            raise ValueError("source_kind must be a non-empty string.")
        object.__setattr__(self, "source_kind", self.source_kind.strip())
        if self.source_identifier is not None:
            object.__setattr__(self, "source_identifier", str(self.source_identifier))
        for name in ("projection_residual", "fit_residual"):
            value = getattr(self, name)
            if value is not None:
                numeric = float(value)
                if not np.isfinite(numeric) or numeric < 0.0:
                    raise ValueError(f"{name} must be finite and non-negative when supplied.")
                object.__setattr__(self, name, numeric)


@dataclass(frozen=True)
class CurveEvaluation2D:
    """Positions and available derivatives at arbitrary parameters."""

    parameters: np.ndarray
    points: np.ndarray
    first_derivatives: np.ndarray
    second_derivatives: np.ndarray
    third_derivatives: np.ndarray | None = None

    def __post_init__(self) -> None:
        parameters = readonly_float_array(self.parameters, name="parameters")
        expected_shape = parameters.shape + (2,)
        arrays = {}
        for name in ("points", "first_derivatives", "second_derivatives"):
            value = readonly_float_array(getattr(self, name), name=name)
            if value.shape != expected_shape:
                raise ValueError(f"{name} must have shape parameters.shape + (2,).")
            arrays[name] = value
        third_derivatives = None
        if self.third_derivatives is not None:
            third_derivatives = readonly_float_array(
                self.third_derivatives,
                name="third_derivatives",
            )
            if third_derivatives.shape != expected_shape:
                raise ValueError("third_derivatives must have shape parameters.shape + (2,).")
        object.__setattr__(self, "parameters", parameters)
        for name, value in arrays.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "third_derivatives", third_derivatives)

    @property
    def maximum_derivative_order(self) -> int:
        return 3 if self.third_derivatives is not None else 2


@dataclass(frozen=True)
class PeriodicParameterization2D:
    """Continuous producer for an immutable node-based :class:`PeriodicCurve2D`.

    The evaluator returns ``(x(t), x'(t), x''(t))`` and may additionally
    return ``x'''(t)``.  This object is useful for analytic geometry, fitting,
    validation, off-node evaluation, and changing resolution.  It is not the
    boundary object passed to a BIE assembler; call :meth:`discretize` first.
    """

    component_id: str
    evaluator: CurveEvaluator2D
    name: str = "curve"
    period: float = 2.0 * np.pi
    parameter_origin: float = 0.0
    provenance: CurveProvenance2D = CurveProvenance2D()

    def __post_init__(self) -> None:
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be a non-empty string.")
        if not callable(self.evaluator):
            raise TypeError("evaluator must be callable.")
        if not isinstance(self.provenance, CurveProvenance2D):
            raise TypeError("provenance must be a CurveProvenance2D object.")
        period = float(self.period)
        origin = float(self.parameter_origin)
        if not np.isfinite(period) or period <= 0.0:
            raise ValueError("period must be finite and positive.")
        if not np.isfinite(origin):
            raise ValueError("parameter_origin must be finite.")
        object.__setattr__(self, "component_id", self.component_id.strip())
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "parameter_origin", origin)

    def evaluate(self, parameters, *, wrap: bool = True) -> CurveEvaluation2D:
        """Evaluate geometry, optionally wrapping parameters to one period."""

        if np.iscomplexobj(parameters):
            raise ValueError("parameters must be real-valued.")
        values = np.asarray(parameters, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ValueError("parameters must contain only finite values.")
        if wrap:
            evaluation_parameters = self.parameter_origin + np.mod(
                values - self.parameter_origin,
                self.period,
            )
        else:
            evaluation_parameters = values
        result = self.evaluator(evaluation_parameters)
        if not isinstance(result, tuple) or len(result) not in (3, 4):
            raise TypeError(
                "evaluator must return "
                "(points, first_derivatives, second_derivatives[, third_derivatives])."
            )
        return CurveEvaluation2D(evaluation_parameters, *result)

    def discretize(
        self,
        num_nodes: int,
        *,
        require_even: bool = False,
    ) -> "PeriodicCurve2D":
        """Evaluate one uniform periodic node grid with no repeated endpoint."""

        from .curve import PeriodicCurve2D

        if isinstance(num_nodes, bool):
            raise TypeError("num_nodes must be an integer, not bool.")
        try:
            count = operator.index(num_nodes)
        except TypeError as exc:
            raise TypeError("num_nodes must be an integer.") from exc
        if count < 3:
            raise ValueError("num_nodes must be at least 3.")
        if require_even and count % 2:
            raise ValueError(
                f"Component {self.component_id!r} requires an even number of nodes "
                "for this discretisation."
            )
        step = self.period / count
        parameters = self.parameter_origin + step * np.arange(count, dtype=np.float64)
        evaluation = self.evaluate(parameters, wrap=False)
        return PeriodicCurve2D.from_evaluation(
            component_id=self.component_id,
            name=self.name,
            evaluation=evaluation,
            period=self.period,
            parameter_origin=self.parameter_origin,
            provenance=self.provenance,
        )

    def reversed(self, *, component_id: str | None = None) -> "PeriodicParameterization2D":
        """Return the same geometric curve with reversed parameter direction."""

        original = self

        def evaluator(parameters: np.ndarray) -> tuple[np.ndarray, ...]:
            reflected = 2.0 * original.parameter_origin + original.period - parameters
            evaluated = original.evaluate(reflected, wrap=False)
            values = (
                evaluated.points,
                -evaluated.first_derivatives,
                evaluated.second_derivatives,
            )
            if evaluated.third_derivatives is not None:
                values += (-evaluated.third_derivatives,)
            return values

        return PeriodicParameterization2D(
            component_id=self.component_id if component_id is None else component_id,
            evaluator=evaluator,
            name=self.name,
            period=self.period,
            parameter_origin=self.parameter_origin,
            provenance=self.provenance,
        )

    def with_parameter_shift(
        self,
        shift: float,
        *,
        component_id: str | None = None,
    ) -> "PeriodicParameterization2D":
        """Return an equivalent curve whose canonical phase is shifted."""

        offset = float(shift)
        if not np.isfinite(offset):
            raise ValueError("shift must be finite.")
        original = self

        def evaluator(parameters: np.ndarray) -> tuple[np.ndarray, ...]:
            evaluated = original.evaluate(parameters + offset, wrap=True)
            values = (
                evaluated.points,
                evaluated.first_derivatives,
                evaluated.second_derivatives,
            )
            if evaluated.third_derivatives is not None:
                values += (evaluated.third_derivatives,)
            return values

        return PeriodicParameterization2D(
            component_id=self.component_id if component_id is None else component_id,
            evaluator=evaluator,
            name=self.name,
            period=self.period,
            parameter_origin=self.parameter_origin,
            provenance=self.provenance,
        )
