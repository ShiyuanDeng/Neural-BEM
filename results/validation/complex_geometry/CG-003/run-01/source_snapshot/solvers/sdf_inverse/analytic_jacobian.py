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
from .work_accounting import record_work, analytic_work
from .runtime import current_runtime


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


def cartesian_residual_jacobian(state, data, geometry_config, *, solve_config, directions,
                                method=None, compiled_evaluator=None):
    """Return J and the independently solved base prediction; setup is charged.

    Operator derivatives are streamed one direction at a time. Reciprocal
    derivatives reuse one receiver-illumination batch per frequency. Geometry direction
    arrays are evaluated once on the native grid and reused across frequencies.
    No finite differences or geometry retractions occur inside this function.
    Runtime selection retains operator derivatives below the qualified minimum
    node count. An explicit method bypasses this runtime guard for diagnostics.
    """
    if compiled_evaluator is not None:
        if method is not None or not np.array_equal(directions, compiled_evaluator.directions):
            raise ValueError('Compiled fit directions/method do not match the evaluator.')
        compiled = compiled_evaluator.evaluate(state)
        if compiled is not None:
            # The constrained-direction policy may replace columns in-place.
            return compiled['jacobian'].copy(), compiled['prediction']
    boundary = state.boundary(geometry_config)
    problem = PairedForwardProblem.from_compatible(data.forward_problem)
    automatic = method is None
    runtime = current_runtime()
    method = runtime.shape_derivative if automatic else method
    if method not in ("operator", "reciprocal"):
        raise ValueError("Shape derivative method must be operator or reciprocal.")
    if (automatic and method == "reciprocal"
            and any(c.num_nodes < runtime.reciprocal_min_nodes for c in boundary.components)):
        method = "operator"
    # Keep the established path if future forward support extends the material
    # domain. The present high-level Kress forward rejects these materials too.
    if method == "reciprocal" and any(s.sigma != 0. or abs(s.mur-1.) > 1e-14
                                      for s in (problem.exterior, problem.interior)):
        method = "operator"
    dirs = np.asarray(directions, dtype=float)
    if dirs.ndim != 2 or len(dirs) == 0 or dirs.shape[1] != state.parameter_count or not np.all(np.isfinite(dirs)):
        raise ValueError("Directions must have shape (directions, parameters).")
    geometry_directions = [state_directions(state, boundary, d) for d in dirs]
    if method == "reciprocal":
        normal_weights = np.array([np.concatenate([
            np.sum(d.points*c.normals, axis=1)*c.arc_length_weights
            for d, c in zip(direction, boundary.components)]) for direction in geometry_directions])
    derivatives = np.zeros((len(dirs), problem.num_pairs, problem.num_frequencies), complex)
    predictions = np.empty((problem.num_pairs, problem.num_frequencies), complex)
    material = lambda spec: Material(epsr=spec.epsr, sigma=spec.sigma, mur=spec.mur)
    for fi, (omega, strength) in enumerate(zip(problem.angular_frequencies, problem.source_strengths)):
        with analytic_work('base', float(omega)):
            base = build_coupled_base(boundary, problem.source_points, problem.receiver_points,
                float(omega), strength, exterior=material(problem.exterior), interior=material(problem.interior),
                eps0=problem.eps0, mu0=problem.mu0, config=solve_config)
        record_work(analytic_base_frequency_solve_count=1, factorization_count=1,
                    analytic_primal_rhs_count=len(base.sources))
        predictions[:, fi] = np.diag(base.Y)
        if method == "reciprocal":
            from gpr_bem_kress.reciprocal_shape_derivative import reciprocal_paired_response
            with analytic_work('reciprocal', float(omega)):
                derivatives[:, :, fi] = reciprocal_paired_response(base, normal_weights)
            record_work(reciprocal_frequency_solve_count=1, reciprocal_rhs_count=len(base.receivers),
                        reciprocal_contraction_count=len(dirs))
            del base
            continue
        for index, direction in enumerate(geometry_directions):
            with analytic_work('direction', float(omega)):
                operators = directional_operators(base, direction)
                derivatives[index, :, fi] = np.diag(tangent_response(base, operators))
            record_work(derivative_assembly_count=1, tangent_solve_count=1)
        del base
    observed = data.observed_scattered_response
    matrix = np.column_stack([normalized_complex_residual(observed+dy, observed, data.frequency_weights)[0]
                              for dy in derivatives])
    return matrix, predictions
