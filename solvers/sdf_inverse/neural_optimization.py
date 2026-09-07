"""Alternating black-box shape updates and neural-SDF re-distancing.

``legacy_strict`` preserves the coupled behavior below. The opt-in
``curve_only`` and ``export_only`` policies share exactly the canonical
reconstruction loop without neural vetoes; export is a separate final step.

This explicit-curve control retains numerical derivatives. The separate
``implicit_adjoint`` module now updates MLP weights through a discrete Kress
adjoint and the actual Method-B conversion. This module differentiates the
measured residual in a small, smooth basis
of direct normal displacements of one canonical ordered contour.  An accepted
contour is then distilled into the full MLP with signed-distance supervision
and an Eikonal penalty.

The extracted post-distillation zero set is a representation audit, not the
next optimization state.  A neural fit that moves the zero contour too far or
changes topology is rolled back, while a successful fit cannot inject its
grid/projection error into the next BEM linearisation.  A materially decreasing
canonical step may retain the preceding audited representation after a
transient fit failure, but only while that representation still satisfies the
same explicit drift bound.  This also removes SDF extraction from the many
finite-difference probes in each iteration.

The modal step is regularised, because the measured failure mode without it is
specific: at ``ka`` of order one the highest column of the basis is nearly
null, undamped Gauss-Newton inverts it, and the contour grows a ripple at that
mode while the resolvable content crawls.  Three things prevent it -- a floor
under the Levenberg damping, a curvature prior that prices a mode by ``k**4``,
and a trust region enforced by raising the damping rather than by rescaling a
step whose direction is already wrong.  Acceptance then asks for an Armijo
fraction of the predicted decrease instead of any decrease at all.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
import math
import operator
from time import perf_counter
from types import MappingProxyType
from typing import Callable, Mapping, TYPE_CHECKING

import numpy as np
import torch
from torch import nn

from ordered_boundary import PeriodicCurve2D, PeriodicParameterization2D

from .curve_updates import (
    RadialFourierCurveState,
    apply_normal_mode_update,
    apply_radial_fourier_update,
    fit_radial_fourier_curve_state,
    radial_fourier_displacement_basis,
    radial_fourier_parameterization,
    radial_fourier_state_curve,
    smooth_normal_mode_values,
)
from .geometry import (
    OrderedSDFGeometryConfig,
    OrderedSDFGeometryError,
    build_ordered_sdf_geometry,
)
from .neural import (
    NeuralRedistanceConfig,
    NeuralRedistanceResult,
    SmoothMLPSDF2D,
    redistance_neural_sdf_to_curve,
)
from .optimization import ComplexScatteredData, normalized_complex_residual

if TYPE_CHECKING:
    from .forward import PairedForwardResult


ForwardPredictor = Callable[..., "PairedForwardResult"]
CurveForwardPredictor = Callable[..., "PairedForwardResult"]
ProgressCallback = Callable[["NeuralInverseIteration"], None]


def _positive_integer(value: object, *, name: str, allow_zero: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    minimum = 0 if allow_zero else 1
    if result < minimum:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}.")
    return int(result)


def _finite_positive(value: object, *, name: str, allow_zero: bool = False) -> float:
    result = float(value)
    valid = result >= 0.0 if allow_zero else result > 0.0
    if not math.isfinite(result) or not valid:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}.")
    return result


def normal_mode_count(maximum_mode: int) -> int:
    """Number of real modes ``1, cos(k t), sin(k t)`` through ``maximum_mode``."""

    return 1 + 2 * _positive_integer(maximum_mode, name="maximum_mode")


class SmoothNormalModeUpdate2D(nn.Module):
    """A bounded smooth implicit perturbation around one reference component.

    Angular harmonics are represented by Gaussian-windowed complex
    polynomials.  Unlike a bare ``atan2`` basis, they and their spatial
    gradients remain finite at the reference centre.  If the base field is an
    SDF, a coefficient measured in metres approximates the corresponding
    outward normal displacement near the reference radius.
    """

    claims_signed_distance = False

    def __init__(
        self,
        base_model: nn.Module,
        *,
        center: tuple[float, float] | np.ndarray,
        radius_scale: float,
        maximum_mode: int,
        coefficients: np.ndarray,
    ) -> None:
        super().__init__()
        if not isinstance(base_model, nn.Module):
            raise TypeError("base_model must be a torch.nn.Module.")
        mode = _positive_integer(maximum_mode, name="maximum_mode")
        center_values = np.asarray(center, dtype=np.float64)
        if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
            raise ValueError("center must contain two finite coordinates.")
        scale = _finite_positive(radius_scale, name="radius_scale")
        coefficient_values = np.asarray(coefficients, dtype=np.float64)
        expected = normal_mode_count(mode)
        if coefficient_values.shape != (expected,) or not np.all(
            np.isfinite(coefficient_values)
        ):
            raise ValueError(f"coefficients must have finite shape ({expected},).")

        reference = next(base_model.parameters(), None)
        if reference is None:
            reference = next(base_model.buffers(), None)
        dtype = torch.get_default_dtype() if reference is None else reference.dtype
        device = torch.device("cpu") if reference is None else reference.device
        self.base_model = base_model
        self.register_buffer(
            "center", torch.as_tensor(center_values, dtype=dtype, device=device)
        )
        self.register_buffer(
            "radius_scale", torch.tensor(scale, dtype=dtype, device=device)
        )
        self.register_buffer(
            "coefficients",
            torch.as_tensor(coefficient_values, dtype=dtype, device=device),
        )
        self.maximum_mode = mode

    def mode_values(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor) or points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must be a torch.Tensor with shape (N, 2).")
        delta = (points - self.center.to(dtype=points.dtype)[None, :]) / self.radius_scale.to(
            dtype=points.dtype
        )
        x = delta[:, 0]
        y = delta[:, 1]
        radius_squared = x * x + y * y
        # A radial mode that is one near the reference circle and decays both
        # inward and outward without an angular singularity.
        values = [torch.exp(-0.5 * (radius_squared - 1.0) ** 2)]
        real = torch.ones_like(x)
        imaginary = torch.zeros_like(x)
        for mode in range(1, self.maximum_mode + 1):
            real, imaginary = real * x - imaginary * y, real * y + imaginary * x
            exponent = torch.clamp(
                0.5 * mode * (1.0 - radius_squared), min=-80.0, max=40.0
            )
            envelope = torch.exp(exponent)
            values.extend((real * envelope, imaginary * envelope))
        return torch.stack(values, dim=1)

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        base = self.base_model(points)
        if base.ndim != 2 or base.shape != (points.shape[0], 1):
            raise ValueError("base_model(points) must have shape (N, 1).")
        correction = self.mode_values(points) @ self.coefficients.to(dtype=points.dtype)
        return base - correction[:, None]


@dataclass(frozen=True)
class AlternatingNeuralInverseConfig:
    """Controls for modal data steps followed by neural re-distancing."""

    redistance: NeuralRedistanceConfig
    max_iterations: int = 8
    maximum_mode: int = 6
    finite_difference_step_m: float = 2.0e-4
    minimum_finite_difference_step_m: float = 1.25e-5
    max_stencil_shrinks: int = 4
    # This caps the requested outward-normal displacement evaluated on the
    # canonical curve.  Coefficients and the cap are physical metres; MLP
    # gradient scaling no longer enters the geometry step.
    maximum_modal_field_update_m: float = 2.0e-3
    maximum_redistance_curve_drift_m: float = 1.5e-3
    # Persistent high-mode structure is measured relative to the initially
    # accepted contour, so pre-existing discretisation/fitting residual is not
    # mistaken for artifact growth.
    # ``None`` records the tail without imposing a hard gate.  Radial Fourier
    # order is not the same as normal-displacement order away from a circle: a
    # measured, fully admissible k=2 ellipse step created 0.224 mm of radial
    # >K tail and was rejected by the former 0.2 mm default.  The canonical
    # curve path no longer accumulates MLP-projection ripple, so this is now an
    # explicit opt-in safety limit rather than a convergence default.
    maximum_spectral_tail_growth_m: float | None = None
    # Continuation stages may change ``maximum_mode`` and restart this
    # optimizer.  Supplying the original contour's tail at the active K keeps
    # the growth allowance global instead of silently re-baselining it at
    # every stage.  ``None`` preserves standalone per-run baselining.
    spectral_tail_reference_rms_m: float | None = None
    initial_damping: float = 1.0e-3
    # The measured failure without these four was a growing ripple at the
    # highest available mode: undamped Gauss-Newton inverts the near-null
    # column of an unresolvable harmonic, rescaling an oversized step keeps
    # that direction, and an any-decrease test accepts the result forever.
    minimum_damping: float = 1.0e-6
    curvature_penalty_weight: float = 1.0e-4
    armijo_coefficient: float = 1.0e-4
    max_trust_region_solves: int = 8
    trust_region_refinement_steps: int = 8
    damping_increase: float = 10.0
    damping_decrease: float = 0.3
    max_damping_trials: int = 5
    # The completed full-band progressive-mode run first found an admissible
    # K=3 descent at the sixth halving.  Include that 2**-6 candidate: a cap
    # of five stops one trial before it and can mislabel the stage as blocked
    # by geometry.
    max_backtracks: int = 6
    loss_tolerance: float = 1.0e-12
    relative_loss_change_tolerance: float = 1.0e-4
    geometry_change_tolerance_m: float = 5.0e-5
    eikonal_rms_tolerance: float = 1.5e-1
    consecutive_convergence_iterations: int = 2
    audit_point_count: int = 512
    audit_seed: int = 2718
    # The default preserves the historical general normal-flow API.  The
    # radial option is an exact, gauge-fixed finite-dimensional retraction for
    # star-shaped curve-state inverses; it requires direct curve probes.
    direct_curve_retraction: str = "normal"
    distillation_policy: str = "legacy_strict"
    representation_audit_num_nodes: int = 512
    maximum_representation_audit_num_nodes: int = 2048
    representation_audit_tolerance_m: float = 1.0e-6
    representation_export_drift_tolerance_m: float = 2.0e-4

    def __post_init__(self) -> None:
        if not isinstance(self.redistance, NeuralRedistanceConfig):
            raise TypeError("redistance must be a NeuralRedistanceConfig.")
        if self.distillation_policy not in {"legacy_strict", "curve_only", "export_only"}:
            raise ValueError(
                "distillation_policy must be 'legacy_strict', 'curve_only', or 'export_only'."
            )
        for name in ("representation_audit_num_nodes", "maximum_representation_audit_num_nodes"):
            value = _positive_integer(getattr(self, name), name=name)
            if value < 8 or value % 2:
                raise ValueError(f"{name} must be even and at least eight.")
            object.__setattr__(self, name, value)
        if self.maximum_representation_audit_num_nodes < 2 * self.representation_audit_num_nodes:
            raise ValueError("maximum_representation_audit_num_nodes must allow one audit refinement.")
        object.__setattr__(self, "representation_audit_tolerance_m", _finite_positive(
            self.representation_audit_tolerance_m, name="representation_audit_tolerance_m"
        ))
        object.__setattr__(self, "representation_export_drift_tolerance_m", _finite_positive(
            self.representation_export_drift_tolerance_m,
            name="representation_export_drift_tolerance_m",
        ))
        for name in (
            "max_iterations",
            "maximum_mode",
            "max_damping_trials",
            "consecutive_convergence_iterations",
            "audit_point_count",
        ):
            object.__setattr__(self, name, _positive_integer(getattr(self, name), name=name))
        for name in (
            "max_stencil_shrinks",
            "max_backtracks",
            "max_trust_region_solves",
            "trust_region_refinement_steps",
        ):
            object.__setattr__(
                self, name, _positive_integer(getattr(self, name), name=name, allow_zero=True)
            )
        if isinstance(self.audit_seed, (bool, np.bool_)):
            raise TypeError("audit_seed must be an integer, not bool.")
        object.__setattr__(self, "audit_seed", int(operator.index(self.audit_seed)))
        for name in (
            "finite_difference_step_m",
            "minimum_finite_difference_step_m",
            "maximum_modal_field_update_m",
            "maximum_redistance_curve_drift_m",
            "initial_damping",
            "minimum_damping",
            "relative_loss_change_tolerance",
            "geometry_change_tolerance_m",
            "eikonal_rms_tolerance",
        ):
            object.__setattr__(self, name, _finite_positive(getattr(self, name), name=name))
        object.__setattr__(
            self,
            "loss_tolerance",
            _finite_positive(self.loss_tolerance, name="loss_tolerance", allow_zero=True),
        )
        if self.maximum_spectral_tail_growth_m is not None:
            object.__setattr__(
                self,
                "maximum_spectral_tail_growth_m",
                _finite_positive(
                    self.maximum_spectral_tail_growth_m,
                    name="maximum_spectral_tail_growth_m",
                    allow_zero=True,
                ),
            )
        if self.spectral_tail_reference_rms_m is not None:
            object.__setattr__(
                self,
                "spectral_tail_reference_rms_m",
                _finite_positive(
                    self.spectral_tail_reference_rms_m,
                    name="spectral_tail_reference_rms_m",
                    allow_zero=True,
                ),
            )
        for name in ("curvature_penalty_weight", "armijo_coefficient"):
            object.__setattr__(
                self, name, _finite_positive(getattr(self, name), name=name, allow_zero=True)
            )
        if self.minimum_finite_difference_step_m > self.finite_difference_step_m:
            raise ValueError(
                "minimum_finite_difference_step_m cannot exceed finite_difference_step_m."
            )
        if self.minimum_damping > self.initial_damping:
            raise ValueError("minimum_damping cannot exceed initial_damping.")
        if (
            self.distillation_policy == "legacy_strict"
            and self.redistance.eikonal_rms_tolerance > self.eikonal_rms_tolerance
        ):
            # Otherwise the inner fit is allowed to stop in a field state the
            # outer loop then refuses to call converged, and the run can only
            # ever end at maximum_iterations.
            raise ValueError(
                "redistance.eikonal_rms_tolerance cannot exceed the inverse "
                "eikonal_rms_tolerance."
            )
        if self.armijo_coefficient >= 1.0:
            raise ValueError("armijo_coefficient must be smaller than one.")
        if not math.isfinite(self.damping_increase) or self.damping_increase <= 1.0:
            raise ValueError("damping_increase must be finite and greater than one.")
        if (
            not math.isfinite(self.damping_decrease)
            or self.damping_decrease <= 0.0
            or self.damping_decrease > 1.0
        ):
            raise ValueError("damping_decrease must lie in (0, 1].")
        if self.direct_curve_retraction not in {"normal", "radial_fourier"}:
            raise ValueError(
                "direct_curve_retraction must be 'normal' or 'radial_fourier'."
            )


@dataclass(frozen=True)
class NeuralInverseIteration:
    """One accepted canonical contour; iteration zero is the initialized state."""

    iteration: int
    loss: float
    relative_l2_error: float
    geometry_points: np.ndarray
    modal_step: np.ndarray
    applied_damping: float
    maximum_modal_field_update_m: float
    curve_change_m: float
    redistance_curve_drift_m: float | None
    eikonal_rms: float | None
    eikonal_maximum_deviation: float | None
    maximum_curve_field_residual: float | None
    redistance_steps: int
    redistance_stop_reason: str
    evaluation_count: int
    maximum_system_residual: float
    timings: Mapping[str, float]
    trust_region_predicted_relative_change: float = 0.0
    radial_spectral_tail_rms_m: float = 0.0
    radial_spectral_tail_limit_m: float | None = None
    spectral_tail_rejection_count: int = 0
    accepted_step_predicted_relative_change: float = 0.0
    accepted_backtrack_count: int = 0
    arclength_refit_rms_m: float = 0.0
    arclength_refit_maximum_m: float = 0.0
    arclength_speed_ratio_before: float = 1.0
    arclength_speed_ratio_after: float = 1.0
    representation_evaluated: bool = True

    def __post_init__(self) -> None:
        points = np.array(self.geometry_points, dtype=np.float64, copy=True)
        step = np.array(self.modal_step, dtype=np.float64, copy=True)
        if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
            raise ValueError("geometry_points must have finite shape (N, 2).")
        if step.ndim != 1 or not np.all(np.isfinite(step)):
            raise ValueError("modal_step must be a finite vector.")
        points.setflags(write=False)
        step.setflags(write=False)
        timings = {str(key): float(value) for key, value in self.timings.items()}
        if not all(math.isfinite(value) and value >= 0.0 for value in timings.values()):
            raise ValueError("timings must contain finite non-negative values.")
        for name in (
            "loss",
            "relative_l2_error",
            "applied_damping",
            "maximum_modal_field_update_m",
            "curve_change_m",
            "maximum_system_residual",
            "trust_region_predicted_relative_change",
            "accepted_step_predicted_relative_change",
            "radial_spectral_tail_rms_m",
            "arclength_refit_rms_m",
            "arclength_refit_maximum_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        if not isinstance(self.representation_evaluated, (bool, np.bool_)):
            raise TypeError("representation_evaluated must be bool.")
        for name in (
            "redistance_curve_drift_m", "eikonal_rms",
            "eikonal_maximum_deviation", "maximum_curve_field_residual",
        ):
            value = getattr(self, name)
            if not self.representation_evaluated:
                if value is not None:
                    raise ValueError(f"{name} must be None when representation was not evaluated.")
            elif value is None:
                raise ValueError(f"{name} is required when representation was evaluated.")
            else:
                object.__setattr__(
                    self, name, _finite_positive(value, name=name, allow_zero=True)
                )
        if self.radial_spectral_tail_limit_m is not None:
            tail_limit = float(self.radial_spectral_tail_limit_m)
            if not math.isfinite(tail_limit) or tail_limit < 0.0:
                raise ValueError(
                    "radial_spectral_tail_limit_m must be finite and non-negative "
                    "when supplied."
                )
            object.__setattr__(self, "radial_spectral_tail_limit_m", tail_limit)
        for name in (
            "arclength_speed_ratio_before",
            "arclength_speed_ratio_after",
        ):
            speed_ratio = float(getattr(self, name))
            if not math.isfinite(speed_ratio) or speed_ratio < 1.0:
                raise ValueError(f"{name} must be finite and at least one.")
            object.__setattr__(self, name, speed_ratio)
        object.__setattr__(
            self, "iteration", _positive_integer(self.iteration, name="iteration", allow_zero=True)
        )
        object.__setattr__(
            self,
            "redistance_steps",
            _positive_integer(self.redistance_steps, name="redistance_steps", allow_zero=True),
        )
        object.__setattr__(
            self,
            "evaluation_count",
            _positive_integer(self.evaluation_count, name="evaluation_count", allow_zero=True),
        )
        object.__setattr__(
            self,
            "spectral_tail_rejection_count",
            _positive_integer(
                self.spectral_tail_rejection_count,
                name="spectral_tail_rejection_count",
                allow_zero=True,
            ),
        )
        object.__setattr__(
            self,
            "accepted_backtrack_count",
            _positive_integer(
                self.accepted_backtrack_count,
                name="accepted_backtrack_count",
                allow_zero=True,
            ),
        )
        if not isinstance(self.redistance_stop_reason, str) or not self.redistance_stop_reason:
            raise ValueError("redistance_stop_reason must be non-empty.")
        object.__setattr__(self, "geometry_points", points)
        object.__setattr__(self, "modal_step", step)
        object.__setattr__(self, "timings", MappingProxyType(timings))


@dataclass(frozen=True)
class AlternatingNeuralInverseResult:
    solver: str
    iterations: tuple[NeuralInverseIteration, ...]
    converged: bool
    stop_reason: str
    total_evaluation_count: int
    infeasible_evaluation_count: int
    maximum_system_residual: float
    total_forward_seconds: float
    total_redistance_seconds: float
    total_seconds: float
    final_curve: "PeriodicCurve2D"
    final_representation_curve: "PeriodicCurve2D | None"
    total_geometry_audit_seconds: float = 0.0
    total_bem_seconds: float = 0.0
    total_curve_update_seconds: float = 0.0
    redistance_attempt_count: int = 0
    total_redistance_step_count: int = 0
    spectral_tail_rejection_count: int = 0
    full_validation_rejection_count: int = 0
    redistance_failure_count: int = 0
    representation_extraction_failure_count: int = 0
    representation_drift_rejection_count: int = 0
    final_radial_curve_state: RadialFourierCurveState | None = None
    distillation_policy: str = "legacy_strict"
    reconstruction_converged: bool | None = None
    reconstruction_stop_reason: str | None = None
    representation_status: str = "evaluated"
    representation_stop_reason: str | None = None
    representation_evaluated: bool = True
    reconstruction_seconds: float | None = None
    export_seconds: float = 0.0
    export_result: "NeuralSDFExportResult | None" = None
    schema_version: int = 2

    def __post_init__(self) -> None:
        if self.solver not in {"mod", "kress"}:
            raise ValueError("solver must be exactly 'mod' or 'kress'.")
        records = tuple(self.iterations)
        if not records or any(
            not isinstance(item, NeuralInverseIteration) for item in records
        ):
            raise ValueError(
                "iterations must contain at least one NeuralInverseIteration."
            )
        expected_indices = tuple(range(len(records)))
        if tuple(item.iteration for item in records) != expected_indices:
            raise ValueError("iteration indices must be consecutive from zero.")
        if any(
            later.loss >= earlier.loss
            for earlier, later in zip(records, records[1:])
        ):
            raise ValueError("accepted iteration losses must decrease strictly.")
        if not isinstance(self.converged, (bool, np.bool_)):
            raise TypeError("converged must be bool.")
        object.__setattr__(self, "converged", bool(self.converged))
        if not isinstance(self.stop_reason, str) or not self.stop_reason:
            raise ValueError("stop_reason must be non-empty.")
        for name in (
            "total_evaluation_count",
            "infeasible_evaluation_count",
            "redistance_attempt_count",
            "total_redistance_step_count",
            "full_validation_rejection_count",
            "redistance_failure_count",
            "representation_extraction_failure_count",
            "representation_drift_rejection_count",
            "spectral_tail_rejection_count",
        ):
            object.__setattr__(
                self,
                name,
                _positive_integer(getattr(self, name), name=name, allow_zero=True),
            )
        if self.total_evaluation_count < records[-1].evaluation_count:
            raise ValueError(
                "total_evaluation_count cannot precede the final iteration count."
            )
        if self.infeasible_evaluation_count > self.total_evaluation_count:
            raise ValueError(
                "infeasible_evaluation_count cannot exceed total_evaluation_count."
            )
        post_redistance_rejections = (
            self.redistance_failure_count
            + self.representation_extraction_failure_count
            + self.representation_drift_rejection_count
        )
        if post_redistance_rejections > self.redistance_attempt_count:
            raise ValueError(
                "post-redistance rejection counts cannot exceed "
                "redistance_attempt_count."
            )
        for name in (
            "maximum_system_residual",
            "total_forward_seconds",
            "total_redistance_seconds",
            "total_geometry_audit_seconds",
            "total_bem_seconds",
            "total_curve_update_seconds",
            "total_seconds",
        ):
            object.__setattr__(
                self,
                name,
                _finite_positive(getattr(self, name), name=name, allow_zero=True),
            )
        if not isinstance(self.final_curve, PeriodicCurve2D):
            raise TypeError("final_curve must be a PeriodicCurve2D.")
        if self.final_representation_curve is not None and not isinstance(
            self.final_representation_curve, PeriodicCurve2D
        ):
            raise TypeError("final_representation_curve must be a PeriodicCurve2D or None.")
        if self.distillation_policy not in {"legacy_strict", "curve_only", "export_only"}:
            raise ValueError("Unsupported distillation_policy.")
        if self.distillation_policy == "legacy_strict" and self.final_representation_curve is None:
            raise ValueError("legacy_strict requires the audited representation curve.")
        if not isinstance(self.representation_evaluated, (bool, np.bool_)):
            raise TypeError("representation_evaluated must be bool.")
        if self.representation_status not in {"evaluated", "passed", "failed", "not_requested", "not_evaluated"}:
            raise ValueError("Unsupported representation_status.")
        reconstruction_converged = (
            self.converged if self.reconstruction_converged is None
            else self.reconstruction_converged
        )
        if not isinstance(reconstruction_converged, (bool, np.bool_)):
            raise TypeError("reconstruction_converged must be bool.")
        object.__setattr__(self, "reconstruction_converged", bool(reconstruction_converged))
        object.__setattr__(self, "reconstruction_stop_reason", self.reconstruction_stop_reason or self.stop_reason)
        object.__setattr__(self, "representation_stop_reason", self.representation_stop_reason or self.stop_reason)
        object.__setattr__(self, "reconstruction_seconds", _finite_positive(
            self.total_seconds if self.reconstruction_seconds is None else self.reconstruction_seconds,
            name="reconstruction_seconds", allow_zero=True,
        ))
        object.__setattr__(self, "export_seconds", _finite_positive(
            self.export_seconds, name="export_seconds", allow_zero=True,
        ))
        if self.final_radial_curve_state is not None and not isinstance(
            self.final_radial_curve_state, RadialFourierCurveState
        ):
            raise TypeError(
                "final_radial_curve_state must be a RadialFourierCurveState when supplied."
            )
        if not np.array_equal(records[-1].geometry_points, self.final_curve.points):
            raise ValueError(
                "final iteration geometry_points must equal final_curve.points."
            )
        object.__setattr__(self, "iterations", records)

    @property
    def initial_iteration(self) -> NeuralInverseIteration:
        return self.iterations[0]

    @property
    def final_iteration(self) -> NeuralInverseIteration:
        return self.iterations[-1]

    @property
    def requested_delivery_complete(self) -> bool:
        """Keep legacy success intact; an explicitly requested export must pass."""

        if self.distillation_policy == "legacy_strict":
            return self.converged
        return bool(self.reconstruction_converged and (
            self.distillation_policy == "curve_only" or self.representation_status == "passed"
        ))

    @property
    def canonical_relative_l2_error(self) -> float:
        return self.final_iteration.relative_l2_error

    @property
    def representation_relative_l2_error(self) -> float | None:
        return None if self.export_result is None else self.export_result.relative_l2_error


@dataclass(frozen=True)
class _Evaluation:
    coefficients: np.ndarray
    residual: np.ndarray
    loss: float
    relative_l2_error: float
    forward_result: "PairedForwardResult"
    wall_seconds: float


@dataclass(frozen=True)
class _RetainedRepresentationCandidate:
    """A valid canonical descent paired with the last audited MLP contour.

    Production probes depend only on the canonical ordered curve.  If a
    transient neural re-distancing attempt fails, that curve can therefore
    remain a coherent candidate provided the *previous* representation still
    lies inside the same explicit drift gate.  Keeping the complete candidate
    here lets the line search continue looking for a freshly distilled state
    first; this fallback is considered only after every such attempt fails.
    """

    forward_result: "PairedForwardResult"
    loss: float
    relative_l2_error: float
    curve: PeriodicCurve2D
    modal_step: np.ndarray
    trust_region_predicted_change: float
    step_predicted_change: float
    backtrack_count: int
    fit: NeuralRedistanceResult | None
    damping: float
    retained_representation_drift_m: float
    spectral_tail_rms_m: float
    arclength_refit_rms_m: float
    arclength_refit_maximum_m: float
    arclength_speed_ratio_before: float
    arclength_speed_ratio_after: float
    redistance_stop_reason: str = ""


class _ModalEvaluator:
    def __init__(
        self,
        model: nn.Module,
        curve: PeriodicCurve2D,
        data: ComplexScatteredData,
        geometry_config: OrderedSDFGeometryConfig,
        solver: str,
        center: np.ndarray,
        radius_scale: float,
        maximum_mode: int,
        predictor: ForwardPredictor,
        base_forward: "PairedForwardResult",
        *,
        direct_curve_probes: bool,
        direct_curve_retraction: str = "normal",
        radial_curve_state: RadialFourierCurveState | None = None,
    ) -> None:
        self.model = model
        self.curve = curve
        self.data = data
        self.geometry_config = geometry_config
        self.solver = solver
        self.center = center
        self.radius_scale = radius_scale
        self.maximum_mode = maximum_mode
        self.predictor = predictor
        self.direct_curve_probes = bool(direct_curve_probes)
        self.direct_curve_retraction = str(direct_curve_retraction)
        self.radial_curve_state = radial_curve_state
        if self.direct_curve_retraction not in {"normal", "radial_fourier"}:
            raise ValueError("Unsupported direct curve retraction.")
        if self.direct_curve_retraction == "radial_fourier":
            if not self.direct_curve_probes:
                raise ValueError("Radial Fourier retraction requires direct curve probes.")
            if not isinstance(self.radial_curve_state, RadialFourierCurveState):
                raise TypeError(
                    "radial_curve_state is required for radial Fourier retraction."
                )
            if self.maximum_mode > self.radial_curve_state.maximum_mode:
                raise ValueError(
                    "maximum_mode cannot exceed radial_curve_state.maximum_mode."
                )
        elif self.radial_curve_state is not None:
            raise ValueError(
                "radial_curve_state is only valid with radial Fourier retraction."
            )
        self.cache: dict[bytes, _Evaluation | OrderedSDFGeometryError] = {}
        self.evaluation_count = 0
        self.infeasible_count = 0
        self.forward_seconds = 0.0
        self.bem_seconds = 0.0
        self.curve_update_seconds = 0.0
        self.maximum_system_residual = _maximum_system_residual(base_forward)
        zeros = np.zeros(normal_mode_count(maximum_mode), dtype=np.float64)
        self.cache[self._key(zeros)] = self._from_forward(zeros, base_forward, 0.0)

    @staticmethod
    def _key(coefficients: np.ndarray) -> bytes:
        return np.ascontiguousarray(coefficients, dtype=np.float64).tobytes()

    def _from_forward(
        self, coefficients: np.ndarray, forward_result: "PairedForwardResult", wall: float
    ) -> _Evaluation:
        residual, relative = normalized_complex_residual(
            forward_result.scattered_response,
            self.data.observed_scattered_response,
            self.data.frequency_weights,
        )
        return _Evaluation(
            coefficients=np.array(coefficients, dtype=np.float64, copy=True),
            residual=residual,
            loss=0.5 * float(np.dot(residual, residual)),
            relative_l2_error=relative,
            forward_result=forward_result,
            wall_seconds=wall,
        )

    def evaluate(self, coefficients: np.ndarray) -> _Evaluation:
        values = np.asarray(coefficients, dtype=np.float64)
        expected = normal_mode_count(self.maximum_mode)
        if values.shape != (expected,) or not np.all(np.isfinite(values)):
            raise ValueError(f"coefficients must have finite shape ({expected},).")
        key = self._key(values)
        cached = self.cache.get(key)
        if isinstance(cached, OrderedSDFGeometryError):
            raise cached
        if cached is not None:
            return cached
        started = perf_counter()
        self.evaluation_count += 1
        curve_update_elapsed = 0.0
        try:
            curve_update_started = perf_counter()
            if self.direct_curve_probes:
                if self.direct_curve_retraction == "radial_fourier":
                    assert self.radial_curve_state is not None
                    update = apply_radial_fourier_update(
                        self.radial_curve_state,
                        values,
                        maximum_mode=self.maximum_mode,
                        geometry_config=self.geometry_config,
                        full_validation=False,
                    )
                else:
                    update = apply_normal_mode_update(
                        self.curve,
                        values,
                        center=self.center,
                        radius_scale=self.radius_scale,
                        maximum_mode=self.maximum_mode,
                        geometry_config=self.geometry_config,
                        full_validation=False,
                    )
                trial = update.curve
            else:
                # Compatibility seam for tests and external callers that
                # supplied only a model-based predictor.  Production uses the
                # direct ordered-curve path above, so no SDF extraction occurs
                # in its finite-difference stencil.
                trial = SmoothNormalModeUpdate2D(
                    self.model,
                    center=self.center,
                    radius_scale=self.radius_scale,
                    maximum_mode=self.maximum_mode,
                    coefficients=values,
                )
                trial.eval()
            curve_update_elapsed = float(perf_counter() - curve_update_started)
            forward = self.predictor(
                trial, self.data.forward_problem, self.geometry_config, solver=self.solver
            )
            if self.direct_curve_probes:
                returned_points = np.asarray(
                    forward.geometry_build.curve.points, dtype=np.float64
                )
                if not np.array_equal(returned_points, trial.points):
                    raise RuntimeError(
                        "curve_forward_predictor must solve the supplied ordered curve."
                    )
        except OrderedSDFGeometryError as exc:
            wall = float(perf_counter() - started)
            self.infeasible_count += 1
            self.forward_seconds += wall
            self.curve_update_seconds += (
                curve_update_elapsed if curve_update_elapsed > 0.0 else wall
            )
            self.cache[key] = exc
            raise
        wall = float(perf_counter() - started)
        evaluation = self._from_forward(values, forward, wall)
        self.cache[key] = evaluation
        self.forward_seconds += wall
        self.curve_update_seconds += curve_update_elapsed
        reported_bem_seconds = getattr(
            forward,
            "forward_seconds",
            max(wall - curve_update_elapsed, 0.0),
        )
        self.bem_seconds += _finite_positive(
            reported_bem_seconds, name="forward.forward_seconds", allow_zero=True
        )
        self.maximum_system_residual = max(
            self.maximum_system_residual, _maximum_system_residual(forward)
        )
        return evaluation


def _modal_jacobian(
    evaluator: _ModalEvaluator,
    base: _Evaluation,
    config: AlternatingNeuralInverseConfig,
) -> tuple[np.ndarray, np.ndarray]:
    count = normal_mode_count(config.maximum_mode)
    jacobian = np.empty((base.residual.size, count), dtype=np.float64)
    used_steps = np.empty(count, dtype=np.float64)
    origin = np.zeros(count, dtype=np.float64)
    for index in range(count):
        step = config.finite_difference_step_m
        central = None
        for _ in range(config.max_stencil_shrinks + 1):
            if step < config.minimum_finite_difference_step_m:
                break
            plus = origin.copy()
            minus = origin.copy()
            plus[index] = step
            minus[index] = -step
            try:
                plus_value = evaluator.evaluate(plus)
                minus_value = evaluator.evaluate(minus)
            except OrderedSDFGeometryError:
                step *= 0.5
                continue
            central = (plus_value, minus_value)
            break
        if central is None:
            # A second-order one-sided stencil is still a derivative of the
            # actual feasible map.  If neither side supplies it, topology is a
            # barrier and the outer iteration must stop explicitly.
            for sign in (1.0, -1.0):
                probe_step = max(step, config.minimum_finite_difference_step_m)
                first_parameters = origin.copy()
                second_parameters = origin.copy()
                first_parameters[index] = sign * probe_step
                second_parameters[index] = sign * 2.0 * probe_step
                try:
                    first = evaluator.evaluate(first_parameters)
                    second = evaluator.evaluate(second_parameters)
                except OrderedSDFGeometryError:
                    continue
                jacobian[:, index] = sign * (
                    -3.0 * base.residual + 4.0 * first.residual - second.residual
                ) / (2.0 * probe_step)
                used_steps[index] = probe_step
                break
            else:
                raise OrderedSDFGeometryError(
                    f"No feasible finite-difference stencil for normal mode {index}."
                )
        else:
            plus_value, minus_value = central
            jacobian[:, index] = (
                plus_value.residual - minus_value.residual
            ) / (2.0 * step)
            used_steps[index] = step
    return jacobian, used_steps


def resolvable_maximum_mode(
    wavenumber: float, radius: float, *, maximum: int = 12
) -> int:
    """Highest angular harmonic a measurement at ``wavenumber`` can still see.

    A boundary harmonic of order ``n`` on a scatterer of radius ``a`` radiates
    as an order-``n`` multipole, whose exterior coupling collapses once ``n``
    passes ``ka``.  This uses the localisation form ``ka + (ka)**(1/3)`` -- the
    shape of the Wiscombe multipole truncation with a deliberately small
    coefficient.  It is a reporting heuristic for choosing a basis size, not a
    theorem about which modes are recoverable.
    """

    ka = _finite_positive(wavenumber, name="wavenumber") * _finite_positive(
        radius, name="radius"
    )
    limit = _positive_integer(maximum, name="maximum")
    return int(min(max(math.ceil(ka + ka ** (1.0 / 3.0)), 1), limit))


def _mode_orders(maximum_mode: int) -> np.ndarray:
    """Angular order of each real mode, ``0, 1, 1, 2, 2, ...``."""

    orders = [0]
    for mode in range(1, _positive_integer(maximum_mode, name="maximum_mode") + 1):
        orders.extend((mode, mode))
    return np.asarray(orders, dtype=np.float64)


def _curvature_penalty(
    normal_matrix: np.ndarray, config: AlternatingNeuralInverseConfig
) -> np.ndarray:
    """Tikhonov weights that price a mode by its bending energy.

    ``k**4`` is the curvature seminorm of a radial harmonic, referred here to
    the best-determined column of the normal matrix so the prior is invariant
    to the units and the overall scale of the residual.  Modes the data cannot
    resolve are then bought at their smoothness cost instead of for free.
    """

    if config.direct_curve_retraction == "radial_fourier":
        # Gauge-fixed ordering: mean radius, x/y translation, then radial
        # harmonics 2..K.  Rigid translations and uniform dilation carry no
        # bending penalty.
        orders = np.asarray(
            [0.0, 0.0, 0.0]
            + [float(mode) for mode in range(2, config.maximum_mode + 1) for _ in range(2)],
            dtype=np.float64,
        )
    else:
        orders = _mode_orders(config.maximum_mode)
    if config.curvature_penalty_weight == 0.0:
        return np.zeros_like(orders)
    reference = float(np.max(np.diag(normal_matrix)))
    if not math.isfinite(reference) or reference <= 0.0:
        reference = 1.0
    return config.curvature_penalty_weight * reference * orders**4


def _mode_values_at_curve(
    model: nn.Module,
    points: np.ndarray,
    center: np.ndarray,
    radius_scale: float,
    maximum_mode: int,
) -> np.ndarray:
    """Modal basis sampled on the current curve, shape ``(nodes, modes)``."""
    del model  # Kept in the private signature for compatibility with callers.
    return smooth_normal_mode_values(
        points,
        center=center,
        radius_scale=radius_scale,
        maximum_mode=maximum_mode,
    )


def _bounded_modal_step(
    normal_matrix: np.ndarray,
    gradient: np.ndarray,
    scaling: np.ndarray,
    curvature: np.ndarray,
    basis_at_curve: np.ndarray,
    damping: float,
    config: AlternatingNeuralInverseConfig,
) -> tuple[np.ndarray, float] | None:
    """A Levenberg step inside the field-update trust region, or ``None``.

    Rescaling an oversized step preserves its direction, so a step dominated
    by an unresolvable mode stays dominated by it while the resolvable content
    is divided away.  Raising the damping instead shortens the step *and*
    rotates it toward steepest descent, which is what the region is for; the
    rescale survives only as the fallback once the damping search is spent.
    """

    trial = float(damping)
    attempted = trial
    step = None
    maximum = math.inf
    infeasible_damping: float | None = None
    for _ in range(config.max_trust_region_solves + 1):
        try:
            step = np.linalg.solve(
                normal_matrix + trial * np.diag(scaling) + np.diag(curvature), -gradient
            )
        except np.linalg.LinAlgError:
            return None
        if not np.all(np.isfinite(step)):
            return None
        maximum = _maximum_modal_displacement(basis_at_curve, step)
        if not math.isfinite(maximum):
            return None
        if maximum <= config.maximum_modal_field_update_m:
            if infeasible_damping is None:
                return step, trial

            # The decade search only brackets the useful damping.  Returning
            # its first feasible endpoint can waste almost the entire trust
            # region (the measured ellipse probe used 0.49 mm of an available
            # 4 mm).  Refine in log(lambda), retaining the smallest known
            # feasible damping and therefore the least over-damped direction.
            feasible_damping = trial
            feasible_step = step
            for _ in range(config.trust_region_refinement_steps):
                midpoint = math.sqrt(infeasible_damping * feasible_damping)
                try:
                    midpoint_step = np.linalg.solve(
                        normal_matrix
                        + midpoint * np.diag(scaling)
                        + np.diag(curvature),
                        -gradient,
                    )
                except np.linalg.LinAlgError:
                    break
                if not np.all(np.isfinite(midpoint_step)):
                    break
                midpoint_maximum = _maximum_modal_displacement(
                    basis_at_curve, midpoint_step
                )
                if not math.isfinite(midpoint_maximum):
                    break
                if midpoint_maximum <= config.maximum_modal_field_update_m:
                    feasible_damping = midpoint
                    feasible_step = midpoint_step
                else:
                    infeasible_damping = midpoint
            return feasible_step, feasible_damping
        infeasible_damping = trial
        attempted = trial
        trial *= config.damping_increase
    if maximum <= 0.0:
        return step, attempted
    return step * (config.maximum_modal_field_update_m / maximum), attempted


def _maximum_modal_displacement(
    basis_at_curve: np.ndarray, coefficients: np.ndarray
) -> float:
    """Largest scalar-normal or vector-chart displacement represented by a step."""

    basis = np.asarray(basis_at_curve, dtype=np.float64)
    step = np.asarray(coefficients, dtype=np.float64)
    if basis.ndim == 2:
        if basis.shape[1] != step.size:
            raise ValueError("basis and coefficient counts must match.")
        return float(np.max(np.abs(basis @ step)))
    if basis.ndim == 3 and basis.shape[2] == 2:
        if basis.shape[1] != step.size:
            raise ValueError("basis and coefficient counts must match.")
        displacement = np.einsum("npd,p->nd", basis, step)
        return float(np.max(np.linalg.norm(displacement, axis=1)))
    raise ValueError("basis_at_curve must have shape (N, P) or (N, P, 2).")


def _sufficient_decrease(
    loss: float,
    current_loss: float,
    predicted_change: float,
    config: AlternatingNeuralInverseConfig,
) -> bool:
    """Armijo test against the linear model's own predicted decrease.

    A plain ``loss < current_loss`` accepts a step that realises an
    arbitrarily small fraction of what its direction promised, which is how a
    data-invisible ripple survives cycle after cycle.
    """

    if not loss < current_loss:
        return False
    if not math.isfinite(predicted_change) or predicted_change >= 0.0:
        return True
    return loss <= current_loss + config.armijo_coefficient * predicted_change


def _curve_center_and_scale(points: np.ndarray) -> tuple[np.ndarray, float]:
    center = np.mean(points, axis=0)
    radii = np.linalg.norm(points - center[None, :], axis=1)
    scale = float(np.mean(radii))
    if not np.all(np.isfinite(center)) or not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("Current curve has no finite positive radial scale.")
    return center, scale


def radial_spectral_tail_rms(points: np.ndarray, maximum_mode: int) -> float:
    """RMS radial content not represented by angular modes ``0..K``.

    Radii and polar angles are formed about the curve's own mean center, which
    makes the diagnostic translation invariant.  A deterministic least-
    squares fit removes the mean radius and both real harmonics at each mode
    through ``maximum_mode``; its residual is the total unresolved tail in
    metres, without allowing artifacts from earlier iterations to become a
    free incremental update in the next one.
    """

    values = np.asarray(points, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 3 or values.shape[1] != 2:
        raise ValueError("points must have shape (N, 2), N >= 3.")
    if not np.all(np.isfinite(values)):
        raise ValueError("points must contain only finite coordinates.")
    mode = _positive_integer(maximum_mode, name="maximum_mode")
    column_count = normal_mode_count(mode)
    if values.shape[0] <= column_count:
        raise ValueError(
            "points must outnumber the fitted radial spectral coefficients."
        )

    center = np.mean(values, axis=0)
    delta = values - center[None, :]
    radii = np.linalg.norm(delta, axis=1)
    if np.any(radii <= 64.0 * np.finfo(float).eps):
        raise ValueError("points must define nonzero radii about their mean center.")
    angles = np.arctan2(delta[:, 1], delta[:, 0])
    columns = [np.ones(values.shape[0], dtype=np.float64)]
    for order in range(1, mode + 1):
        columns.extend((np.cos(order * angles), np.sin(order * angles)))
    design = np.column_stack(columns)
    coefficients, _, _, _ = np.linalg.lstsq(design, radii, rcond=None)
    residual = radii - design @ coefficients
    return float(np.sqrt(np.mean(residual * residual)))


def _radial_spectral_tail_rms(points: np.ndarray, maximum_mode: int) -> float:
    """Backward-compatible private alias for :func:`radial_spectral_tail_rms`."""

    return radial_spectral_tail_rms(points, maximum_mode)


def _maximum_point_to_closed_polygon_distance(
    query_points: np.ndarray, polygon_points: np.ndarray
) -> float:
    """Maximum distance from query nodes to the closed polygon's segments.

    Comparing only curve nodes gives a false motion of order one node spacing
    when contour extraction chooses a different periodic phase.  Segment
    projection measures the represented geometric set instead.  The chunking
    keeps the temporary pairwise arrays bounded for unusually dense curves.
    """

    query = np.asarray(query_points, dtype=np.float64)
    polygon = np.asarray(polygon_points, dtype=np.float64)
    for name, values in (("query_points", query), ("polygon_points", polygon)):
        if values.ndim != 2 or values.shape[0] < 3 or values.shape[1] != 2:
            raise ValueError(f"{name} must have shape (N, 2), N >= 3.")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} must contain only finite coordinates.")

    starts = polygon
    edges = np.roll(polygon, -1, axis=0) - polygon
    squared_lengths = np.sum(edges * edges, axis=1)
    scale = max(float(np.max(np.ptp(polygon, axis=0))), 1.0)
    if np.any(squared_lengths <= (64.0 * np.finfo(float).eps * scale) ** 2):
        raise ValueError("polygon_points contains a zero-length edge.")

    # Keep displacement/closest arrays to roughly 32 MiB each or less.
    chunk_size = max(1, min(query.shape[0], 2_000_000 // polygon.shape[0]))
    maximum_squared = 0.0
    for first in range(0, query.shape[0], chunk_size):
        values = query[first : first + chunk_size]
        displacement = values[:, None, :] - starts[None, :, :]
        fractions = np.sum(displacement * edges[None, :, :], axis=2)
        fractions /= squared_lengths[None, :]
        np.clip(fractions, 0.0, 1.0, out=fractions)
        closest = starts[None, :, :] + fractions[:, :, None] * edges[None, :, :]
        minimum_squared = np.min(
            np.sum((values[:, None, :] - closest) ** 2, axis=2), axis=1
        )
        maximum_squared = max(maximum_squared, float(np.max(minimum_squared)))
    return math.sqrt(maximum_squared)


def maximum_curve_set_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Symmetric maximum vertex-to-closed-polygon distance between curves.

    This metric is insensitive to cyclic node phase and orientation.  Unlike
    nearest-node distance, its discretisation floor is the polygon chord
    error (quadratic in node spacing), not the node spacing itself.
    """

    return max(
        _maximum_point_to_closed_polygon_distance(first, second),
        _maximum_point_to_closed_polygon_distance(second, first),
    )


