"""Opt-in bounded radial-shape plus one interior-permittivity inverse.

The current lossless/nonmagnetic forward is rebuilt for every changed physical
candidate. No production optimizer, source calibration or material default is
modified. The analytic Jacobian differentiates the complete discrete Kress
forward on a fixed correspondence using the independently tested E module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from time import perf_counter

import numpy as np
from scipy.optimize import least_squares

from gpr_bem_kress import KressSolveConfig, Material, solve_kress_tmz_total_field_batch
from gpr_bem_kress.shape_derivative import KressDirection, linearize_kress_forward
from .curve_updates import RadialFourierCurveState, radial_fourier_parameterization
from .forward import MaterialSpec, PairedForwardProblem


PARAMETER_NAMES = ("mean_radius_m", "center_x_m", "center_y_m", "radial_cos2_m", "radial_sin2_m", "interior_epsr")
PARAMETER_ORIGIN = np.array([.05, .5, .5, 0., 0., 6.])
PARAMETER_SCALES = np.array([.01, .01, .01, .005, .005, 2.])
PHYSICAL_LOWER = np.array([.035, .47, .47, -.004, -.004, 1.2])
PHYSICAL_UPPER = np.array([.075, .53, .53, .004, .004, 12.])
for _constant in (PARAMETER_ORIGIN, PARAMETER_SCALES, PHYSICAL_LOWER, PHYSICAL_UPPER):
    _constant.setflags(write=False)


def _readonly(values, *, dtype=float):
    result = np.array(values, dtype=dtype, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError("Nonfinite numeric input.")
    result.setflags(write=False)
    return result


def scaled_parameters(physical):
    if np.iscomplexobj(physical):
        raise ValueError("Physical parameters must be real.")
    values = _readonly(physical)
    if values.shape != (6,):
        raise ValueError("Expected six physical parameters.")
    return (values-PARAMETER_ORIGIN)/PARAMETER_SCALES


def candidate_state(scaled):
    if np.iscomplexobj(scaled):
        raise ValueError("Scaled parameters must be real.")
    values = _readonly(scaled)
    if values.shape != (6,):
        raise ValueError("Expected six scaled real parameters.")
    physical = PARAMETER_ORIGIN+PARAMETER_SCALES*values
    tolerance = 1e-12
    if np.any(physical < PHYSICAL_LOWER-tolerance) or np.any(physical > PHYSICAL_UPPER+tolerance):
        raise ValueError("Candidate violates the declared physical bounds.")
    state = RadialFourierCurveState(physical[1:3], [physical[0], 0., physical[3]],
                                  [0., 0., physical[4]], component_id="material_inverse_radial_k2")
    return _readonly(physical), state


def scaled_direction(parameters, index):
    """Exact jets of the affine, gauge-fixed radial chart (no FD probes)."""
    if isinstance(index, (bool, np.bool_)) or not isinstance(index, (int, np.integer)) or not 0 <= index < 6:
        raise ValueError("Parameter index must be an integer from zero through five.")
    if index == 5:
        return KressDirection(interior_epsr=float(PARAMETER_SCALES[index]))
    t = np.asarray(parameters, dtype=float)
    er = np.column_stack((np.cos(t), np.sin(t)))
    et = np.column_stack((-np.sin(t), np.cos(t)))
    if index in (1, 2):
        points = np.zeros_like(er); points[:, index-1] = PARAMETER_SCALES[index]
        return KressDirection(points, np.zeros_like(er), np.zeros_like(er), np.zeros_like(er))
    if index == 0:
        b, first, second, third = np.ones(len(t)), np.zeros(len(t)), np.zeros(len(t)), np.zeros(len(t))
    elif index == 3:
        b, first = np.cos(2*t), -2*np.sin(2*t)
        second, third = -4*b, -4*first
    else:
        b, first = np.sin(2*t), 2*np.cos(2*t)
        second, third = -4*b, -4*first
    jets = (b[:, None]*er,
            first[:, None]*er+b[:, None]*et,
            (second-b)[:, None]*er+2*first[:, None]*et,
            (third-3*first)[:, None]*er+(3*second-b)[:, None]*et)
    return KressDirection(*(jet*PARAMETER_SCALES[index] for jet in jets))


def _scene_hash(problem, nodes, config):
    digest = hashlib.sha256()
    for array in (problem.source_points, problem.receiver_points, problem.angular_frequencies, problem.source_strengths):
        digest.update(str(array.shape).encode()); digest.update(array.tobytes())
    digest.update(json.dumps({"exterior": asdict(problem.exterior), "template_interior": asdict(problem.interior),
        "eps0": problem.eps0, "mu0": problem.mu0, "num_nodes": nodes, "kress_config": asdict(config),
        "chart_origin": PARAMETER_ORIGIN.tolist(), "chart_scales": PARAMETER_SCALES.tolist()}, sort_keys=True).encode())
    return digest.hexdigest()


@dataclass(frozen=True)
class CandidateEvaluation:
    scaled: np.ndarray
    physical: np.ndarray
    state: RadialFourierCurveState
    problem: PairedForwardProblem
    forward_results: tuple
    prediction: np.ndarray
    residual: np.ndarray
    cache_key: str


class MaterialCurveEvaluator:
    """Immutable observations and one-entry, full-identity candidate cache."""

    def __init__(self, problem, observed, *, nodes=64, config=None):
        if not isinstance(problem, PairedForwardProblem):
            raise TypeError("Expected PairedForwardProblem.")
        if problem.exterior.sigma != 0 or problem.interior.sigma != 0 or problem.exterior.mur != 1 or problem.interior.mur != 1:
            raise ValueError("This experiment supports only lossless nonmagnetic materials.")
        if isinstance(nodes, (bool, np.bool_)) or not isinstance(nodes, (int, np.integer)) or nodes < 16 or nodes % 2:
            raise ValueError("nodes must be even and at least sixteen.")
        self.problem = problem
        self.observed = _readonly(observed, dtype=np.complex128)
        if self.observed.shape != (problem.num_pairs, problem.num_frequencies):
            raise ValueError("Observation shape does not match acquisition.")
        self.nodes = int(nodes)
        self.config = KressSolveConfig() if config is None else config
        if not isinstance(self.config, KressSolveConfig):
            raise TypeError("Expected KressSolveConfig.")
        norms = np.linalg.norm(self.observed, axis=0)
        if np.any(norms <= 1e-20):
            raise ValueError("This normalization requires a nonzero observed field in every frequency.")
        self.frequency_scales = _readonly(norms)
        self.normalization_hash = hashlib.sha256(self.frequency_scales.tobytes()).hexdigest()
        self.observation_hash = hashlib.sha256(self.observed.tobytes()).hexdigest()
        self.scene_hash = _scene_hash(problem, self.nodes, self.config)
        self._cached = None
        self._jacobian_cache = {}
        self.work = {"candidate_builds": 0, "forward_solves": 0, "cache_hits": 0,
                     "invalid_candidate_probes": 0, "failed_forward_solves": 0,
                     "analytic_direction_evaluations": 0, "forward_seconds": 0., "jacobian_seconds": 0.}
        self.history = []

    def _assert_frozen(self):
        if hashlib.sha256(self.observed.tobytes()).hexdigest() != self.observation_hash:
            raise RuntimeError("Immutable observations changed.")
        if _scene_hash(self.problem, self.nodes, self.config) != self.scene_hash:
            raise RuntimeError("Immutable acquisition/numerical configuration changed.")
        if hashlib.sha256(np.asarray(self.frequency_scales).tobytes()).hexdigest() != self.normalization_hash:
            raise RuntimeError("Immutable residual normalization changed.")

    def evaluate(self, scaled):
        self._assert_frozen()
        try:
            physical, state = candidate_state(scaled)
        except (TypeError, ValueError):
            self.work["invalid_candidate_probes"] += 1
            raise
        values = _readonly(scaled)
        key = hashlib.sha256((self.scene_hash+self.observation_hash+self.normalization_hash).encode()+values.tobytes()).hexdigest()
        if self._cached is not None and self._cached.cache_key == key:
            self.work["cache_hits"] += 1
            return self._cached
        started = perf_counter()
        self.work["candidate_builds"] += 1
        # A new MaterialSpec and production Material are built for every new
        # candidate, so interior k, differences and analytic diagonals change.
        candidate_problem = replace(self.problem, interior=MaterialSpec(float(physical[5])))
        producer = radial_fourier_parameterization(state)
        curve = producer.discretize(self.nodes, require_even=True)
        forwards = []
        try:
            for omega, strength in zip(candidate_problem.angular_frequencies, candidate_problem.source_strengths):
                self.work["forward_solves"] += 1
                try:
                    forwards.append(solve_kress_tmz_total_field_batch(curve, candidate_problem.source_points,
                        candidate_problem.receiver_points, float(omega), complex(strength),
                        exterior=Material(**asdict(candidate_problem.exterior)),
                        interior=Material(**asdict(candidate_problem.interior)), eps0=candidate_problem.eps0,
                        mu0=candidate_problem.mu0, config=self.config))
                except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
                    self.work["failed_forward_solves"] += 1
                    raise
        finally:
            self.work["forward_seconds"] += perf_counter()-started
        forwards = tuple(forwards)
        prediction = np.column_stack([np.diag(forward.scattered_receiver) for forward in forwards])
        residual_complex = (prediction-self.observed)/self.frequency_scales[None, :]
        residual = np.r_[residual_complex.real.ravel(), residual_complex.imag.ravel()]
        self._cached = CandidateEvaluation(values, physical, state, candidate_problem, forwards,
            _readonly(prediction, dtype=np.complex128), _readonly(residual), key)
        self._jacobian_cache = {}
        self.history.append({"physical_parameters": physical.tolist(), "cache_key": key,
            "loss": .5*float(residual@residual), "interior_wavenumbers": [[float(f.system.k_interior.real),
                float(f.system.k_interior.imag)] for f in forwards]})
        return self._cached

    def jacobian(self, scaled, *, active_indices=tuple(range(6))):
        active_indices = tuple(active_indices)
        if (not active_indices or any(isinstance(index, (bool, np.bool_)) or
            not isinstance(index, (int, np.integer)) or not 0 <= index < 6 for index in active_indices)
            or len(set(active_indices)) != len(active_indices)):
            raise ValueError("active_indices must be nonempty distinct integer indices from zero through five.")
        base = self.evaluate(scaled)
        started = perf_counter()
        columns = []
        for index in active_indices:
            if index not in self._jacobian_cache:
                direction = scaled_direction(base.forward_results[0].system.geometry.parameters, index)
                jvps = [linearize_kress_forward(forward, direction) for forward in base.forward_results]
                self.work["analytic_direction_evaluations"] += len(jvps)
                complex_column = np.column_stack([np.diag(jvp.d_scattered_receiver) for jvp in jvps])
                weighted = complex_column/self.frequency_scales[None, :]
                self._jacobian_cache[index] = _readonly(np.r_[weighted.real.ravel(), weighted.imag.ravel()])
            columns.append(self._jacobian_cache[index])
        self.work["jacobian_seconds"] += perf_counter()-started
        return np.column_stack(columns)


def fit_material_curve(evaluator, initial_physical, *, joint_shape=False, max_evaluations=40):
    """Bounded TRF least squares; observations/normalization never regenerate."""
    initial = scaled_parameters(initial_physical)
    candidate_state(initial)
    active = tuple(range(6)) if joint_shape else (5,)
    lower = ((PHYSICAL_LOWER-PARAMETER_ORIGIN)/PARAMETER_SCALES)[list(active)]
    upper = ((PHYSICAL_UPPER-PARAMETER_ORIGIN)/PARAMETER_SCALES)[list(active)]
    def expand(values):
        result = initial.copy(); result[list(active)] = values
        return result
    started = perf_counter()
    result = least_squares(lambda x: evaluator.evaluate(expand(x)).residual,
        initial[list(active)], jac=lambda x: evaluator.jacobian(expand(x), active_indices=active),
        bounds=(lower, upper), method="trf", x_scale=1., max_nfev=max_evaluations,
        ftol=1e-11, xtol=1e-11, gtol=1e-10)
    final = evaluator.evaluate(expand(result.x))
    jacobian = evaluator.jacobian(final.scaled, active_indices=active)
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    column_norms = np.linalg.norm(jacobian, axis=0)
    correlations = (jacobian.T@jacobian)/np.maximum(column_norms[:, None]*column_norms[None, :], 1e-300)
    full_gradient = jacobian.T@final.residual
    projected_gradient = result.x-np.clip(result.x-full_gradient, lower, upper)
    projected_norm = float(np.max(np.abs(projected_gradient)))
    bound_flags = np.asarray(result.active_mask)
    return final, {"optimizer_success": bool(result.success), "optimizer_status": int(result.status),
        "optimizer_message": str(result.message), "active_parameter_names": [PARAMETER_NAMES[index] for index in active],
        "active_indices": list(active), "function_evaluations": int(result.nfev),
        "jacobian_evaluations": int(result.njev), "optimality": float(result.optimality),
        "active_bounds": bound_flags.tolist(), "scaled_gradient": full_gradient.tolist(),
        "scaled_projected_gradient": projected_gradient.tolist(), "projected_gradient_inf": projected_norm,
        "stationarity_tolerance": 1e-7, "verified_stationarity": projected_norm <= 1e-7,
        "initial_physical": np.asarray(initial_physical).tolist(), "final_physical": final.physical.tolist(),
        "weighted_loss": .5*float(final.residual@final.residual),
        "jacobian_singular_values": singular_values.tolist(),
        "jacobian_condition": float(singular_values[0]/singular_values[-1]) if singular_values[-1] > 0 else None,
        "jacobian_column_correlations": correlations.tolist(), "scaled_weighted_real_jacobian": jacobian,
        "jacobian_interpretation": "rows are real then imaginary weighted paired residuals; columns are dimensionless declared parameter scales; local diagnostics, not a global identifiability proof",
        "seconds": perf_counter()-started, "work": dict(evaluator.work),
        "candidate_history": list(evaluator.history), "observation_sha256": evaluator.observation_hash,
        "scene_sha256": evaluator.scene_hash,
        "normalization_sha256": evaluator.normalization_hash,
        "frequency_normalization": evaluator.frequency_scales.tolist(),
        "cache_policy": "one entry; full scaled geometry/material vector, acquisition/frequency/calibration/constants/config/chart and immutable observation identity"}
