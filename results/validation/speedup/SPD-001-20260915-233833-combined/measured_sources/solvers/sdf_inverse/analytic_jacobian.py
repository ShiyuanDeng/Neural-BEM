"""Coupled Kress residual Jacobian in explicit Cartesian coefficient directions."""
import numpy as np
from ordered_boundary import fourier_curve
from gpr_bem_kress.materials import Material
from gpr_bem_kress.shape_derivative import KressDirection
from gpr_bem_kress.coupled_shape_derivative import (
    build_coupled_base, directional_operators, tangent_response,
)
from sdf_bem_multicomponent import PairedForwardProblem
from .explicit_fourier import CartesianFourierCurveState
from .optimization import normalized_complex_residual
from .work_accounting import record_work


def state_directions(state, boundary, direction):
    """Evaluate a coefficient direction on the exact native component grids."""
    if not all(isinstance(c, CartesianFourierCurveState) for c in state.components):
        raise ValueError("Analytic coefficient Jacobians currently require Cartesian Fourier components.")
    direction = np.asarray(direction, dtype=float)
    if direction.shape != (state.parameter_count,) or not np.all(np.isfinite(direction)):
        raise ValueError("Direction does not match the state coefficients.")
    result = []
    for component, sl, curve in zip(state.components, state.parameter_slices, boundary.components):
        v = direction[sl]
        cut = 2*(component.maximum_mode+1)
        parameterization = fourier_curve(v[:cut].reshape(-1, 2),
            np.vstack((np.zeros(2), v[cut:].reshape(-1, 2))),
            component_id=component.component_id, period=curve.period)
        jets = parameterization.evaluate(curve.parameters)
        result.append(KressDirection(*(getattr(jets, name) for name in
            ("points", "first_derivatives", "second_derivatives", "third_derivatives"))))
    return tuple(result)


def cartesian_residual_jacobian(state, data, geometry_config, *, solve_config, directions):
    """Return J and the independently solved base prediction; setup is charged.

    Derivative matrices are streamed one direction at a time. Geometry direction
    arrays are evaluated once on the native grid and reused across frequencies.
    No finite differences or geometry retractions occur inside this function.
    """
    boundary = state.boundary(geometry_config)
    problem = PairedForwardProblem.from_compatible(data.forward_problem)
    dirs = np.asarray(directions, dtype=float)
    if dirs.ndim != 2 or dirs.shape[1] != state.parameter_count or not np.all(np.isfinite(dirs)):
        raise ValueError("Directions must have shape (directions, parameters).")
    geometry_directions = [state_directions(state, boundary, d) for d in dirs]
    derivatives = np.zeros((len(dirs), problem.num_pairs, problem.num_frequencies), complex)
    predictions = np.empty((problem.num_pairs, problem.num_frequencies), complex)
    material = lambda spec: Material(epsr=spec.epsr, sigma=spec.sigma, mur=spec.mur)
    for fi, (omega, strength) in enumerate(zip(problem.angular_frequencies, problem.source_strengths)):
        base = build_coupled_base(boundary, problem.source_points, problem.receiver_points,
            float(omega), strength, exterior=material(problem.exterior), interior=material(problem.interior),
            eps0=problem.eps0, mu0=problem.mu0, config=solve_config)
        record_work(analytic_base_frequency_solve_count=1, factorization_count=1)
        predictions[:, fi] = np.diag(base.Y)
        for index, direction in enumerate(geometry_directions):
            operators = directional_operators(base, direction)
            derivatives[index, :, fi] = np.diag(tangent_response(base, operators))
            record_work(derivative_assembly_count=1, tangent_solve_count=1)
        del base
    observed = data.observed_scattered_response
    matrix = np.column_stack([normalized_complex_residual(observed+dy, observed, data.frequency_weights)[0]
                              for dy in derivatives])
    return matrix, predictions