def _curve_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Backward-compatible private alias for :func:`maximum_curve_set_distance`."""

    return maximum_curve_set_distance(first, second)


def _redistance_curve_drift(first_curve: object, second_curve: object) -> float:
    """Symmetric maximum point-to-closed-polygon distance between curves."""

    first_points = np.asarray(first_curve.points, dtype=np.float64)
    second_points = np.asarray(second_curve.points, dtype=np.float64)
    return _curve_distance(first_points, second_points)


def _redistance_config_for_iteration(
    config: NeuralRedistanceConfig, iteration: int
) -> NeuralRedistanceConfig:
    """Return one deterministic sampling configuration per outer iteration.

    Every damping/backtracking candidate in an iteration must see the same
    training and held-out locations so candidate acceptance is comparable.
    Advancing the seed between accepted outer states avoids repeatedly fitting
    to one fixed Monte-Carlo sample for the entire inverse trajectory.
    """

    if not isinstance(config, NeuralRedistanceConfig):
        raise TypeError("config must be a NeuralRedistanceConfig.")
    index = _positive_integer(iteration, name="iteration")
    return replace(config, seed=config.seed + index)


def _update_meets_canonical_stationarity_tolerances(
    previous_loss: float,
    updated_loss: float,
    curve_change_m: float,
    config: AlternatingNeuralInverseConfig,
    *,
    trust_region_predicted_change: float = 0.0,
) -> bool:
    """Whether the authoritative canonical inverse state is stationary.

    This deliberately excludes every MLP-representation audit.  It is used
    alongside the complete convergence predicate so a stationary canonical
    contour whose neural distillation has plateaued is reported as
    representation-limited instead of buying dozens of vanishing BEM steps.
    """

    previous = _finite_positive(previous_loss, name="previous_loss", allow_zero=True)
    updated = _finite_positive(updated_loss, name="updated_loss", allow_zero=True)
    curve_change = _finite_positive(
        curve_change_m, name="curve_change_m", allow_zero=True
    )
    predicted_change = float(trust_region_predicted_change)
    if not math.isfinite(predicted_change):
        raise ValueError("trust_region_predicted_change must be finite.")
    if not isinstance(config, AlternatingNeuralInverseConfig):
        raise TypeError("config must be an AlternatingNeuralInverseConfig.")
    if updated > previous:
        return False
    relative_change = (previous - updated) / max(previous, np.finfo(float).tiny)
    predicted_relative_change = abs(predicted_change) / max(
        previous, np.finfo(float).tiny
    )
    return bool(
        (updated <= config.loss_tolerance
         or (
             relative_change <= config.relative_loss_change_tolerance
             and predicted_relative_change
             <= config.relative_loss_change_tolerance
         ))
        and curve_change <= config.geometry_change_tolerance_m
    )


def _update_meets_convergence_tolerances(
    previous_loss: float,
    updated_loss: float,
    curve_change_m: float,
    eikonal_rms: float,
    config: AlternatingNeuralInverseConfig,
    *,
    redistance_curve_drift_m: float = 0.0,
    trust_region_predicted_change: float = 0.0,
    maximum_curve_field_residual: float = 0.0,
) -> bool:
    """Whether canonical stationarity and every representation gate pass."""

    eikonal = _finite_positive(eikonal_rms, name="eikonal_rms", allow_zero=True)
    representation_drift = _finite_positive(
        redistance_curve_drift_m,
        name="redistance_curve_drift_m",
        allow_zero=True,
    )
    boundary_residual = _finite_positive(
        maximum_curve_field_residual,
        name="maximum_curve_field_residual",
        allow_zero=True,
    )
    if not isinstance(config, AlternatingNeuralInverseConfig):
        raise TypeError("config must be an AlternatingNeuralInverseConfig.")
    return bool(
        _update_meets_canonical_stationarity_tolerances(
            previous_loss,
            updated_loss,
            curve_change_m,
            config,
            trust_region_predicted_change=trust_region_predicted_change,
        )
        and representation_drift <= config.geometry_change_tolerance_m
        and boundary_residual
        <= min(
            config.geometry_change_tolerance_m,
            config.redistance.boundary_max_tolerance_m,
        )
        and eikonal <= config.eikonal_rms_tolerance
    )


def _failed_step_outcome(
    current_loss: float,
    *,
    best_direct_loss: float | None,
    best_direct_curve_change_m: float | None,
    best_trial_loss: float | None,
    best_trial_curve_change_m: float | None,
    best_trial_predicted_change: float | None,
    eikonal_rms: float,
    config: AlternatingNeuralInverseConfig,
    redistance_curve_drift_m: float = 0.0,
    maximum_curve_field_residual: float = 0.0,
    full_validation_rejection_count: int = 0,
) -> tuple[bool, str]:
    """Classify failure before versus after neural-SDF projection.

    A direct modal descent followed by no decreasing re-distanced state is a
    projection-limited stop, never verified convergence.  The more specific
    ``representation_limited_stationary`` reason says that its best direct update
    was already below the ordinary tolerances without claiming the MLP state
    reached that update.  If larger candidates also hit the dense geometry
    audit, the corresponding reason is ``geometry_limited_stationary`` instead.
    Looking at the best candidate prevents an
    arbitrarily tiny backtrack from hiding a larger useful step that the
    projection failed to preserve.

    Convergence without projection is reserved for a genuinely stationary
    modal trial: its actual loss change, predicted decrease, curve motion,
    current MLP-to-canonical drift, and current Eikonal error must all be
    within their respective gates.
    """

    geometry_rejections = _positive_integer(
        full_validation_rejection_count,
        name="full_validation_rejection_count",
        allow_zero=True,
    )
    representation_required = config.distillation_policy == "legacy_strict"
    if representation_required:
        representation_drift = _finite_positive(
            redistance_curve_drift_m, name="redistance_curve_drift_m", allow_zero=True
        )
        boundary_residual = _finite_positive(
            maximum_curve_field_residual, name="maximum_curve_field_residual", allow_zero=True
        )

    if best_direct_loss is not None:
        if not representation_required:
            return False, "no_decreasing_modal_step"
        if best_direct_curve_change_m is None:
            raise ValueError(
                "best_direct_curve_change_m is required when best_direct_loss is supplied."
            )
        if _update_meets_convergence_tolerances(
            current_loss,
            best_direct_loss,
            best_direct_curve_change_m,
            eikonal_rms,
            config,
            redistance_curve_drift_m=representation_drift,
            maximum_curve_field_residual=boundary_residual,
        ):
            return (
                False,
                "geometry_limited_stationary"
                if geometry_rejections > 0
                else "representation_limited_stationary",
            )
        return False, "no_acceptable_mlp_distillation"

    supplied_trial_values = (
        best_trial_loss,
        best_trial_curve_change_m,
        best_trial_predicted_change,
    )
    if all(value is None for value in supplied_trial_values):
        return False, "no_decreasing_modal_step"
    if any(value is None for value in supplied_trial_values):
        raise ValueError("best trial diagnostics must either all be supplied or all be None.")

    previous = _finite_positive(current_loss, name="current_loss", allow_zero=True)
    trial = _finite_positive(best_trial_loss, name="best_trial_loss", allow_zero=True)
    curve_change = _finite_positive(
        best_trial_curve_change_m,
        name="best_trial_curve_change_m",
        allow_zero=True,
    )
    predicted_change = float(best_trial_predicted_change)
    representation_passes = True
    if representation_required:
        current_eikonal = _finite_positive(eikonal_rms, name="eikonal_rms", allow_zero=True)
        representation_passes = (
            representation_drift <= config.geometry_change_tolerance_m
            and boundary_residual <= min(
                config.geometry_change_tolerance_m, config.redistance.boundary_max_tolerance_m
            )
            and current_eikonal <= config.eikonal_rms_tolerance
        )
    if not math.isfinite(predicted_change):
        raise ValueError("best_trial_predicted_change must be finite.")
    scale = max(previous, np.finfo(float).tiny)
    stationary = (
        abs(trial - previous) / scale
        <= config.relative_loss_change_tolerance
        and max(-predicted_change, 0.0) / scale
        <= config.relative_loss_change_tolerance
        and curve_change <= config.geometry_change_tolerance_m
        and representation_passes
    )
    if stationary:
        return True, "stationary_modal_step"
    return False, "no_decreasing_modal_step"


def _maximum_system_residual(forward_result: object) -> float:
    values = np.asarray(forward_result.linear_system_relative_residuals, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("linear_system_relative_residuals must be a finite vector.")
    return float(np.max(values))


def _field_audit(
    model: nn.Module,
    geometry_points: np.ndarray,
    audit_points: torch.Tensor,
) -> tuple[float, float, float]:
    reference = next(model.parameters(), None)
    if reference is None:
        raise ValueError("Neural inverse model must have parameters.")
    points = audit_points.to(device=reference.device, dtype=reference.dtype).detach().requires_grad_(True)
    values = model(points)
    gradients = torch.autograd.grad(values.sum(), points, create_graph=False)[0]
    deviations = torch.abs(torch.linalg.norm(gradients, dim=1) - 1.0)
    curve_tensor = torch.as_tensor(
        np.array(geometry_points, copy=True), dtype=reference.dtype, device=reference.device
    )
    with torch.no_grad():
        curve_values = torch.abs(model(curve_tensor).reshape(-1))
    return (
        float(torch.sqrt(torch.mean(deviations**2)).detach().cpu()),
        float(torch.max(deviations).detach().cpu()),
        float(torch.max(curve_values).detach().cpu()),
    )


def _audit_points(config: AlternatingNeuralInverseConfig, model: nn.Module) -> torch.Tensor:
    bounds = np.asarray(config.redistance.bounds, dtype=np.float64)
    generator = np.random.default_rng(config.audit_seed)
    values = generator.uniform(bounds[0], bounds[1], size=(config.audit_point_count, 2))
    reference = next(model.parameters(), None)
    if reference is None:
        raise ValueError("Neural inverse model must have parameters.")
    return torch.as_tensor(values, dtype=reference.dtype, device=reference.device)


def _run_alternating_neural_inverse_eval(
    model: nn.Module,
    data: ComplexScatteredData,
    geometry_config: object,
    *,
    solver: str,
    config: AlternatingNeuralInverseConfig,
    progress_callback: ProgressCallback | None = None,
    forward_predictor: ForwardPredictor | None = None,
    curve_forward_predictor: CurveForwardPredictor | None = None,
    initial_curve: PeriodicCurve2D | None = None,
    initial_representation_curve: PeriodicCurve2D | None = None,
    initial_radial_curve_state: RadialFourierCurveState | None = None,
) -> AlternatingNeuralInverseResult:
    """Run direct ordered-curve updates and distil each accepted state to an MLP."""

    if not isinstance(model, nn.Module):
        raise TypeError("model must be a torch.nn.Module.")
    if not isinstance(data, ComplexScatteredData):
        raise TypeError("data must be ComplexScatteredData.")
    if not isinstance(config, AlternatingNeuralInverseConfig):
        raise TypeError("config must be AlternatingNeuralInverseConfig.")
    if solver not in {"mod", "kress"}:
        raise ValueError("solver must be exactly 'mod' or 'kress'.")
    if progress_callback is not None and not callable(progress_callback):
        raise TypeError("progress_callback must be callable when supplied.")
    if initial_curve is not None and not isinstance(initial_curve, PeriodicCurve2D):
        raise TypeError("initial_curve must be a PeriodicCurve2D when supplied.")
    if initial_representation_curve is not None and not isinstance(
        initial_representation_curve, PeriodicCurve2D
    ):
        raise TypeError(
            "initial_representation_curve must be a PeriodicCurve2D when supplied."
        )
    if initial_curve is None and initial_representation_curve is not None:
        raise ValueError(
            "initial_representation_curve requires initial_curve."
        )
    if initial_radial_curve_state is not None and not isinstance(
        initial_radial_curve_state, RadialFourierCurveState
    ):
        raise TypeError(
            "initial_radial_curve_state must be a RadialFourierCurveState when supplied."
        )
    if initial_curve is None and initial_radial_curve_state is not None:
        raise ValueError("initial_radial_curve_state requires initial_curve.")

    default_model_predictor = forward_predictor is None
    if default_model_predictor:
        from .forward import predict_paired_curve_response, predict_paired_response

        model_predictor = predict_paired_response
        curve_predictor = (
            predict_paired_curve_response
            if curve_forward_predictor is None
            else curve_forward_predictor
        )
        direct_curve_probes = True
    else:
        model_predictor = forward_predictor
        curve_predictor = curve_forward_predictor
        # A custom model-based predictor has no general way to consume an
        # ordered curve.  Preserve that injection seam for lightweight tests,
        # but production and new callers should provide the explicit curve
        # predictor and thereby bypass extraction in every modal probe.
        direct_curve_probes = curve_predictor is not None
    if direct_curve_probes and not isinstance(
        geometry_config, OrderedSDFGeometryConfig
    ):
        raise TypeError(
            "Direct curve probes require an OrderedSDFGeometryConfig."
        )
    if initial_curve is not None and not direct_curve_probes:
        raise ValueError(
            "curve_forward_predictor is required with initial_curve when a "
            "custom forward_predictor is supplied."
        )
    if config.direct_curve_retraction == "radial_fourier" and not direct_curve_probes:
        raise ValueError("Radial Fourier retraction requires direct curve probes.")
    if config.direct_curve_retraction == "radial_fourier" and initial_curve is None:
        raise ValueError(
            "Radial Fourier retraction requires an explicit initial_curve."
        )
    if config.direct_curve_retraction == "normal" and initial_radial_curve_state is not None:
        raise ValueError(
            "initial_radial_curve_state requires radial Fourier retraction."
        )
    probe_predictor = curve_predictor if direct_curve_probes else model_predictor
    strict_representation = config.distillation_policy == "legacy_strict"
    if not strict_representation and not direct_curve_probes:
        raise ValueError("curve_only and export_only require direct curve probes.")

    run_started = perf_counter()
    audit_points = _audit_points(config, model) if strict_representation else None
    total_evaluations = 0
    total_infeasible = 0
    total_forward_seconds = 0.0
    total_bem_seconds = 0.0
    total_curve_update_seconds = 0.0
    total_redistance_seconds = 0.0
    redistance_attempt_count = 0
    total_redistance_step_count = 0
    total_geometry_audit_seconds = 0.0
    full_validation_rejection_count = 0
    redistance_failure_count = 0
    representation_extraction_failure_count = 0
    representation_drift_rejection_count = 0
    total_spectral_tail_rejections = 0
    maximum_residual = 0.0
    records: list[NeuralInverseIteration] = []
    stop_reason = "maximum_iterations"
    converged = False
    canonical_converged = False
    stable_iterations = 0
    canonical_stationary_iterations = 0
    representation_limited_iterations = 0
    geometry_limited_iterations = 0

    started = perf_counter()
    initial_geometry_audit_wall = 0.0
    current_radial_curve_state: RadialFourierCurveState | None = None
    if initial_curve is None:
        current_forward = model_predictor(
            model, data.forward_problem, geometry_config, solver=solver
        )
        current_curve = current_forward.geometry_build.curve
        current_representation_curve = current_curve if strict_representation else None
    else:
        current_curve = initial_curve
        # A continuation caller can reuse an explicitly supplied audited MLP
        # contour.  The canonical curve alone says nothing about the current
        # model's zero set: assuming those curves coincide would fabricate a
        # zero drift and bypass topology validation at initialization.
        if not strict_representation:
            current_representation_curve = None
        elif initial_representation_curve is None:
            audit_started = perf_counter()
            current_representation_curve = build_ordered_sdf_geometry(
                model, geometry_config
            ).curve
            initial_geometry_audit_wall = float(perf_counter() - audit_started)
            total_geometry_audit_seconds += initial_geometry_audit_wall
        else:
            current_representation_curve = initial_representation_curve
        if config.direct_curve_retraction == "radial_fourier":
            assert isinstance(geometry_config, OrderedSDFGeometryConfig)
            if initial_radial_curve_state is None:
                current_radial_curve_state = fit_radial_fourier_curve_state(
                    current_curve,
                    maximum_mode=config.maximum_mode,
                )
                current_curve = radial_fourier_state_curve(
                    current_radial_curve_state,
                    geometry_config=geometry_config,
                    full_validation=True,
                )
            else:
                current_radial_curve_state = initial_radial_curve_state
                if config.maximum_mode > current_radial_curve_state.maximum_mode:
                    raise ValueError(
                        "config.maximum_mode cannot exceed the supplied radial state's maximum mode."
                    )
                represented_curve = radial_fourier_state_curve(
                    current_radial_curve_state,
                    geometry_config=geometry_config,
                    full_validation=True,
                )
                if not np.array_equal(represented_curve.points, current_curve.points):
                    raise ValueError(
                        "initial_curve must exactly match initial_radial_curve_state."
                    )
                current_curve = represented_curve
        current_forward = probe_predictor(
            current_curve, data.forward_problem, geometry_config, solver=solver
        )
    initial_wall = float(perf_counter() - started)
    total_evaluations += 1
    total_forward_seconds += initial_wall
    total_bem_seconds += _finite_positive(
        getattr(current_forward, "forward_seconds", initial_wall),
        name="current_forward.forward_seconds",
        allow_zero=True,
    )
    current_residual, current_relative = normalized_complex_residual(
        current_forward.scattered_response,
        data.observed_scattered_response,
        data.frequency_weights,
    )
    current_loss = 0.5 * float(np.dot(current_residual, current_residual))
    maximum_residual = _maximum_system_residual(current_forward)
    current_points = np.asarray(current_curve.points, dtype=np.float64)
    initial_representation_drift = (
        _redistance_curve_drift(current_curve, current_representation_curve)
        if strict_representation else None
    )
    current_representation_drift = initial_representation_drift
    initial_spectral_tail = _radial_spectral_tail_rms(
        current_points, config.maximum_mode
    )
    spectral_tail_reference = (
        initial_spectral_tail
        if config.spectral_tail_reference_rms_m is None
        else config.spectral_tail_reference_rms_m
    )
    # If a supplied continuation state already exceeds its global reference
    # cap, do not make the stage infeasible: permit non-increasing tail so it
    # can recover, while forbidding any further accumulation.
    spectral_tail_limit = (
        None
        if config.maximum_spectral_tail_growth_m is None
        else max(
            initial_spectral_tail,
            spectral_tail_reference + config.maximum_spectral_tail_growth_m,
        )
    )
    if strict_representation:
        eikonal_rms, eikonal_max, curve_field = _field_audit(model, current_points, audit_points)
    else:
        eikonal_rms = eikonal_max = curve_field = None
    initial_speed_ratio = float(
        np.max(current_curve.speeds) / np.min(current_curve.speeds)
    )
    initial_record = NeuralInverseIteration(
        iteration=0,
        loss=current_loss,
        relative_l2_error=current_relative,
        geometry_points=current_points,
        modal_step=np.zeros(normal_mode_count(config.maximum_mode)),
        applied_damping=0.0,
        maximum_modal_field_update_m=0.0,
        curve_change_m=0.0,
        redistance_curve_drift_m=initial_representation_drift,
        eikonal_rms=eikonal_rms,
        eikonal_maximum_deviation=eikonal_max,
        maximum_curve_field_residual=curve_field,
        redistance_steps=0,
        redistance_stop_reason="initialized" if strict_representation else "not_evaluated",
        evaluation_count=total_evaluations,
        maximum_system_residual=maximum_residual,
        accepted_backtrack_count=0,
        accepted_step_predicted_relative_change=0.0,
        arclength_refit_rms_m=0.0,
        arclength_refit_maximum_m=0.0,
        arclength_speed_ratio_before=initial_speed_ratio,
        arclength_speed_ratio_after=initial_speed_ratio,
        timings={
            "iteration_seconds": initial_wall,
            "redistance_seconds": 0.0,
            "geometry_audit_seconds": initial_geometry_audit_wall,
        },
        radial_spectral_tail_rms_m=initial_spectral_tail,
        radial_spectral_tail_limit_m=spectral_tail_limit,
        spectral_tail_rejection_count=0,
        representation_evaluated=strict_representation,
    )
    records.append(initial_record)
    if progress_callback is not None:
        progress_callback(initial_record)

    if (
        current_loss <= config.loss_tolerance
        and (not strict_representation or (
            eikonal_rms <= config.eikonal_rms_tolerance
            and initial_representation_drift <= config.geometry_change_tolerance_m
            and curve_field <= min(
                config.geometry_change_tolerance_m,
                config.redistance.boundary_max_tolerance_m,
            )
        ))
    ):
        return AlternatingNeuralInverseResult(
            solver=solver,
            iterations=tuple(records),
            converged=True,
            stop_reason=("initial_data_representation_and_eikonal_tolerances"
                         if strict_representation else "initial_data_tolerance"),
            total_evaluation_count=total_evaluations,
            infeasible_evaluation_count=total_infeasible,
            maximum_system_residual=maximum_residual,
            total_forward_seconds=total_forward_seconds,
            total_redistance_seconds=total_redistance_seconds,
            total_seconds=float(perf_counter() - run_started),
            final_curve=current_curve,
            final_representation_curve=current_representation_curve,
            total_geometry_audit_seconds=total_geometry_audit_seconds,
            total_bem_seconds=total_bem_seconds,
            total_curve_update_seconds=total_curve_update_seconds,
            redistance_attempt_count=redistance_attempt_count,
            total_redistance_step_count=total_redistance_step_count,
            full_validation_rejection_count=full_validation_rejection_count,
            redistance_failure_count=redistance_failure_count,
            representation_extraction_failure_count=(
                representation_extraction_failure_count
            ),
            representation_drift_rejection_count=(
                representation_drift_rejection_count
            ),
            spectral_tail_rejection_count=total_spectral_tail_rejections,
            final_radial_curve_state=current_radial_curve_state,
            distillation_policy=config.distillation_policy,
            representation_evaluated=strict_representation,
            representation_status="evaluated" if strict_representation else "not_requested",
        )

    damping = config.initial_damping
    for iteration in range(1, config.max_iterations + 1):
        iteration_started = perf_counter()
        iteration_redistance_config = _redistance_config_for_iteration(
            config.redistance, iteration
        )
        if current_radial_curve_state is None:
            center, radius_scale = _curve_center_and_scale(current_points)
        else:
            center = np.asarray(current_radial_curve_state.center)
            radius_scale = current_radial_curve_state.mean_radius_m
        evaluator = _ModalEvaluator(
            model,
            current_curve,
            data,
            geometry_config,
            solver,
            center,
            radius_scale,
            config.maximum_mode,
            probe_predictor,
            current_forward,
            direct_curve_probes=direct_curve_probes,
            direct_curve_retraction=config.direct_curve_retraction,
            radial_curve_state=current_radial_curve_state,
        )
        base = evaluator.evaluate(np.zeros(normal_mode_count(config.maximum_mode)))
        try:
            jacobian, _used_steps = _modal_jacobian(evaluator, base, config)
        except OrderedSDFGeometryError:
            total_evaluations += evaluator.evaluation_count
            total_infeasible += evaluator.infeasible_count
            total_forward_seconds += evaluator.forward_seconds
            total_bem_seconds += evaluator.bem_seconds
            total_curve_update_seconds += evaluator.curve_update_seconds
            maximum_residual = max(
                maximum_residual, evaluator.maximum_system_residual
            )
            stop_reason = "topology_barrier"
            break

        gradient = jacobian.T @ base.residual
        normal_matrix = jacobian.T @ jacobian
        scaling = np.maximum(np.diag(normal_matrix), 1.0)
        curvature = _curvature_penalty(normal_matrix, config)
        if current_radial_curve_state is None:
            basis_at_curve = _mode_values_at_curve(
                model, current_points, center, radius_scale, config.maximum_mode
            )
        else:
            # The authoritative radial curve uses polar angle itself as its
            # periodic parameter.  Audit a dense uniform angular grid rather
            # than only the solver nodes: a phase-shifted retained harmonic can
            # attain its maximum between those nodes.  This same basis is kept
            # through acceptance, so the trust cap and the recorded maximum
            # physical displacement have exactly the same meaning.
            radial_audit_count = max(
                geometry_config.validation_resolution,
                64 * (config.maximum_mode + 1),
            )
            radial_audit_angles = (
                2.0
                * np.pi
                * np.arange(radial_audit_count, dtype=np.float64)
                / radial_audit_count
            )
            basis_at_curve = radial_fourier_displacement_basis(
                radial_audit_angles,
                maximum_mode=config.maximum_mode,
            )
        accepted = None
        trial_damping = damping
        redistance_wall = 0.0
        geometry_audit_wall = 0.0
        best_direct_loss: float | None = None
        best_direct_curve_change: float | None = None
        best_trial_loss: float | None = None
        best_trial_curve_change: float | None = None
        best_trial_predicted_change: float | None = None
        best_retained_representation: _RetainedRepresentationCandidate | None = None
        iteration_spectral_tail_rejections = 0
        iteration_full_validation_rejections = 0
        iteration_redistance_attempt_count = 0
        iteration_redistance_step_count = 0
        sufficient_decrease_count = 0
        tail_blocked_decrease_count = 0
        for _ in range(config.max_damping_trials):
            bounded = _bounded_modal_step(
                normal_matrix,
                gradient,
                scaling,
                curvature,
                basis_at_curve,
                trial_damping,
                config,
            )
            if bounded is None:
                trial_damping *= config.damping_increase
                continue
            raw_step, trial_damping = bounded
            trust_region_predicted_change = float(gradient @ raw_step)

            for backtrack in range(config.max_backtracks + 1):
                modal_step = (0.5**backtrack) * raw_step
                predicted_change = float(gradient @ modal_step)
                try:
                    direct = evaluator.evaluate(modal_step)
                except OrderedSDFGeometryError:
                    continue
                direct_curve_change = _curve_distance(
                    current_points,
                    np.asarray(
                        direct.forward_result.geometry_build.curve.points,
                        dtype=np.float64,
                    ),
                )
                if best_trial_loss is None or direct.loss < best_trial_loss:
                    best_trial_loss = direct.loss
                    best_trial_curve_change = direct_curve_change
                    best_trial_predicted_change = predicted_change
                if not _sufficient_decrease(
                    direct.loss, current_loss, predicted_change, config
                ):
                    continue
                sufficient_decrease_count += 1
                arclength_refit_rms = 0.0
                arclength_refit_maximum = 0.0
                arclength_speed_ratio_before = 1.0
                arclength_speed_ratio_after = 1.0
                direct_curve = direct.forward_result.geometry_build.curve
                direct_forward = direct.forward_result
                direct_loss = direct.loss
                direct_relative = direct.relative_l2_error
                candidate_spectral_tail = _radial_spectral_tail_rms(
                    np.asarray(direct_curve.points, dtype=np.float64),
                    config.maximum_mode,
                )
                # This optional guard is cheap and precedes both the dense
                # continuous validation and neural distillation.
                if (
                    spectral_tail_limit is not None
                    and candidate_spectral_tail > spectral_tail_limit
                ):
                    iteration_spectral_tail_rejections += 1
                    total_spectral_tail_rejections += 1
                    tail_blocked_decrease_count += 1
                    continue
                if direct_curve_probes:
                    # Probe validation is deliberately cheap.  Pay for the
                    # dense continuous topology/regularity audit only after the
                    # data line search has selected this candidate.  A legacy
                    # normal update is then arc-length remeshed and must be
                    # solved again.  A radial-state update is deterministic and
                    # keeps identical nodes across cheap and full validation,
                    # so its already-computed probe response remains exact.
                    validation_started = perf_counter()
                    try:
                        if current_radial_curve_state is None:
                            validated_update = apply_normal_mode_update(
                                current_curve,
                                modal_step,
                                center=center,
                                radius_scale=radius_scale,
                                maximum_mode=config.maximum_mode,
                                geometry_config=geometry_config,
                                full_validation=True,
                                reparameterize_arclength=True,
                            )
                        else:
                            validated_update = apply_radial_fourier_update(
                                current_radial_curve_state,
                                modal_step,
                                maximum_mode=config.maximum_mode,
                                geometry_config=geometry_config,
                                full_validation=True,
                            )
                    except OrderedSDFGeometryError:
                        geometry_audit_wall += float(
                            perf_counter() - validation_started
                        )
                        full_validation_rejection_count += 1
                        iteration_full_validation_rejections += 1
                        continue
                    geometry_audit_wall += float(
                        perf_counter() - validation_started
                    )
                    arclength_refit_rms = validated_update.arclength_refit_rms_m
                    arclength_refit_maximum = (
                        validated_update.arclength_refit_maximum_m
                    )
                    arclength_speed_ratio_before = (
                        validated_update.arclength_speed_ratio_before
                    )
                    arclength_speed_ratio_after = (
                        validated_update.arclength_speed_ratio_after
                    )
                    direct_curve = validated_update.curve
                    if current_radial_curve_state is not None:
                        probe_points = np.asarray(
                            direct.forward_result.geometry_build.curve.points,
                            dtype=np.float64,
                        )
                        if not np.array_equal(probe_points, direct_curve.points):
                            raise RuntimeError(
                                "Radial probe and fully validated retraction must be identical."
                            )
                    candidate_spectral_tail = _radial_spectral_tail_rms(
                        np.asarray(direct_curve.points, dtype=np.float64),
                        config.maximum_mode,
                    )
                    if (
                        spectral_tail_limit is not None
                        and candidate_spectral_tail > spectral_tail_limit
                    ):
                        iteration_spectral_tail_rejections += 1
                        total_spectral_tail_rejections += 1
                        tail_blocked_decrease_count += 1
                        continue

                    if current_radial_curve_state is None:
                        remeshed_forward_started = perf_counter()
                        total_evaluations += 1
                        try:
                            direct_forward = probe_predictor(
                                direct_curve,
                                data.forward_problem,
                                geometry_config,
                                solver=solver,
                            )
                        except OrderedSDFGeometryError:
                            remeshed_forward_wall = float(
                                perf_counter() - remeshed_forward_started
                            )
                            total_forward_seconds += remeshed_forward_wall
                            total_infeasible += 1
                            continue
                        remeshed_forward_wall = float(
                            perf_counter() - remeshed_forward_started
                        )
                        total_forward_seconds += remeshed_forward_wall
                        total_bem_seconds += _finite_positive(
                            getattr(
                                direct_forward,
                                "forward_seconds",
                                remeshed_forward_wall,
                            ),
                            name="direct_forward.forward_seconds",
                            allow_zero=True,
                        )
                        maximum_residual = max(
                            maximum_residual,
                            _maximum_system_residual(direct_forward),
                        )
                        returned_points = np.asarray(
                            direct_forward.geometry_build.curve.points,
                            dtype=np.float64,
                        )
                        if not np.array_equal(returned_points, direct_curve.points):
                            raise RuntimeError(
                                "curve_forward_predictor must solve the remeshed "
                                "ordered curve."
                            )
                        remeshed_residual, direct_relative = normalized_complex_residual(
                            direct_forward.scattered_response,
                            data.observed_scattered_response,
                            data.frequency_weights,
                        )
                        direct_loss = 0.5 * float(
                            np.dot(remeshed_residual, remeshed_residual)
                        )
                        direct_curve_change = _curve_distance(
                            current_points,
                            np.asarray(direct_curve.points, dtype=np.float64),
                        )
                        if not _sufficient_decrease(
                            direct_loss,
                            current_loss,
                            predicted_change,
                            config,
                        ):
                            continue
                if best_direct_loss is None or direct_loss < best_direct_loss:
                    best_direct_loss = direct_loss
                    best_direct_curve_change = direct_curve_change
                if not strict_representation:
                    # Both opt-in policies accept the same physics-validated
                    # canonical step without evaluating a neural field.
                    accepted = (
                        None, direct_forward, direct_loss, direct_relative,
                        direct_curve, None, modal_step,
                        trust_region_predicted_change, predicted_change,
                        backtrack, None, "not_evaluated", False, trial_damping,
                        None, candidate_spectral_tail,
                        arclength_refit_rms, arclength_refit_maximum,
                        arclength_speed_ratio_before, arclength_speed_ratio_after,
                    )
                    break
                retained_candidate = None
                if direct_curve_probes:
                    # The preceding MLP contour was already extracted and
                    # audited.  It remains a valid representation of this new
                    # canonical state only while their set distance satisfies
                    # the ordinary per-update drift gate.  This physical bound
                    # prevents repeated neural failures from letting the two
                    # states silently diverge.
                    retained_drift = _redistance_curve_drift(
                        direct_curve,
                        current_representation_curve,
                    )
                    if retained_drift <= config.maximum_redistance_curve_drift_m:
                        retained_candidate = _RetainedRepresentationCandidate(
                            forward_result=direct_forward,
                            loss=direct_loss,
                            relative_l2_error=direct_relative,
                            curve=direct_curve,
                            modal_step=np.array(modal_step, copy=True),
                            trust_region_predicted_change=(
                                trust_region_predicted_change
                            ),
                            step_predicted_change=predicted_change,
                            backtrack_count=backtrack,
                            fit=None,
                            damping=trial_damping,
                            retained_representation_drift_m=retained_drift,
                            spectral_tail_rms_m=candidate_spectral_tail,
                            arclength_refit_rms_m=arclength_refit_rms,
                            arclength_refit_maximum_m=arclength_refit_maximum,
                            arclength_speed_ratio_before=(
                                arclength_speed_ratio_before
                            ),
                            arclength_speed_ratio_after=(
                                arclength_speed_ratio_after
                            ),
                        )
                candidate_model = copy.deepcopy(model)
                redistance_started = perf_counter()
                redistance_attempt_count += 1
                iteration_redistance_attempt_count += 1
                fit: NeuralRedistanceResult = redistance_neural_sdf_to_curve(
                    candidate_model,
                    direct_curve,
                    iteration_redistance_config,
                )
                redistance_elapsed = float(perf_counter() - redistance_started)
                redistance_wall += redistance_elapsed
                total_redistance_step_count += fit.steps
                iteration_redistance_step_count += fit.steps
                if not fit.converged:
                    redistance_failure_count += 1
                    if retained_candidate is not None:
                        contender = replace(
                            retained_candidate,
                            fit=fit,
                            redistance_stop_reason=(
                                "retained_previous_representation_after_"
                                f"redistance_{fit.stop_reason}"
                            ),
                        )
                        if (
                            best_retained_representation is None
                            or contender.loss < best_retained_representation.loss
                        ):
                            best_retained_representation = contender
                    continue
                audit_started = perf_counter()
                audit_forward = None
                if not direct_curve_probes:
                    total_evaluations += 1
                try:
                    if direct_curve_probes:
                        candidate_geometry = build_ordered_sdf_geometry(
                            candidate_model, geometry_config
                        )
                    else:
                        # Compatibility only for injected synthetic tests.
                        # The real path performs geometry extraction without a
                        # redundant BEM solve.
                        audit_forward = model_predictor(
                            candidate_model,
                            data.forward_problem,
                            geometry_config,
                            solver=solver,
                        )
                        candidate_geometry = audit_forward.geometry_build
                except OrderedSDFGeometryError:
                    audit_elapsed = float(perf_counter() - audit_started)
                    geometry_audit_wall += audit_elapsed
                    if not direct_curve_probes:
                        total_forward_seconds += audit_elapsed
                        total_infeasible += 1
                    representation_extraction_failure_count += 1
                    if retained_candidate is not None:
                        contender = replace(
                            retained_candidate,
                            fit=fit,
                            redistance_stop_reason=(
                                "retained_previous_representation_after_"
                                "representation_extraction_failure"
                            ),
                        )
                        if (
                            best_retained_representation is None
                            or contender.loss < best_retained_representation.loss
                        ):
                            best_retained_representation = contender
                    continue
                audit_elapsed = float(perf_counter() - audit_started)
                geometry_audit_wall += audit_elapsed
                if audit_forward is not None:
                    total_forward_seconds += audit_elapsed
                    total_bem_seconds += _finite_positive(
                        getattr(audit_forward, "forward_seconds", audit_elapsed),
                        name="audit_forward.forward_seconds",
                        allow_zero=True,
                    )
                    maximum_residual = max(
                        maximum_residual, _maximum_system_residual(audit_forward)
                    )
                redistance_drift = _redistance_curve_drift(
                    direct_curve,
                    candidate_geometry.curve,
                )
                if redistance_drift > config.maximum_redistance_curve_drift_m:
                    representation_drift_rejection_count += 1
                    if retained_candidate is not None:
                        contender = replace(
                            retained_candidate,
                            fit=fit,
                            redistance_stop_reason=(
                                "retained_previous_representation_after_"
                                "representation_drift_rejection"
                            ),
                        )
                        if (
                            best_retained_representation is None
                            or contender.loss < best_retained_representation.loss
                        ):
                            best_retained_representation = contender
                    continue
                if audit_forward is None:
                    accepted_forward = direct_forward
                    accepted_loss = direct_loss
                    accepted_relative = direct_relative
                    accepted_curve = direct_curve
                else:
                    # Preserve the historical model-only predictor injection
                    # seam coherently: without a curve predictor its next +/-
                    # probes are necessarily based on the distilled MLP, so
                    # the accepted base response and curve must be too.
                    audit_residual, accepted_relative = normalized_complex_residual(
                        audit_forward.scattered_response,
                        data.observed_scattered_response,
                        data.frequency_weights,
                    )
                    accepted_loss = 0.5 * float(
                        np.dot(audit_residual, audit_residual)
                    )
                    if not _sufficient_decrease(
                        accepted_loss,
                        current_loss,
                        predicted_change,
                        config,
                    ):
                        continue
                    accepted_curve = candidate_geometry.curve
                    accepted_forward = audit_forward
                    legacy_tail = _radial_spectral_tail_rms(
                        np.asarray(accepted_curve.points, dtype=np.float64),
                        config.maximum_mode,
                    )
                    if (
                        spectral_tail_limit is not None
                        and legacy_tail > spectral_tail_limit
                    ):
                        iteration_spectral_tail_rejections += 1
                        total_spectral_tail_rejections += 1
                        tail_blocked_decrease_count += 1
                        continue
                    candidate_spectral_tail = legacy_tail
                    legacy_speed_ratio = float(
                        np.max(accepted_curve.speeds)
                        / np.min(accepted_curve.speeds)
                    )
                    arclength_speed_ratio_before = legacy_speed_ratio
                    arclength_speed_ratio_after = legacy_speed_ratio
                # The BEM decrease belongs to ``direct_curve`` and remains the
                # accepted inverse state.  The extracted MLP curve is retained
                # as a representation audit only; allowing its discretization
                # error to replace the contour here created the non-vanishing
                # late-iteration projection floor seen in the benchmark.
                accepted = (
                    candidate_model,
                    accepted_forward,
                    accepted_loss,
                    accepted_relative,
                    accepted_curve,
                    candidate_geometry.curve,
                    modal_step,
                    # Keep the un-backtracked trust-region model change.  A
                    # tiny accepted backtrack does not certify stationarity
                    # while the model still proposes a materially large
                    # direction at the current trust-region radius.
                    trust_region_predicted_change,
                    predicted_change,
                    backtrack,
                    fit,
                    fit.stop_reason,
                    True,
                    trial_damping,
                    redistance_drift,
                    candidate_spectral_tail,
                    arclength_refit_rms,
                    arclength_refit_maximum,
                    arclength_speed_ratio_before,
                    arclength_speed_ratio_after,
                )
                break
            if accepted is not None:
                break
            trial_damping *= config.damping_increase

        if accepted is None and best_retained_representation is not None:
            fallback = best_retained_representation
            fallback_curve_change = _curve_distance(
                current_points,
                np.asarray(fallback.curve.points, dtype=np.float64),
            )
            # A lagging representation may keep a materially moving canonical
            # inverse alive, but must never manufacture convergence through a
            # sequence of vanishing curve updates.  A stationary direct state
            # remains a representation-limited non-converged outcome below.
            fallback_is_stationary = (
                _update_meets_canonical_stationarity_tolerances(
                    current_loss,
                    fallback.loss,
                    fallback_curve_change,
                    config,
                    trust_region_predicted_change=(
                        fallback.trust_region_predicted_change
                    ),
                )
            )
            if not fallback_is_stationary:
                assert fallback.fit is not None
                accepted = (
                    None,
                    fallback.forward_result,
                    fallback.loss,
                    fallback.relative_l2_error,
                    fallback.curve,
                    current_representation_curve,
                    fallback.modal_step,
                    fallback.trust_region_predicted_change,
                    fallback.step_predicted_change,
                    fallback.backtrack_count,
                    fallback.fit,
                    fallback.redistance_stop_reason,
                    False,
                    fallback.damping,
                    fallback.retained_representation_drift_m,
                    fallback.spectral_tail_rms_m,
                    fallback.arclength_refit_rms_m,
                    fallback.arclength_refit_maximum_m,
                    fallback.arclength_speed_ratio_before,
                    fallback.arclength_speed_ratio_after,
                )

        total_evaluations += evaluator.evaluation_count
        total_infeasible += evaluator.infeasible_count
        total_forward_seconds += evaluator.forward_seconds
        total_bem_seconds += evaluator.bem_seconds
        total_curve_update_seconds += evaluator.curve_update_seconds
        total_redistance_seconds += redistance_wall
        total_geometry_audit_seconds += geometry_audit_wall
        maximum_residual = max(maximum_residual, evaluator.maximum_system_residual)
        if accepted is None:
            if (
                sufficient_decrease_count > 0
                and tail_blocked_decrease_count == sufficient_decrease_count
            ):
                converged = False
                stop_reason = "spectral_tail_growth_limit"
            elif (
                iteration_redistance_attempt_count == 0
                and iteration_full_validation_rejections > 0
            ):
                converged = False
                stop_reason = "no_fully_valid_geometry"
            else:
                converged, stop_reason = _failed_step_outcome(
                    current_loss,
                    best_direct_loss=best_direct_loss,
                    best_direct_curve_change_m=best_direct_curve_change,
                    best_trial_loss=best_trial_loss,
                    best_trial_curve_change_m=best_trial_curve_change,
                    best_trial_predicted_change=best_trial_predicted_change,
                    eikonal_rms=eikonal_rms,
                    config=config,
                    redistance_curve_drift_m=current_representation_drift,
                    maximum_curve_field_residual=curve_field,
                    full_validation_rejection_count=(
                        iteration_full_validation_rejections
                    ),
                )
            break

        (
            accepted_model,
            accepted_forward,
            accepted_loss,
            accepted_relative,
            accepted_curve,
            accepted_representation_curve,
            accepted_step,
            accepted_trust_region_predicted_change,
            accepted_step_predicted_change,
            accepted_backtrack_count,
            fit,
            accepted_redistance_stop_reason,
            accepted_representation_updated,
            used_damping,
            redistance_drift,
            accepted_spectral_tail,
            accepted_arclength_refit_rms,
            accepted_arclength_refit_maximum,
            accepted_arclength_speed_ratio_before,
            accepted_arclength_speed_ratio_after,
        ) = accepted
        previous_loss = current_loss
        previous_points = current_points
        if accepted_model is not None:
            model.load_state_dict(accepted_model.state_dict())
            if isinstance(model, SmoothMLPSDF2D) and isinstance(
                accepted_model, SmoothMLPSDF2D
            ):
                model.trained_against_signed_distance = (
                    accepted_model.trained_against_signed_distance
                )
        if current_radial_curve_state is not None:
            current_radial_curve_state = current_radial_curve_state.incremented(
                accepted_step,
                maximum_mode=config.maximum_mode,
            )
            represented_curve = radial_fourier_state_curve(
                current_radial_curve_state,
                geometry_config=geometry_config,
                full_validation=False,
            )
            if not np.array_equal(represented_curve.points, accepted_curve.points):
                raise RuntimeError(
                    "Accepted curve does not match the advanced radial state."
                )
        current_forward = accepted_forward
        current_curve = accepted_curve
        current_representation_curve = accepted_representation_curve
        current_representation_drift = redistance_drift
        current_loss = accepted_loss
        current_relative = accepted_relative
        current_points = np.asarray(current_curve.points, dtype=np.float64)
        curve_change = _curve_distance(previous_points, current_points)
        max_modal_update = _maximum_modal_displacement(
            basis_at_curve, accepted_step
        )
        trust_region_predicted_relative_change = abs(
            accepted_trust_region_predicted_change
        ) / max(previous_loss, np.finfo(float).tiny)
        accepted_step_predicted_relative_change = abs(
            accepted_step_predicted_change
        ) / max(previous_loss, np.finfo(float).tiny)
        if strict_representation:
            eikonal_rms, eikonal_max, curve_field = _field_audit(model, current_points, audit_points)
        maximum_residual = max(maximum_residual, _maximum_system_residual(current_forward))
        record = NeuralInverseIteration(
            iteration=iteration,
            loss=current_loss,
            relative_l2_error=current_relative,
            geometry_points=current_points,
            modal_step=accepted_step,
            applied_damping=used_damping,
            maximum_modal_field_update_m=max_modal_update,
            curve_change_m=curve_change,
            redistance_curve_drift_m=redistance_drift,
            eikonal_rms=eikonal_rms,
            eikonal_maximum_deviation=eikonal_max,
            maximum_curve_field_residual=curve_field,
            # This is the work spent on every attempted fit in the accepted
            # outer iteration, including rejected candidates before either a
            # fresh or retained representation was selected.
            redistance_steps=iteration_redistance_step_count,
            redistance_stop_reason=accepted_redistance_stop_reason,
            evaluation_count=total_evaluations,
            maximum_system_residual=maximum_residual,
            trust_region_predicted_relative_change=(
                trust_region_predicted_relative_change
            ),
            accepted_step_predicted_relative_change=(
                accepted_step_predicted_relative_change
            ),
            accepted_backtrack_count=accepted_backtrack_count,
            timings={
                "iteration_seconds": float(perf_counter() - iteration_started),
                "redistance_seconds": redistance_wall,
                "geometry_audit_seconds": geometry_audit_wall,
            },
            radial_spectral_tail_rms_m=accepted_spectral_tail,
            radial_spectral_tail_limit_m=spectral_tail_limit,
            spectral_tail_rejection_count=iteration_spectral_tail_rejections,
            arclength_refit_rms_m=accepted_arclength_refit_rms,
            arclength_refit_maximum_m=accepted_arclength_refit_maximum,
            arclength_speed_ratio_before=(
                accepted_arclength_speed_ratio_before
            ),
            arclength_speed_ratio_after=accepted_arclength_speed_ratio_after,
            representation_evaluated=strict_representation,
        )
        records.append(record)
        if progress_callback is not None:
            progress_callback(record)
        # A full accepted step earns less damping.  A backtracked acceptance
        # does not: decreasing here made the next outer iteration immediately
        # reconstruct the damping it had just discarded, while rotating the
        # direction through a long reject/escalate cycle.  Retain the damping
        # that produced the accepted direction whenever the line search had
        # to shorten it.
        damping_scale = (
            config.damping_decrease if accepted_backtrack_count == 0 else 1.0
        )
        damping = max(used_damping * damping_scale, config.minimum_damping)

        canonical_stationary = _update_meets_canonical_stationarity_tolerances(
            previous_loss,
            current_loss,
            curve_change,
            config,
            trust_region_predicted_change=(
                accepted_trust_region_predicted_change
            ),
        )
        stable = canonical_stationary
        if strict_representation:
            stable = bool(accepted_representation_updated and _update_meets_convergence_tolerances(
                previous_loss,
                current_loss,
                curve_change,
                eikonal_rms,
                config,
                redistance_curve_drift_m=redistance_drift,
                trust_region_predicted_change=(
                    accepted_trust_region_predicted_change
                ),
                maximum_curve_field_residual=curve_field,
            ))
        canonical_stationary_iterations = (
            canonical_stationary_iterations + 1 if canonical_stationary else 0
        )
        stable_iterations = stable_iterations + 1 if stable else 0
        geometry_limited = bool(
            canonical_stationary
            and not stable
            and iteration_full_validation_rejections > 0
        )
        geometry_limited_iterations = (
            geometry_limited_iterations + 1 if geometry_limited else 0
        )
        representation_limited_iterations = (
            representation_limited_iterations + 1
            if canonical_stationary
            and not stable
            and iteration_full_validation_rejections == 0
            else 0
        )
        if stable_iterations >= config.consecutive_convergence_iterations:
            converged = True
            stop_reason = (
                "stable_data_geometry_representation_and_eikonal"
                if strict_representation else "stable_data_and_geometry"
            )
            break
        if (
            canonical_stationary_iterations
            >= config.consecutive_convergence_iterations
            and geometry_limited_iterations
            >= config.consecutive_convergence_iterations
        ):
            # The accepted contour moved only after larger, data-decreasing
            # candidates repeatedly failed the dense topology/regularity
            # audit.  The resulting micro-step plateau is a geometry barrier,
            # not evidence that the MLP representation is the limiting state.
            converged = False
            stop_reason = "geometry_limited_stationary"
            break
        if (
            canonical_stationary_iterations
            >= config.consecutive_convergence_iterations
            and representation_limited_iterations
            >= config.consecutive_convergence_iterations
        ):
            # The canonical contour is the accepted inverse state.  Once its
            # realised and predicted data changes and its motion are all
            # stationary, further modal cycles cannot repair a plateaued MLP
            # representation; they only repeat the expensive BEM/distillation
            # pair for progressively smaller updates.
            converged = False
            canonical_converged = True
            stop_reason = "representation_limited_stationary"
            break

    return AlternatingNeuralInverseResult(
        solver=solver,
        iterations=tuple(records),
        converged=converged,
        stop_reason=stop_reason,
        total_evaluation_count=total_evaluations,
        infeasible_evaluation_count=total_infeasible,
        maximum_system_residual=maximum_residual,
        total_forward_seconds=total_forward_seconds,
        total_redistance_seconds=total_redistance_seconds,
        total_seconds=float(perf_counter() - run_started),
        final_curve=current_curve,
        final_representation_curve=current_representation_curve,
        total_geometry_audit_seconds=total_geometry_audit_seconds,
        total_bem_seconds=total_bem_seconds,
        total_curve_update_seconds=total_curve_update_seconds,
        redistance_attempt_count=redistance_attempt_count,
        total_redistance_step_count=total_redistance_step_count,
        full_validation_rejection_count=full_validation_rejection_count,
        redistance_failure_count=redistance_failure_count,
        representation_extraction_failure_count=(
            representation_extraction_failure_count
        ),
        representation_drift_rejection_count=(
            representation_drift_rejection_count
        ),
        spectral_tail_rejection_count=total_spectral_tail_rejections,
        final_radial_curve_state=current_radial_curve_state,
        distillation_policy=config.distillation_policy,
        representation_evaluated=strict_representation,
        representation_status="evaluated" if strict_representation else "not_requested",
        reconstruction_converged=converged or canonical_converged,
        reconstruction_stop_reason=(
            "stable_data_and_geometry" if canonical_converged else stop_reason
        ),
    )


@dataclass(frozen=True)
class NeuralSDFExportResult:
    """A separate delivery result; failure never replaces the canonical curve."""

    status: str
    stop_reason: str
    representation_evaluated: bool
    curve: PeriodicCurve2D | None = None
    fit: NeuralRedistanceResult | None = None
    drift_m: float | None = None
    eikonal_rms: float | None = None
    eikonal_maximum_deviation: float | None = None
    maximum_curve_field_residual: float | None = None
    relative_l2_error: float | None = None
    total_seconds: float = 0.0
    training_seconds: float = 0.0
    audit_seconds: float = 0.0
    forward_seconds: float = 0.0
    training_attempt_count: int = 0
    extraction_count: int = 0
    forward_evaluation_count: int = 0
    audit_num_nodes: int = 0
    drift_refinement_difference_m: float | None = None

    def __post_init__(self) -> None:
        if self.status not in {"passed", "failed"}:
            raise ValueError("export status must be passed or failed.")
        if not isinstance(self.stop_reason, str) or not self.stop_reason:
            raise ValueError("export stop_reason must be non-empty.")
        if not isinstance(self.representation_evaluated, (bool, np.bool_)):
            raise TypeError("representation_evaluated must be bool.")
        if self.curve is not None and not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("export curve must be PeriodicCurve2D when present.")
        if self.status == "passed" and (self.curve is None or not self.representation_evaluated):
            raise ValueError("a passed export requires an evaluated curve.")
        for name in (
            "drift_m", "eikonal_rms", "eikonal_maximum_deviation",
            "maximum_curve_field_residual", "relative_l2_error", "drift_refinement_difference_m",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite_positive(value, name=name, allow_zero=True))
        for name in ("total_seconds", "training_seconds", "audit_seconds", "forward_seconds"):
            object.__setattr__(self, name, _finite_positive(getattr(self, name), name=name, allow_zero=True))
        for name in ("training_attempt_count", "extraction_count", "forward_evaluation_count", "audit_num_nodes"):
            object.__setattr__(self, name, _positive_integer(getattr(self, name), name=name, allow_zero=True))


def export_neural_sdf_representation(
    model: nn.Module,
    curve: PeriodicCurve2D,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    config: AlternatingNeuralInverseConfig,
    continuous_curve: PeriodicParameterization2D | None = None,
    data: ComplexScatteredData | None = None,
    solver: str = "kress",
    curve_forward_predictor: CurveForwardPredictor | None = None,
) -> NeuralSDFExportResult:
    """Train one final smooth-curve export, committing model weights only on success.

    Drift compares the supplied continuous producer to independently refined
    extracted polygons. Agreement under doubling is a numerical check, not a
    global error certificate. The returned representation uses the requested
    solver node grid, independently of the denser drift-audit grids.
    """

    if not isinstance(model, nn.Module) or not isinstance(curve, PeriodicCurve2D):
        raise TypeError("export requires a Torch module and a PeriodicCurve2D.")
    if not isinstance(config, AlternatingNeuralInverseConfig):
        raise TypeError("config must be AlternatingNeuralInverseConfig.")
    if not isinstance(geometry_config, OrderedSDFGeometryConfig):
        raise TypeError("geometry_config must be OrderedSDFGeometryConfig.")
    if solver not in {"mod", "kress"}:
        raise ValueError("solver must be mod or kress.")
    from .continuous_distance import ContinuousDistanceRefinementError
    started = perf_counter()
    values = dict(representation_evaluated=False)

    def finish(status: str, reason: str) -> NeuralSDFExportResult:
        # Failed candidate weights are rolled back, so their contour must not
        # be exposed as the current model's delivered representation.
        if status == "failed":
            values.pop("curve", None)
        return NeuralSDFExportResult(
            status=status, stop_reason=reason,
            total_seconds=float(perf_counter() - started), **values,
        )

    if continuous_curve is None:
        return finish("failed", "continuous_curve_required")
    if not isinstance(continuous_curve, PeriodicParameterization2D):
        raise TypeError("continuous_curve must be PeriodicParameterization2D.")
    candidate = copy.deepcopy(model)
    candidate.eval()
    train_started = perf_counter()
    values["training_attempt_count"] = 1
    values["representation_evaluated"] = True
    try:
        fit = redistance_neural_sdf_to_curve(
            candidate, curve, replace(config.redistance, distance_target="smooth_curve"),
            continuous_curve=continuous_curve,
        )
    except ContinuousDistanceRefinementError as exc:
        # Targets are prepared before redistancing evaluates the model. A
        # target-refinement failure therefore did not audit a representation.
        values["representation_evaluated"] = False
        values["training_seconds"] = float(perf_counter() - train_started)
        return finish("failed", f"redistance_numerical_failure: {exc}")
    except FloatingPointError as exc:
        values["training_seconds"] = float(perf_counter() - train_started)
        return finish("failed", f"redistance_numerical_failure: {exc}")
    values["training_seconds"] = float(perf_counter() - train_started)
    values["fit"] = fit
    values["representation_evaluated"] = True
    values["eikonal_rms"] = fit.final_eikonal_rms
    values["eikonal_maximum_deviation"] = fit.final_eikonal_maximum_deviation
    values["maximum_curve_field_residual"] = fit.final_boundary_max_abs_m
    if not fit.converged:
        return finish("failed", f"redistance_{fit.stop_reason}")
    audit_started = perf_counter()
    audit_count = max(config.representation_audit_num_nodes, 2 * geometry_config.bandwidth + 2)
    audit_curve = continuous_curve.discretize(audit_count, require_even=True)
    try:
        eikonal_rms, eikonal_max, field_residual = _field_audit(
            candidate, np.asarray(audit_curve.points), _audit_points(config, candidate)
        )
    except FloatingPointError as exc:
        values["audit_seconds"] = float(perf_counter() - audit_started)
        return finish("failed", f"nonfinite_representation_audit: {exc}")
    if not all(math.isfinite(value) for value in (eikonal_rms, eikonal_max, field_residual)):
        values["audit_seconds"] = float(perf_counter() - audit_started)
        return finish("failed", "nonfinite_representation_audit")
    values["eikonal_rms"] = eikonal_rms
    values["eikonal_maximum_deviation"] = eikonal_max
    values["maximum_curve_field_residual"] = field_residual
    values["extraction_count"] = 0
    try:
        values["extraction_count"] += 1
        representation = build_ordered_sdf_geometry(candidate, geometry_config).curve
        values["curve"] = representation
        previous_drift = None
        drift_converged = False
        while audit_count <= config.maximum_representation_audit_num_nodes:
            values["extraction_count"] += 1
            audited = build_ordered_sdf_geometry(
                candidate, replace(geometry_config, num_nodes=audit_count)
            ).curve
            canonical = continuous_curve.discretize(audit_count, require_even=True)
            drift = _redistance_curve_drift(canonical, audited)
            values["drift_m"] = drift
            values["audit_num_nodes"] = audit_count
            if previous_drift is not None:
                difference = abs(drift - previous_drift)
                values["drift_refinement_difference_m"] = difference
                if difference <= config.representation_audit_tolerance_m:
                    drift_converged = True
                    break
            previous_drift = drift
            audit_count *= 2
    except OrderedSDFGeometryError as exc:
        values["audit_seconds"] = float(perf_counter() - audit_started)
        return finish("failed", f"representation_extraction_failure: {exc}")
    values["audit_seconds"] = float(perf_counter() - audit_started)
    if not drift_converged:
        return finish("failed", "representation_drift_refinement_limit")
    if values["drift_m"] > config.representation_export_drift_tolerance_m:
        return finish("failed", "representation_drift_tolerance")
    if eikonal_rms > config.eikonal_rms_tolerance:
        return finish("failed", "representation_eikonal_tolerance")
    if field_residual > config.redistance.boundary_max_tolerance_m:
        return finish("failed", "representation_boundary_tolerance")
    if data is not None:
        if curve_forward_predictor is None:
            from .forward import predict_paired_curve_response
            curve_forward_predictor = predict_paired_curve_response
        forward_started = perf_counter()
        values["forward_evaluation_count"] = 1
        try:
            prediction = curve_forward_predictor(representation, data.forward_problem, geometry_config, solver=solver)
            _, relative = normalized_complex_residual(
                prediction.scattered_response, data.observed_scattered_response, data.frequency_weights
            )
        except (OrderedSDFGeometryError, FloatingPointError, np.linalg.LinAlgError) as exc:
            values["forward_seconds"] = float(perf_counter() - forward_started)
            return finish("failed", f"representation_forward_failure: {exc}")
        values["forward_seconds"] = float(perf_counter() - forward_started)
        values["relative_l2_error"] = relative
    model.load_state_dict(candidate.state_dict())
    if isinstance(model, SmoothMLPSDF2D):
        model.trained_against_signed_distance = candidate.trained_against_signed_distance
    return finish("passed", "smooth_curve_distance_topology_drift_and_eikonal_tolerances")


def run_alternating_neural_inverse(
    model: nn.Module,
    data: ComplexScatteredData,
    geometry_config: object,
    *,
    solver: str,
    config: AlternatingNeuralInverseConfig,
    progress_callback: ProgressCallback | None = None,
    forward_predictor: ForwardPredictor | None = None,
    curve_forward_predictor: CurveForwardPredictor | None = None,
    initial_curve: PeriodicCurve2D | None = None,
    initial_representation_curve: PeriodicCurve2D | None = None,
    initial_radial_curve_state: RadialFourierCurveState | None = None,
) -> AlternatingNeuralInverseResult:
    """Run the alternating inverse with a canonical ordered-contour state.

    The production path perturbs and solves that curve directly.  After a
    decreasing step, the MLP is re-distanced and its extracted zero set is
    audited, but that representation error is never recycled into the next
    finite-difference Jacobian.  ``initial_curve`` carries the exact canonical
    state between frequency-continuation stages without re-extraction;
    ``initial_representation_curve`` carries the already-audited MLP contour
    alongside it when those two differ. In ``legacy_strict``, omitting that
    representation with an explicit ``initial_curve`` performs one
    geometry-only extraction to audit the model before optimization begins.

    With ``config.direct_curve_retraction == 'radial_fourier'``, an explicit
    ``initial_curve`` is projected once when ``initial_radial_curve_state`` is
    omitted.  Continuation callers should pass the prior result's radial state
    as well as its curve so the finite-dimensional state remains authoritative
    and no stage boundary silently re-projects it.  If later stages raise the
    active mode limit, that supplied state must be preallocated at the final
    maximum mode; each earlier stage updates only its active low-mode prefix.

    Schema version 2 retains historical ``converged``/``stop_reason`` for
    ``legacy_strict``. For ``curve_only`` and ``export_only`` they describe
    reconstruction only; ``representation_status`` and
    ``requested_delivery_complete`` report a separately requested export.
    Unevaluated neural diagnostics are None. Automatic smooth export needs
    the final radial continuous producer; other final continuous curves can
    be supplied explicitly to :func:`export_neural_sdf_representation`.
    """

    if not isinstance(model, nn.Module):
        raise TypeError("model must be a torch.nn.Module.")
    if not isinstance(config, AlternatingNeuralInverseConfig):
        raise TypeError("config must be AlternatingNeuralInverseConfig.")
    parameters = tuple(model.parameters())
    trainable = tuple(parameter for parameter in parameters if parameter.requires_grad)
    if config.distillation_policy != "curve_only" and not trainable:
        raise ValueError("model must have at least one trainable parameter.")
    if any(not parameter.is_floating_point() for parameter in parameters):
        raise TypeError("all model parameters must have floating-point dtype.")
    devices = {parameter.device for parameter in parameters}
    dtypes = {parameter.dtype for parameter in parameters}
    if config.distillation_policy != "curve_only" and (len(devices) != 1 or len(dtypes) != 1):
        raise ValueError("all model parameters must share one device and floating dtype.")

    was_training = model.training
    model.eval()
    try:
        result = _run_alternating_neural_inverse_eval(
            model,
            data,
            geometry_config,
            solver=solver,
            config=config,
            progress_callback=progress_callback,
            forward_predictor=forward_predictor,
            curve_forward_predictor=curve_forward_predictor,
            initial_curve=initial_curve,
            initial_representation_curve=initial_representation_curve,
            initial_radial_curve_state=initial_radial_curve_state,
        )
        if config.distillation_policy == "legacy_strict":
            final = result.final_iteration
            representation_passes = (
                final.redistance_curve_drift_m <= config.geometry_change_tolerance_m
                and final.maximum_curve_field_residual <= min(
                    config.geometry_change_tolerance_m,
                    config.redistance.boundary_max_tolerance_m,
                )
                and final.eikonal_rms <= config.eikonal_rms_tolerance
            )
            return replace(
                result,
                representation_status="passed" if representation_passes else "failed",
                representation_stop_reason=(
                    "legacy_representation_convergence_tolerances"
                    if representation_passes else "legacy_representation_tolerances_not_met"
                ),
            )
        if config.distillation_policy == "curve_only":
            return replace(result, representation_stop_reason="not_requested")
        continuous_curve = (
            None if result.final_radial_curve_state is None
            else radial_fourier_parameterization(result.final_radial_curve_state)
        )
        exported = export_neural_sdf_representation(
            model, result.final_curve, geometry_config, config=config,
            continuous_curve=continuous_curve, data=data, solver=solver,
            curve_forward_predictor=curve_forward_predictor,
        )
        return replace(
            result,
            final_representation_curve=exported.curve,
            representation_status=exported.status,
            representation_stop_reason=exported.stop_reason,
            representation_evaluated=exported.representation_evaluated,
            export_result=exported,
            export_seconds=exported.total_seconds,
            total_seconds=result.total_seconds + exported.total_seconds,
            total_redistance_seconds=result.total_redistance_seconds + exported.training_seconds,
            total_geometry_audit_seconds=result.total_geometry_audit_seconds + exported.audit_seconds,
            total_forward_seconds=result.total_forward_seconds + exported.forward_seconds,
            total_evaluation_count=result.total_evaluation_count + exported.forward_evaluation_count,
            redistance_attempt_count=result.redistance_attempt_count + exported.training_attempt_count,
            total_redistance_step_count=result.total_redistance_step_count + (0 if exported.fit is None else exported.fit.steps),
        )
    finally:
        model.train(was_training)


__all__ = [
    "AlternatingNeuralInverseConfig",
    "AlternatingNeuralInverseResult",
    "NeuralInverseIteration",
    "NeuralSDFExportResult",
    "SmoothNormalModeUpdate2D",
    "maximum_curve_set_distance",
    "export_neural_sdf_representation",
    "normal_mode_count",
    "radial_spectral_tail_rms",
    "resolvable_maximum_mode",
    "run_alternating_neural_inverse",
]
