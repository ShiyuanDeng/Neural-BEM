"""Method C: conservative SDF-constrained Fourier coefficient refinement."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import operator
import time
from typing import Any

import numpy as np
from scipy.special import expit
from scipy.spatial import cKDTree

from ordered_boundary import (
    BoundaryValidationConfig,
    CurveProvenance2D,
    validate_periodic_parameterization,
)

from .arclength import ArcLengthConfig, reparameterize_by_arclength
from .fields import ImplicitField2D
from .representations import FourierBoundary, fit_fourier_least_squares
from .results import BoundaryMethodResult


@dataclass(frozen=True)
class RefinementWeights:
    """Dimensionless weights for one coefficient-optimization stage."""

    fidelity: float = 1.0
    anchor: float = 0.0
    spectral: float = 0.0
    speed: float = 0.0
    regularity: float = 0.0
    normal: float = 0.0
    self_distance: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "fidelity",
            "anchor",
            "spectral",
            "speed",
            "regularity",
            "normal",
            "self_distance",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} weight must be finite and non-negative.")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class RefinementStage:
    """One deterministic Adam stage in Fourier coefficient space."""

    name: str
    iterations: int
    relative_learning_rate: float
    weights: RefinementWeights

    def __post_init__(self) -> None:
        name = str(self.name).strip()
        if not name:
            raise ValueError("stage name must be non-empty.")
        if isinstance(self.iterations, bool):
            raise TypeError("iterations must be an integer, not bool.")
        try:
            iterations = operator.index(self.iterations)
        except TypeError as exc:
            raise TypeError("iterations must be an integer.") from exc
        if iterations < 1:
            raise ValueError("iterations must be positive.")
        rate = float(self.relative_learning_rate)
        if not np.isfinite(rate) or rate <= 0.0:
            raise ValueError("relative_learning_rate must be finite and positive.")
        if not isinstance(self.weights, RefinementWeights):
            raise TypeError("weights must be RefinementWeights.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "iterations", iterations)
        object.__setattr__(self, "relative_learning_rate", rate)


def _default_stages() -> tuple[RefinementStage, ...]:
    return (
        RefinementStage(
            "attach",
            60,
            2.0e-3,
            RefinementWeights(fidelity=1.0, anchor=5.0e-2, spectral=1.0e-8),
        ),
        RefinementStage(
            "regularize",
            40,
            8.0e-4,
            RefinementWeights(
                fidelity=1.0,
                anchor=1.0e-2,
                spectral=1.0e-8,
                speed=1.0e-2,
                regularity=5.0e-2,
            ),
        ),
    )


def _default_final_stage() -> RefinementStage:
    return RefinementStage(
        "final_correction",
        20,
        2.0e-4,
        RefinementWeights(fidelity=1.0, spectral=1.0e-8, regularity=1.0e-2),
    )


@dataclass(frozen=True)
class MethodCConfig:
    """All numerical choices for SDF-constrained Fourier refinement."""

    dense_sample_count: int = 256
    validation_sample_count: int = 512
    checkpoint_interval: int = 10
    stages: tuple[RefinementStage, ...] = field(default_factory=_default_stages)
    final_stage: RefinementStage = field(default_factory=_default_final_stage)
    arc_length: ArcLengthConfig = field(default_factory=ArcLengthConfig)
    normalized_fidelity: bool | None = None
    gradient_epsilon: float = 1.0e-12
    spectral_order: int = 2
    speed_floor_ratio: float = 0.2
    regularity_softplus_beta: float = 12.0
    self_neighbour_width: int = 4
    self_distance_floor_ratio: float = 0.0
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1.0e-8
    maximum_gradient_norm: float = 100.0
    minimum_speed_to_mean: float = 1.0e-3
    maximum_anchor_rms_ratio: float = 0.25
    maximum_residual_degradation: float = 1.0e-3
    maximum_speed_ratio_degradation: float = 1.0e-1
    maximum_relative_area_change: float = 5.0e-2
    maximum_relative_perimeter_change: float = 5.0e-2

    def __post_init__(self) -> None:
        for name, minimum in (
            ("dense_sample_count", 32),
            ("validation_sample_count", 32),
            ("checkpoint_interval", 1),
        ):
            if isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be an integer, not bool.")
            try:
                value = operator.index(getattr(self, name))
            except TypeError as exc:
                raise TypeError(f"{name} must be an integer.") from exc
            if value < minimum:
                raise ValueError(f"{name} must be at least {minimum}.")
            object.__setattr__(self, name, value)
        stages = tuple(self.stages)
        if not stages or not all(isinstance(stage, RefinementStage) for stage in stages):
            raise TypeError("stages must contain at least one RefinementStage.")
        if not isinstance(self.final_stage, RefinementStage):
            raise TypeError("final_stage must be a RefinementStage.")
        if not isinstance(self.arc_length, ArcLengthConfig):
            raise TypeError("arc_length must be ArcLengthConfig.")
        if self.normalized_fidelity is not None and not isinstance(
            self.normalized_fidelity, (bool, np.bool_)
        ):
            raise TypeError("normalized_fidelity must be bool or None.")
        if isinstance(self.spectral_order, bool):
            raise TypeError("spectral_order must be an integer, not bool.")
        spectral_order = operator.index(self.spectral_order)
        if spectral_order < 1:
            raise ValueError("spectral_order must be positive.")
        if isinstance(self.self_neighbour_width, bool):
            raise TypeError("self_neighbour_width must be an integer, not bool.")
        neighbour_width = operator.index(self.self_neighbour_width)
        if neighbour_width < 1:
            raise ValueError("self_neighbour_width must be positive.")
        for name in (
            "gradient_epsilon",
            "speed_floor_ratio",
            "regularity_softplus_beta",
            "adam_epsilon",
            "maximum_gradient_norm",
            "minimum_speed_to_mean",
            "maximum_anchor_rms_ratio",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")
            object.__setattr__(self, name, value)
        for name in (
            "self_distance_floor_ratio",
            "maximum_residual_degradation",
            "maximum_speed_ratio_degradation",
            "maximum_relative_area_change",
            "maximum_relative_perimeter_change",
        ):
            value = float(getattr(self, name))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        for name in ("adam_beta1", "adam_beta2"):
            value = float(getattr(self, name))
            if not np.isfinite(value) or not 0.0 < value < 1.0:
                raise ValueError(f"{name} must lie strictly between zero and one.")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "stages", stages)
        object.__setattr__(self, "spectral_order", spectral_order)
        object.__setattr__(self, "self_neighbour_width", neighbour_width)


def _coefficient_matrix(boundary: FourierBoundary) -> np.ndarray:
    return np.vstack(
        (
            boundary.cosine_coefficients[0:1],
            boundary.cosine_coefficients[1:],
            boundary.sine_coefficients[1:],
        )
    ).copy()


def _boundary_from_matrix(template: FourierBoundary, matrix: np.ndarray) -> FourierBoundary:
    bandwidth = template.bandwidth
    expected_shape = (2 * bandwidth + 1, 2)
    values = np.asarray(matrix, dtype=np.float64)
    if values.shape != expected_shape:
        raise ValueError(f"coefficient matrix must have shape {expected_shape}.")
    cosine = np.zeros_like(template.cosine_coefficients)
    sine = np.zeros_like(template.sine_coefficients)
    cosine[0] = values[0]
    cosine[1:] = values[1 : bandwidth + 1]
    sine[1:] = values[bandwidth + 1 :]
    return template.with_coefficients(cosine, sine)


def _basis(parameters: np.ndarray, bandwidth: int) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(parameters, dtype=np.float64).reshape(-1)
    modes = np.arange(1, bandwidth + 1, dtype=np.float64)
    phase = values[:, None] * modes[None, :]
    cosine = np.cos(phase)
    sine = np.sin(phase)
    position = np.concatenate((np.ones((values.size, 1)), cosine, sine), axis=1)
    derivative = np.concatenate(
        (
            np.zeros((values.size, 1)),
            -sine * modes[None, :],
            cosine * modes[None, :],
        ),
        axis=1,
    )
    return position, derivative


def _spectral_weights(bandwidth: int, order: int) -> np.ndarray:
    modes = np.arange(1, bandwidth + 1, dtype=np.float64) ** (2 * order)
    return np.concatenate(([0.0], modes, modes))


def _field_fidelity(
    field: ImplicitField2D,
    points: np.ndarray,
    *,
    normalized: bool,
    gradient_epsilon: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(field.value(points), dtype=np.float64).reshape(-1)
    gradients = np.asarray(field.gradient(points), dtype=np.float64)
    if values.shape != (points.shape[0],) or gradients.shape != points.shape:
        raise ValueError("Implicit field returned incompatible value/gradient shapes.")
    gradient_norm_squared = np.sum(gradients * gradients, axis=1)
    denominators = (
        gradient_norm_squared + gradient_epsilon if normalized else np.ones_like(values)
    )
    normalized_distances = np.abs(values) / (
        np.sqrt(gradient_norm_squared) + np.sqrt(gradient_epsilon)
    )
    return values, gradients, denominators, normalized_distances


def _loss_and_gradient(
    coefficient_matrix: np.ndarray,
    *,
    field: ImplicitField2D,
    dense_basis: np.ndarray,
    dense_derivative_basis: np.ndarray,
    anchor_basis: np.ndarray,
    anchor_points: np.ndarray,
    geometry_scale: float,
    weights: RefinementWeights,
    config: MethodCConfig,
    normalized_fidelity: bool,
) -> tuple[float, np.ndarray, dict[str, float]]:
    """Return the staged objective and its coefficient-space search direction.

    For a generic implicit field, the gradient-normalized fidelity denominator
    is deliberately treated as a stopped quantity.  Differentiating that
    denominator would require the field Hessian, while the public field
    contract intentionally guarantees only ``F`` and ``grad(F)``.  The
    numerator still uses the exact chain rule through the Fourier basis.  The
    same first-derivative-only convention is used for the optional field-normal
    target and is recorded in Method C diagnostics.
    """
    points = dense_basis @ coefficient_matrix
    first = dense_derivative_basis @ coefficient_matrix
    sample_count = points.shape[0]
    scale_squared = geometry_scale**2
    point_gradient = np.zeros_like(points)
    first_gradient = np.zeros_like(first)
    components: dict[str, float] = {}

    field_values, field_gradients, denominators, _ = _field_fidelity(
        field,
        points,
        normalized=normalized_fidelity,
        gradient_epsilon=config.gradient_epsilon,
    )
    fidelity = float(np.mean(field_values**2 / denominators) / scale_squared)
    components["fidelity"] = fidelity
    if weights.fidelity:
        point_gradient += (
            weights.fidelity
            * (2.0 * field_values / denominators)[:, None]
            * field_gradients
            / (sample_count * scale_squared)
        )

    anchored = anchor_basis @ coefficient_matrix
    anchor_delta = anchored - anchor_points
    anchor = float(np.mean(np.sum(anchor_delta**2, axis=1)) / scale_squared)
    components["anchor"] = anchor
    anchor_gradient = (
        weights.anchor
        * 2.0
        * anchor_basis.T
        @ anchor_delta
        / (anchor_points.shape[0] * scale_squared)
    )

    spectral_weights = _spectral_weights(
        (coefficient_matrix.shape[0] - 1) // 2,
        config.spectral_order,
    )
    spectral = float(
        np.sum(spectral_weights[:, None] * coefficient_matrix**2) / scale_squared
    )
    components["spectral"] = spectral
    spectral_gradient = (
        weights.spectral
        * 2.0
        * spectral_weights[:, None]
        * coefficient_matrix
        / scale_squared
    )

    speeds = np.linalg.norm(first, axis=1)
    speed_safeguard = np.sqrt(config.gradient_epsilon)
    safe_speeds = np.maximum(speeds, speed_safeguard)
    speed_active = speeds > speed_safeguard
    mean_speed = float(np.mean(safe_speeds))
    speed_denominator = mean_speed**2 + config.gradient_epsilon
    mean_square_speed = float(np.mean(safe_speeds**2))
    speed_variance = max(0.0, mean_square_speed - mean_speed**2)
    speed_loss = speed_variance / speed_denominator
    components["speed"] = speed_loss
    if weights.speed and speed_variance > 0.0:
        variance_derivative = 2.0 * (safe_speeds - mean_speed) / sample_count
        denominator_derivative = 2.0 * mean_speed / sample_count
        derivative_speed = (
            variance_derivative * speed_denominator
            - speed_variance * denominator_derivative
        ) / speed_denominator**2
        first_gradient += (
            weights.speed
            * derivative_speed[:, None]
            * first
            / safe_speeds[:, None]
            * speed_active[:, None]
        )

    regularity_denominator = mean_speed + speed_safeguard
    speed_ratio = safe_speeds / regularity_denominator
    z = config.speed_floor_ratio - speed_ratio
    beta = config.regularity_softplus_beta
    softplus = np.logaddexp(0.0, beta * z) / beta
    regularity = float(np.mean(softplus**2))
    components["regularity"] = regularity
    if weights.regularity:
        derivative_z = 2.0 * softplus * expit(beta * z) / sample_count
        derivative_speed = (
            -derivative_z / regularity_denominator
            + np.sum(derivative_z * safe_speeds)
            / (sample_count * regularity_denominator**2)
        )
        first_gradient += (
            weights.regularity
            * derivative_speed[:, None]
            * first
            / safe_speeds[:, None]
            * speed_active[:, None]
        )

    normal_loss = 0.0
    if weights.normal:
        sign = str(getattr(field, "sign_convention", "unspecified"))
        if sign not in {"negative_inside", "positive_inside"}:
            raise ValueError("Normal agreement requires an explicit field sign convention.")
        gradient_norms = np.linalg.norm(field_gradients, axis=1)
        field_normals = field_gradients / np.maximum(
            gradient_norms[:, None], np.sqrt(config.gradient_epsilon)
        )
        if sign == "positive_inside":
            field_normals = -field_normals
        curve_normals = np.column_stack((first[:, 1], -first[:, 0])) / safe_speeds[:, None]
        alignment = np.sum(curve_normals * field_normals, axis=1)
        normal_loss = float(np.mean((1.0 - alignment) ** 2))
        rotated_target = np.column_stack((-field_normals[:, 1], field_normals[:, 0]))
        alignment_gradient = (
            rotated_target / safe_speeds[:, None]
            - alignment[:, None] * first / safe_speeds[:, None] ** 2
        )
        first_gradient += (
            weights.normal
            * (-2.0 * (1.0 - alignment) / sample_count)[:, None]
            * alignment_gradient
        )
    components["normal"] = normal_loss

    self_loss = 0.0
    if weights.self_distance and config.self_distance_floor_ratio > 0.0:
        indices = np.arange(sample_count)
        cyclic_separation = np.minimum(
            (indices[:, None] - indices[None, :]) % sample_count,
            (indices[None, :] - indices[:, None]) % sample_count,
        )
        pair_i, pair_j = np.where(
            np.triu(cyclic_separation > config.self_neighbour_width, k=1)
        )
        if pair_i.size:
            delta = points[pair_i] - points[pair_j]
            distance = np.linalg.norm(delta, axis=1)
            mean_step = mean_speed * 2.0 * np.pi / sample_count
            mean_step_derivative = 2.0 * np.pi / sample_count
            floor_distance = (
                config.self_distance_floor_ratio
                * (config.self_neighbour_width + 1)
                * mean_step
            )
            distance_scale = max(mean_step, speed_safeguard)
            violation = np.maximum(floor_distance - distance, 0.0)
            self_loss = float(np.mean((violation / distance_scale) ** 2))
            active = violation > 0.0
            if np.any(active):
                derivative_distance = np.zeros_like(distance)
                derivative_distance[active] = (
                    -2.0
                    * violation[active]
                    / (pair_i.size * distance_scale**2)
                )
                pair_gradient = (
                    derivative_distance[:, None]
                    * delta
                    / np.maximum(distance[:, None], np.sqrt(config.gradient_epsilon))
                )
                np.add.at(point_gradient, pair_i, weights.self_distance * pair_gradient)
                np.add.at(point_gradient, pair_j, -weights.self_distance * pair_gradient)

                # The barrier's floor, and normally its normalization, scale
                # with mean speed.  Include that coefficient dependence rather
                # than differentiating only pair positions.
                floor_derivative = (
                    config.self_distance_floor_ratio
                    * (config.self_neighbour_width + 1)
                    * mean_step_derivative
                )
                scale_derivative = (
                    mean_step_derivative if mean_step > speed_safeguard else 0.0
                )
                normalized_violation = violation[active] / distance_scale
                normalized_derivative = (
                    floor_derivative / distance_scale
                    - violation[active] * scale_derivative / distance_scale**2
                )
                loss_derivative_mean_speed = float(
                    2.0
                    * np.sum(normalized_violation * normalized_derivative)
                    / pair_i.size
                )
                first_gradient += (
                    weights.self_distance
                    * loss_derivative_mean_speed
                    / sample_count
                    * first
                    / safe_speeds[:, None]
                    * speed_active[:, None]
                )
    components["self_distance"] = self_loss

    total = (
        weights.fidelity * fidelity
        + weights.anchor * anchor
        + weights.spectral * spectral
        + weights.speed * speed_loss
        + weights.regularity * regularity
        + weights.normal * normal_loss
        + weights.self_distance * self_loss
    )
    coefficient_gradient = (
        dense_basis.T @ point_gradient
        + dense_derivative_basis.T @ first_gradient
        + anchor_gradient
        + spectral_gradient
    )
    components["total"] = float(total)
    components["minimum_speed"] = float(np.min(speeds))
    components["mean_speed"] = mean_speed
    return float(total), coefficient_gradient, components


def _fidelity_summary(
    field: ImplicitField2D,
    boundary: FourierBoundary,
    *,
    sample_count: int,
    gradient_epsilon: float,
) -> dict[str, float]:
    parameters = 2.0 * np.pi * np.arange(sample_count, dtype=np.float64) / sample_count
    points = boundary.position(parameters)
    values, _, _, normalized = _field_fidelity(
        field,
        points,
        normalized=True,
        gradient_epsilon=gradient_epsilon,
    )
    return {
        "raw_max": float(np.max(np.abs(values))),
        "raw_rms": float(np.sqrt(np.mean(values**2))),
        "normalized_max": float(np.max(normalized)),
        "normalized_rms": float(np.sqrt(np.mean(normalized**2))),
    }


def _integral_geometry_summary(
    boundary: FourierBoundary,
    *,
    sample_count: int,
) -> dict[str, float]:
    """Return dense signed area and perimeter for acceptance drift checks."""

    parameters = 2.0 * np.pi * np.arange(sample_count, dtype=np.float64) / sample_count
    points = boundary.position(parameters)
    first = boundary.derivative(parameters, 1)
    step = 2.0 * np.pi / sample_count
    cross = points[:, 0] * first[:, 1] - points[:, 1] * first[:, 0]
    return {
        "signed_area": float(0.5 * step * np.sum(cross)),
        "perimeter": float(step * np.sum(np.linalg.norm(first, axis=1))),
    }


def _relative_change(candidate: float, baseline: float) -> float:
    denominator = max(abs(float(baseline)), np.finfo(np.float64).tiny)
    return abs(float(candidate) - float(baseline)) / denominator


def _minimum_nonlocal_sample_distance(
    points: np.ndarray,
    *,
    neighbour_width: int,
) -> float | None:
    """Return a dense point-pair clearance excluding cyclic neighbours."""

    values = np.asarray(points, dtype=np.float64)
    count = values.shape[0]
    indices = np.arange(count)
    separation = np.abs(indices[:, None] - indices[None, :])
    cyclic_separation = np.minimum(separation, count - separation)
    nonlocal_mask = cyclic_separation > neighbour_width
    if not np.any(nonlocal_mask):
        return None
    distances = np.linalg.norm(values[:, None, :] - values[None, :, :], axis=-1)
    return float(np.min(distances[nonlocal_mask]))


def _component_anchor_set_summary(
    boundary: FourierBoundary,
    anchor_points: np.ndarray,
    *,
    sample_count: int,
) -> dict[str, float]:
    """Compare the final curve with the discovered projected loop setwise."""

    parameters = 2.0 * np.pi * np.arange(sample_count, dtype=np.float64) / sample_count
    candidate_points = boundary.position(parameters)
    candidate_to_anchor = cKDTree(anchor_points).query(candidate_points, k=1)[0]
    anchor_to_candidate = cKDTree(candidate_points).query(anchor_points, k=1)[0]
    first_mean_square = float(np.mean(candidate_to_anchor**2))
    second_mean_square = float(np.mean(anchor_to_candidate**2))
    return {
        "candidate_to_anchor_max": float(np.max(candidate_to_anchor)),
        "candidate_to_anchor_rms": float(np.sqrt(first_mean_square)),
        "anchor_to_candidate_max": float(np.max(anchor_to_candidate)),
        "anchor_to_candidate_rms": float(np.sqrt(second_mean_square)),
        "symmetric_hausdorff": float(
            max(np.max(candidate_to_anchor), np.max(anchor_to_candidate))
        ),
        "symmetric_rms": float(
            np.sqrt(0.5 * (first_mean_square + second_mean_square))
        ),
    }


def _validate_candidate(
    field: ImplicitField2D,
    boundary: FourierBoundary,
    *,
    config: MethodCConfig,
) -> tuple[bool, Any, dict[str, Any]]:
    parameterization = boundary.to_parameterization()
    report = validate_periodic_parameterization(
        parameterization,
        BoundaryValidationConfig(num_samples_per_component=config.validation_sample_count),
    )
    parameters = (
        2.0
        * np.pi
        * np.arange(config.validation_sample_count, dtype=np.float64)
        / config.validation_sample_count
    )
    speeds = np.linalg.norm(boundary.derivative(parameters, 1), axis=1)
    speed_to_mean = float(np.min(speeds) / np.mean(speeds))
    speed_ratio = float(np.max(speeds) / np.min(speeds))
    points = boundary.position(parameters)
    minimum_nonlocal_distance = _minimum_nonlocal_sample_distance(
        points,
        neighbour_width=config.self_neighbour_width,
    )
    fidelity = _fidelity_summary(
        field,
        boundary,
        sample_count=config.validation_sample_count,
        gradient_epsilon=config.gradient_epsilon,
    )
    fidelity["minimum_speed_to_mean"] = speed_to_mean
    fidelity["speed_ratio"] = speed_ratio
    fidelity["self_intersection_count"] = int(report.self_intersection_count)
    fidelity["minimum_nonlocal_sample_distance"] = minimum_nonlocal_distance
    return report.valid and speed_to_mean >= config.minimum_speed_to_mean, report, fidelity


def _run_stage(
    initial_matrix: np.ndarray,
    *,
    template: FourierBoundary,
    field: ImplicitField2D,
    stage: RefinementStage,
    dense_basis: np.ndarray,
    dense_derivative_basis: np.ndarray,
    anchor_basis: np.ndarray,
    anchor_points: np.ndarray,
    geometry_scale: float,
    config: MethodCConfig,
    normalized_fidelity: bool,
    history: list[dict[str, Any]],
) -> tuple[np.ndarray, float]:
    """Run one stage and return its lowest weighted-loss valid checkpoint.

    Stage objectives can have different weights, so scores are intentionally
    compared only within a stage.  The selected checkpoint becomes the start
    of the next stage; there is no invalid cross-stage comparison of unlike
    objectives.
    """

    matrix = initial_matrix.copy()
    best_matrix = matrix.copy()
    initial_boundary = _boundary_from_matrix(template, matrix)
    initial_valid, initial_report, initial_fidelity = _validate_candidate(
        field, initial_boundary, config=config
    )
    initial_loss, _, initial_components = _loss_and_gradient(
        matrix,
        field=field,
        dense_basis=dense_basis,
        dense_derivative_basis=dense_derivative_basis,
        anchor_basis=anchor_basis,
        anchor_points=anchor_points,
        geometry_scale=geometry_scale,
        weights=stage.weights,
        config=config,
        normalized_fidelity=normalized_fidelity,
    )
    history.append(
        {
            "event": "stage_start",
            "stage": stage.name,
            "iteration": 0,
            "valid": bool(initial_valid),
            "issues": tuple(initial_report.issues),
            "selection_metric": "weighted_stage_total",
            "components": initial_components,
            "geometry": initial_fidelity,
        }
    )
    if not initial_valid:
        raise ValueError(
            f"Stage {stage.name} received an initializer that failed validation: "
            + "; ".join(initial_report.issues)
        )
    best_score = initial_loss
    first_moment = np.zeros_like(matrix)
    second_moment = np.zeros_like(matrix)

    for iteration in range(1, stage.iterations + 1):
        loss_before_update, gradient, components_before_update = _loss_and_gradient(
            matrix,
            field=field,
            dense_basis=dense_basis,
            dense_derivative_basis=dense_derivative_basis,
            anchor_basis=anchor_basis,
            anchor_points=anchor_points,
            geometry_scale=geometry_scale,
            weights=stage.weights,
            config=config,
            normalized_fidelity=normalized_fidelity,
        )
        gradient_norm = float(np.linalg.norm(gradient))
        if not np.isfinite(gradient_norm):
            raise FloatingPointError(f"Stage {stage.name} produced a non-finite gradient.")
        applied_gradient_norm = gradient_norm
        if gradient_norm > config.maximum_gradient_norm:
            gradient *= config.maximum_gradient_norm / gradient_norm
            applied_gradient_norm = config.maximum_gradient_norm
        first_moment = config.adam_beta1 * first_moment + (1.0 - config.adam_beta1) * gradient
        second_moment = config.adam_beta2 * second_moment + (1.0 - config.adam_beta2) * gradient**2
        corrected_first = first_moment / (1.0 - config.adam_beta1**iteration)
        corrected_second = second_moment / (1.0 - config.adam_beta2**iteration)
        matrix -= (
            stage.relative_learning_rate
            * geometry_scale
            * corrected_first
            / (np.sqrt(corrected_second) + config.adam_epsilon)
        )

        should_checkpoint = (
            iteration == 1
            or iteration == stage.iterations
            or iteration % config.checkpoint_interval == 0
        )
        history_entry: dict[str, Any] = {
            "event": "optimizer_step",
            "stage": stage.name,
            "iteration": iteration,
            "loss_before_update": loss_before_update,
            "components_before_update": components_before_update,
            "gradient_norm_before_clipping": gradient_norm,
            "applied_gradient_norm": applied_gradient_norm,
            "checkpoint": bool(should_checkpoint),
        }
        if should_checkpoint:
            candidate = _boundary_from_matrix(template, matrix)
            valid, report, fidelity = _validate_candidate(field, candidate, config=config)
            checkpoint_loss, _, checkpoint_components = _loss_and_gradient(
                matrix,
                field=field,
                dense_basis=dense_basis,
                dense_derivative_basis=dense_derivative_basis,
                anchor_basis=anchor_basis,
                anchor_points=anchor_points,
                geometry_scale=geometry_scale,
                weights=stage.weights,
                config=config,
                normalized_fidelity=normalized_fidelity,
            )
            history_entry["checkpoint_result"] = {
                "valid": bool(valid),
                "issues": tuple(report.issues),
                "selection_metric": "weighted_stage_total",
                "selection_score": checkpoint_loss,
                "components": checkpoint_components,
                "geometry": fidelity,
            }
            if valid and checkpoint_loss < best_score:
                best_score = checkpoint_loss
                best_matrix = matrix.copy()
                history_entry["checkpoint_result"]["selected"] = True
            else:
                history_entry["checkpoint_result"]["selected"] = False
            history.append(history_entry)
            if not valid:
                break
        else:
            history.append(history_entry)
    return best_matrix, best_score


def fit_method_c(
    field: ImplicitField2D,
    frontend: Any,
    method_b: BoundaryMethodResult,
    *,
    config: MethodCConfig | None = None,
) -> BoundaryMethodResult:
    """Refine a valid Method-B Fourier curve, with explicit fallback to B."""

    settings = MethodCConfig() if config is None else config
    if not isinstance(settings, MethodCConfig):
        raise TypeError("config must be MethodCConfig.")
    if method_b.parameterization is None or not isinstance(
        method_b.representation, FourierBoundary
    ):
        raise TypeError("Method C requires a Method-B result with FourierBoundary coefficients.")
    if method_b.status != "success" or method_b.validation is None or not method_b.validation.valid:
        raise ValueError("Method C requires a successful, valid Method-B initializer.")

    parameters = np.asarray(frontend.parameters, dtype=np.float64)
    projected_points = np.asarray(frontend.projected_points, dtype=np.float64)
    if parameters.ndim != 1 or projected_points.shape != (parameters.size, 2):
        raise ValueError("frontend must expose matching one-dimensional parameters and points.")
    template = method_b.representation
    bandwidth = template.bandwidth
    dense_parameters = (
        2.0
        * np.pi
        * np.arange(settings.dense_sample_count, dtype=np.float64)
        / settings.dense_sample_count
    )
    dense_basis, dense_derivative_basis = _basis(dense_parameters, bandwidth)
    anchor_basis, _ = _basis(parameters, bandwidth)
    center = np.mean(projected_points, axis=0)
    geometry_scale = max(
        float(np.max(np.linalg.norm(projected_points - center, axis=1))),
        np.finfo(float).tiny,
    )
    normalized_fidelity = (
        not bool(getattr(field, "is_signed_distance", False))
        if settings.normalized_fidelity is None
        else bool(settings.normalized_fidelity)
    )
    initial_matrix = _coefficient_matrix(template)
    history: list[dict[str, Any]] = []
    started = time.perf_counter()

    try:
        baseline_valid, baseline_validation, baseline_fidelity = _validate_candidate(
            field,
            template,
            config=settings,
        )
        baseline_integral_geometry = _integral_geometry_summary(
            template,
            sample_count=settings.validation_sample_count,
        )
        history.append(
            {
                "event": "method_b_initializer",
                "stage": "method_b_initializer",
                "iteration": 0,
                "valid": bool(baseline_valid),
                "issues": tuple(baseline_validation.issues),
                "geometry": baseline_fidelity,
            }
        )
        if not baseline_valid:
            raise ValueError(
                "Method-B initializer failed Method-C validation: "
                + "; ".join(baseline_validation.issues)
            )
        current = initial_matrix.copy()
        stage_selection: list[dict[str, Any]] = []
        for stage in settings.stages:
            current, stage_score = _run_stage(
                current,
                template=template,
                field=field,
                stage=stage,
                dense_basis=dense_basis,
                dense_derivative_basis=dense_derivative_basis,
                anchor_basis=anchor_basis,
                anchor_points=projected_points,
                geometry_scale=geometry_scale,
                config=settings,
                normalized_fidelity=normalized_fidelity,
                history=history,
            )
            stage_selection.append(
                {
                    "stage": stage.name,
                    "selection_metric": "weighted_stage_total",
                    "selected_score": stage_score,
                }
            )

        refined_before_arc = _boundary_from_matrix(template, current).with_provenance(
            CurveProvenance2D(source_kind="sdf_refined_fourier")
        )

        def refit_factory(uniform_parameters: np.ndarray, points: np.ndarray) -> FourierBoundary:
            return fit_fourier_least_squares(
                uniform_parameters,
                points,
                bandwidth=bandwidth,
                component_id=template.component_id,
                name="sdf_refined_fourier_arclength",
                provenance=CurveProvenance2D(source_kind="sdf_refined_fourier_arclength"),
            ).boundary

        output_n = (
            settings.arc_length.refit_sample_count
            if settings.arc_length.refit_sample_count is not None
            else max(projected_points.shape[0], 2 * bandwidth + 1)
        )
        arc_result = reparameterize_by_arclength(
            refined_before_arc,
            refit_factory,
            dense_n=settings.arc_length.dense_resolution,
            output_n=output_n,
            validation_n=settings.arc_length.validation_resolution,
        )
        arc_boundary = arc_result.representation
        assert isinstance(arc_boundary, FourierBoundary)

        final_anchor_parameters = (
            2.0
            * np.pi
            * np.arange(output_n, dtype=np.float64)
            / output_n
        )
        final_anchor_points = arc_boundary.position(final_anchor_parameters)
        final_anchor_basis, _ = _basis(final_anchor_parameters, bandwidth)
        final_best, final_score = _run_stage(
            _coefficient_matrix(arc_boundary),
            template=arc_boundary,
            field=field,
            stage=settings.final_stage,
            dense_basis=dense_basis,
            dense_derivative_basis=dense_derivative_basis,
            anchor_basis=final_anchor_basis,
            anchor_points=final_anchor_points,
            geometry_scale=geometry_scale,
            config=settings,
            normalized_fidelity=normalized_fidelity,
            history=history,
        )
        final_boundary = _boundary_from_matrix(arc_boundary, final_best).with_provenance(
            CurveProvenance2D(source_kind="sdf_refined_fourier_final")
        )
        final_valid, final_validation, final_fidelity = _validate_candidate(
            field, final_boundary, config=settings
        )
        final_integral_geometry = _integral_geometry_summary(
            final_boundary,
            sample_count=settings.validation_sample_count,
        )
        relative_area_change = _relative_change(
            final_integral_geometry["signed_area"],
            baseline_integral_geometry["signed_area"],
        )
        relative_perimeter_change = _relative_change(
            final_integral_geometry["perimeter"],
            baseline_integral_geometry["perimeter"],
        )
        final_points_at_anchor = final_boundary.position(final_anchor_parameters)
        final_correction_anchor_rms = float(
            np.sqrt(np.mean(np.sum((final_points_at_anchor - final_anchor_points) ** 2, axis=1)))
        )
        component_anchor_set = _component_anchor_set_summary(
            final_boundary,
            projected_points,
            sample_count=settings.validation_sample_count,
        )
        maximum_residual_limit = (
            baseline_fidelity["normalized_max"]
            * (1.0 + settings.maximum_residual_degradation)
            + np.finfo(float).eps * geometry_scale
        )
        rms_residual_limit = (
            baseline_fidelity["normalized_rms"]
            * (1.0 + settings.maximum_residual_degradation)
            + np.finfo(float).eps * geometry_scale
        )
        speed_ratio_limit = baseline_fidelity["speed_ratio"] * (
            1.0 + settings.maximum_speed_ratio_degradation
        )
        accepted = (
            final_valid
            and final_fidelity["normalized_max"] <= maximum_residual_limit
            and final_fidelity["normalized_rms"] <= rms_residual_limit
            and component_anchor_set["symmetric_rms"]
            <= settings.maximum_anchor_rms_ratio * geometry_scale
            and final_fidelity["speed_ratio"] <= speed_ratio_limit
            and relative_area_change <= settings.maximum_relative_area_change
            and relative_perimeter_change
            <= settings.maximum_relative_perimeter_change
        )
        runtime = time.perf_counter() - started
        diagnostics: dict[str, Any] = {
            "bandwidth": bandwidth,
            "normalized_fidelity": normalized_fidelity,
            "field_second_derivative_policy": "stop_gradient",
            "geometry_scale": geometry_scale,
            "initial_coefficients": initial_matrix.tolist(),
            "pre_arc_stage_selection": tuple(stage_selection),
            "final_best_score": final_score,
            "baseline_fidelity": baseline_fidelity,
            "final_fidelity": final_fidelity,
            "baseline_integral_geometry": baseline_integral_geometry,
            "final_integral_geometry": final_integral_geometry,
            "relative_area_change_from_method_b": relative_area_change,
            "relative_perimeter_change_from_method_b": relative_perimeter_change,
            "component_anchor_set": component_anchor_set,
            "final_correction_anchor_rms": final_correction_anchor_rms,
            "history": tuple(history),
            "config": asdict(settings),
        }
        if arc_result is not None:
            diagnostics["attempted_arc_length"] = asdict(arc_result.diagnostics)
        if not accepted:
            reasons = []
            if not final_valid:
                reasons.append("final checkpoint failed continuous geometry validation")
            if (
                final_fidelity["normalized_max"] > maximum_residual_limit
                or final_fidelity["normalized_rms"] > rms_residual_limit
            ):
                reasons.append(
                    "final normalized max/RMS SDF residual was worse than Method B"
                )
            if (
                component_anchor_set["symmetric_rms"]
                > settings.maximum_anchor_rms_ratio * geometry_scale
            ):
                reasons.append("final curve drifted beyond the configured component anchor")
            if final_fidelity["speed_ratio"] > speed_ratio_limit:
                reasons.append(
                    "final speed ratio degraded beyond the configured Method-B envelope"
                )
            if relative_area_change > settings.maximum_relative_area_change:
                reasons.append("final area drifted beyond the configured Method-B envelope")
            if relative_perimeter_change > settings.maximum_relative_perimeter_change:
                reasons.append(
                    "final perimeter drifted beyond the configured Method-B envelope"
                )
            return BoundaryMethodResult(
                method_name="method_c_sdf_refined_fourier",
                status="fallback",
                representation=template,
                parameterization=method_b.parameterization,
                validation=method_b.validation,
                input_fit_residual=method_b.input_fit_residual,
                arc_length=method_b.arc_length,
                runtime_seconds=runtime,
                diagnostics=diagnostics,
                failure_reason="; ".join(reasons) or "refinement was not accepted",
            )
        return BoundaryMethodResult(
            method_name="method_c_sdf_refined_fourier",
            status="success",
            representation=final_boundary,
            parameterization=final_boundary.to_parameterization(),
            validation=final_validation,
            input_fit_residual=method_b.input_fit_residual,
            arc_length=arc_result.diagnostics,
            runtime_seconds=runtime,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        runtime = time.perf_counter() - started
        return BoundaryMethodResult(
            method_name="method_c_sdf_refined_fourier",
            status="fallback",
            representation=template,
            parameterization=method_b.parameterization,
            validation=method_b.validation,
            input_fit_residual=method_b.input_fit_residual,
            arc_length=method_b.arc_length,
            runtime_seconds=runtime,
            diagnostics={
                "bandwidth": bandwidth,
                "field_second_derivative_policy": "stop_gradient",
                "initial_coefficients": initial_matrix.tolist(),
                "history": tuple(history),
                "config": asdict(settings),
            },
            failure_reason=f"coefficient refinement failed: {type(exc).__name__}: {exc}",
        )


__all__ = [
    "MethodCConfig",
    "RefinementStage",
    "RefinementWeights",
    "fit_method_c",
]
