"""Opt-in frozen neural-feature metrics on a declared radial Fourier chart.

The physics/canonical state stays an explicit curve. A neural metric is built
once on a numerically verified initial zero set, then frozen. It is not a
learned field, a direct neural zero-set reconstruction, or an SDF requirement.
The current geometric-circle MLP initialization activates only its output head.

If H maps coefficient increments to normal motion, W contains arc weights,
and B=-partial_theta(phi)/|grad(phi)|, T=(H^T W H)^-1 H^T W B projects the
neural normal map into the chart. E supplies a discrete coefficient covector
g; descent is -T T^T g, with NO further quadrature weights on g. We compare
metrics after mass whitening, trace normalization and a common eigenvalue
floor. No arbitrary normal-gradient density is reconstructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import Mapping

import numpy as np
import torch

from gpr_bem_kress.shape_derivative import KressDirection
from ordered_boundary import PeriodicCurve2D

from .curve_updates import radial_fourier_displacement_basis
from .neural import SmoothMLPSDF2D


def _readonly(value):
    result = np.array(value, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError("Metric arrays must be finite.")
    result.setflags(write=False)
    return result


def _inverse_sqrt(matrix):
    values, vectors = np.linalg.eigh(matrix)
    if values[-1] <= 0 or values[0] <= np.finfo(float).eps * float(values[-1]):
        raise ValueError("The normal-displacement chart mass matrix is singular.")
    return (vectors / np.sqrt(values)) @ vectors.T


def _normalized(matrix, floor):
    values, vectors = np.linalg.eigh((matrix + matrix.T) / 2.0)
    if values[0] < -1e-10 * max(float(values[-1]), np.finfo(float).tiny):
        raise ValueError("The proposed update metric is not positive semidefinite.")
    values = np.maximum(values, 0.0)
    if np.sum(values) <= np.finfo(float).tiny:
        raise ValueError("The proposed update metric has no nonzero direction.")
    # Convex mixing with identity preserves trace=d and gives lambda_min>=floor.
    values = (1.0-floor) * matrix.shape[0] * values / np.sum(values) + floor
    return (vectors * values) @ vectors.T, values


def radial_chart_directions(parameters, maximum_mode):
    """Exact point/first/second/third jets of each fixed-polar-angle control.

    Radius modes 0,2..K and Cartesian translations replace the radial mode-one
    gauge. Native period is 2*pi, as required by RadialFourierCurveState.
    No finite differences, interpolation or normal-field surrogates are used.
    """
    angles = np.asarray(parameters, dtype=np.float64)
    basis = radial_fourier_displacement_basis(angles, maximum_mode=maximum_mode)
    count = basis.shape[-2]
    jets = [basis]
    for order in (1, 2, 3):
        radial = np.column_stack((np.cos(angles + order*np.pi/2), np.sin(angles + order*np.pi/2)))
        values = np.zeros_like(basis)
        values[:, 0, :] = radial
        for mode in range(2, maximum_mode+1):
            # Product-to-sum differentiates radius harmonic * (cos t,sin t).
            plus, minus = mode+1, mode-1
            cp = plus**order*np.cos(plus*angles + order*np.pi/2)
            sp = plus**order*np.sin(plus*angles + order*np.pi/2)
            cm = minus**order*np.cos(minus*angles + order*np.pi/2)
            sm = minus**order*np.sin(minus*angles + order*np.pi/2)
            values[:, 2*mode-1, :] = .5*np.column_stack((cp+cm, sp-sm))
            values[:, 2*mode, :] = .5*np.column_stack((sp+sm, cm-cp))
        jets.append(values)
    return tuple(KressDirection(*(jet[:, index, :] for jet in jets)) for index in range(count))


@dataclass(frozen=True)
class FrozenCurveMetric:
    """Frozen initial geometry/feature covariance; active prefixes are explicit."""

    kind: str
    maximum_mode: int
    mass_matrix: np.ndarray
    normal_feature_covariance: np.ndarray | None
    eigenvalue_floor: float
    sobolev_angular_length: float
    diagnostics: Mapping[str, object]

    def _active_raw(self, maximum_mode):
        mode = self.maximum_mode if maximum_mode is None else maximum_mode
        if isinstance(mode, bool) or int(mode) != mode or not 1 <= mode <= self.maximum_mode:
            raise ValueError("active maximum_mode must be an integer within the frozen chart.")
        size = 1 + 2*int(mode)
        mass = self.mass_matrix[:size, :size]
        inverse_sqrt = _inverse_sqrt(mass)
        if self.kind == "neural":
            raw = inverse_sqrt @ self.normal_feature_covariance[:size, :size] @ inverse_sqrt
        elif self.kind == "sobolev":
            orders = np.r_[0, np.repeat(np.arange(1, int(mode)+1), 2)]
            raw = np.diag(1.0 / (1.0 + (self.sobolev_angular_length*orders)**2))
        else:
            raw = np.eye(size)
        return inverse_sqrt, raw

    def active_matrices(self, maximum_mode=None):
        """Return coefficient metric, mass-whitened metric and its eigenvalues.

        Each active prefix is projected and normalized independently on the
        same frozen initial geometry; no inactive-mode cross terms leak in.
        """
        inverse_sqrt, raw = self._active_raw(maximum_mode)
        whitened, eigenvalues = _normalized(raw, self.eigenvalue_floor)
        coefficient = inverse_sqrt @ whitened @ inverse_sqrt
        return _readonly(coefficient), _readonly(whitened), _readonly(eigenvalues)

    def active_diagnostics(self, maximum_mode=None):
        """Expose raw spectrum separately from the common floor/normalization."""
        _, raw = self._active_raw(maximum_mode)
        raw_values = np.linalg.eigvalsh((raw+raw.T)/2)
        _, values = _normalized(raw, self.eigenvalue_floor)
        return {
            "raw_whitened_eigenvalues": raw_values.tolist(),
            "raw_whitened_rank": int(np.linalg.matrix_rank(raw)),
            "normalized_whitened_eigenvalues": values.tolist(),
            "normalized_whitened_trace": float(np.sum(values)),
            "normalized_whitened_condition": float(values[-1]/values[0]),
            "isotropic_floor_trace_fraction": self.eigenvalue_floor,
        }

    def descent_direction(self, gradient, *, maximum_mode=None):
        """Apply the frozen coefficient metric to an already-discrete covector."""
        matrix, _, _ = self.active_matrices(maximum_mode)
        if np.iscomplexobj(gradient):
            raise ValueError("gradient must be real-valued.")
        values = np.asarray(gradient, dtype=np.float64)
        if values.shape != (matrix.shape[0],) or not np.all(np.isfinite(values)):
            raise ValueError("gradient must be a finite active coefficient covector.")
        return _readonly(-matrix @ values)

    def covector_norm(self, gradient, *, maximum_mode=None, curve=None):
        size = len(gradient)
        if maximum_mode is not None and size != 1+2*maximum_mode:
            raise ValueError("gradient and active mode disagree.")
        self.descent_direction(gradient, maximum_mode=maximum_mode)
        mass = self.mass_matrix[:size, :size]
        if curve is not None:
            basis = radial_fourier_displacement_basis(curve.parameters, maximum_mode=(size-1)//2)
            normal_basis = np.einsum("npd,nd->np", basis, curve.normals)
            mass = normal_basis.T @ (curve.arc_length_weights[:, None]*normal_basis)
            _inverse_sqrt(mass)
        # Same identity mass norm for every arm: not a metric-dependent stop.
        return float(np.sqrt(max(0.0, np.dot(gradient, np.linalg.solve(mass, gradient)))))


def build_frozen_curve_metric(
    curve: PeriodicCurve2D,
    *,
    maximum_mode=5,
    kind="identity",
    model: SmoothMLPSDF2D | None = None,
    eigenvalue_floor=1e-3,
    sobolev_angular_length=.35,
    zero_set_tolerance_m=1e-10,
) -> FrozenCurveMetric:
    """Build one fair-comparison metric without training or changing the model.

    For neural mode, every parameter Jacobian column is evaluated and active
    columns counted explicitly. Only a regular, node-verified initial zero set
    is accepted. The bounded experiment uses the model's exact geometric circle
    initialization, so that this is not an approximate MLP contour substitution.
    """
    started = perf_counter()
    if not isinstance(curve, PeriodicCurve2D) or not np.isclose(curve.period, 2*np.pi, rtol=0, atol=1e-13):
        raise ValueError("A 2*pi-periodic canonical curve is required.")
    if kind not in ("identity", "sobolev", "neural"):
        raise ValueError("kind must be identity, sobolev or neural.")
    if not np.isfinite(eigenvalue_floor) or not 0 < eigenvalue_floor < 1:
        raise ValueError("eigenvalue_floor must lie strictly between zero and one.")
    if not np.isfinite(sobolev_angular_length) or sobolev_angular_length <= 0:
        raise ValueError("sobolev_angular_length must be positive and finite.")
    if not np.isfinite(zero_set_tolerance_m) or zero_set_tolerance_m <= 0:
        raise ValueError("zero_set_tolerance_m must be positive and finite.")
    vectors = radial_fourier_displacement_basis(curve.parameters, maximum_mode=maximum_mode)
    normal_basis = np.einsum("npd,nd->np", vectors, curve.normals)
    weights = curve.arc_length_weights
    mass = normal_basis.T @ (weights[:, None] * normal_basis)
    _inverse_sqrt(mass)
    covariance = None
    diagnostics = {
        "kind": kind, "frozen_at_initial_curve": True,
        "model_training_steps": 0, "model_queries_after_initialization": 0,
        "parameter_count": None, "active_parameter_columns": None,
        "normal_map_projection_relative_error": None,
        "maximum_initial_field_residual_m": None,
        "minimum_initial_spatial_gradient_norm": None,
        "maximum_initial_spatial_gradient_norm": None,
        "model_jacobian_seconds": None, "model_jacobian_bytes": None,
        "model_initialization": None,
        "gradient_contract": "discrete coefficient covector; no additional arc weights",
    }
    if kind == "neural":
        if not isinstance(model, SmoothMLPSDF2D):
            raise TypeError("neural metric requires a SmoothMLPSDF2D.")
        jacobian_started = perf_counter()
        points = torch.tensor(np.array(curve.points), dtype=model.coordinate_center.dtype,
                              device=model.coordinate_center.device, requires_grad=True)
        values = model(points)
        gradient = torch.autograd.grad(values.sum(), points, retain_graph=True)[0]
        lengths = torch.linalg.vector_norm(gradient, dim=1).detach().cpu().numpy()
        maximum_residual = float(values.detach().abs().max().cpu())
        if not np.all(np.isfinite(lengths)) or np.min(lengths) <= 1e-8:
            raise ValueError("The neural initial zero set is not regular.")
        if maximum_residual > zero_set_tolerance_m:
            raise ValueError("The neural field does not match the initial canonical zero set.")
        parameters = tuple(model.parameters())
        rows = []
        for value in values[:, 0]:
            derivatives = torch.autograd.grad(value, parameters, retain_graph=True)
            rows.append(torch.cat([array.reshape(-1) for array in derivatives]).detach().cpu().numpy())
        jacobian = np.asarray(rows)
        normal_map = -jacobian / lengths[:, None]
        weighted_projection = normal_basis.T @ (weights[:, None] * normal_map)
        coefficients = np.linalg.solve(mass, weighted_projection)
        error = np.sqrt(weights)[:, None] * (normal_basis @ coefficients - normal_map)
        denominator = np.linalg.norm(np.sqrt(weights)[:, None] * normal_map)
        covariance = weighted_projection @ weighted_projection.T
        diagnostics.update(
            parameter_count=int(jacobian.shape[1]),
            active_parameter_columns=int(np.count_nonzero(np.any(jacobian != 0, axis=0))),
            normal_map_projection_relative_error=float(np.linalg.norm(error)/max(denominator, np.finfo(float).tiny)),
            maximum_initial_field_residual_m=maximum_residual,
            minimum_initial_spatial_gradient_norm=float(np.min(lengths)),
            maximum_initial_spatial_gradient_norm=float(np.max(lengths)),
            model_jacobian_seconds=float(perf_counter()-jacobian_started),
            model_jacobian_bytes=int(jacobian.nbytes),
            model_initialization=model.initialization_metadata(),
        )
    elif model is not None:
        raise ValueError("Explicit metrics must not receive or query a neural model.")
    diagnostics["setup_seconds"] = float(perf_counter()-started)
    result = FrozenCurveMetric(
        kind, int(maximum_mode), _readonly(mass), None if covariance is None else _readonly(covariance),
        float(eigenvalue_floor), float(sobolev_angular_length), MappingProxyType(diagnostics),
    )
    result.active_matrices()
    return result


__all__ = ["FrozenCurveMetric", "build_frozen_curve_metric", "radial_chart_directions"]
