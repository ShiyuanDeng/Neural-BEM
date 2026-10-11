"""Fit-local compiled Kress cache with explicit convergence and fallback."""
from collections import Counter
from dataclasses import asdict
import hashlib
import numpy as np
from gpr_bem_kress.compiled_scattering import (
    CompiledScatteringFailure, compile_local, reduced_paired_response,
)
from gpr_bem_kress.materials import Material
from gpr_bem_kress.multicomponent import (
    adapt_multicomponent_boundary, _validate_exterior_points, MultiComponentFieldPointError,
)
from sdf_bem_multicomponent import PairedForwardProblem
from .explicit_fourier import CartesianFourierCurveState
from .optimization import normalized_complex_residual
from .work_accounting import analytic_work, record_work


def relative_columns(actual, reference):
    delta = np.linalg.norm(actual-reference, axis=0)
    norms = np.linalg.norm(reference, axis=0)
    floor = max(np.finfo(float).tiny, 1e-12*float(np.max(norms)))
    return (float(np.linalg.norm(delta)/max(np.linalg.norm(norms), floor)),
            float(np.max(delta/np.maximum(norms, floor))))


class CompiledEvaluator:
    """One cache per fixed-topology fit; final/refined checks use full Kress.

    Directions and problem/configuration are fixed by the fit. Cache slots
    retain only the latest local shape per component/frequency/angular order.
    Failed numerical eligibility is cached only at the current exact state.
    Geometry admissibility exceptions propagate through the usual optimizer.
    """
    def __init__(self, data, geometry_config, solve_config, directions, *, allow_single=False,
                 order_pairs=((20, 24), (24, 28), (28, 32))):
        self.data = data
        self.problem = PairedForwardProblem.from_compatible(data.forward_problem)
        self.geometry_config, self.solve_config = geometry_config, solve_config
        self.directions = np.array(directions, dtype=float, copy=True)
        if self.directions.ndim != 2 or not len(self.directions) or not np.all(np.isfinite(self.directions)):
            raise ValueError('Compiled directions must be a nonempty finite matrix.')
        self.directions.setflags(write=False)
        self.allow_single, self.order_pairs = allow_single, tuple(order_pairs)
        self.cache, self.events, self.counts = {}, [], Counter()
        self.last_key = self.last_result = None

    def _fallback(self, key, reason):
        self.counts['fallback:'+reason] += 1
        record_work(compiled_fallback_count=1)
        self.events.append(dict(state_sha256=hashlib.sha256(key).hexdigest(), backend='full_kress', reason=reason))
        self.last_key, self.last_result = key, None
        return None

    def evaluate(self, state):
        key = repr(tuple((c.component_id, c.maximum_mode) for c in state.components)).encode()+state.parameter_vector().tobytes()
        if key == self.last_key:
            self.counts['state_cache_hits'] += 1
            return self.last_result
        if not all(isinstance(c, CartesianFourierCurveState) for c in state.components):
            return self._fallback(key, 'unsupported_chart')
        if len(state.components) < (1 if self.allow_single else 2):
            return self._fallback(key, 'single_component')
        problem = self.problem
        if np.any(np.linalg.norm(problem.source_points[:, None, :]-problem.receiver_points[None, :, :], axis=-1) <= 0):
            raise MultiComponentFieldPointError('source_points and receiver_points must be distinct.')
        if any(s.sigma != 0. or abs(s.mur-1.) > 1e-14 for s in (problem.exterior, problem.interior)):
            return self._fallback(key, 'unsupported_material')
        if self.solve_config.compute_condition_number:
            return self._fallback(key, 'condition_number_requested')
        boundary = state.boundary(self.geometry_config)
        adapt_multicomponent_boundary(boundary, config=self.solve_config.assembly)
        clearance = self.solve_config.minimum_field_point_clearance_in_weights*float(np.max(boundary.arc_length_weights))
        for name, points in (('sources', problem.source_points), ('receivers', problem.receiver_points)):
            _validate_exterior_points(points, boundary, name=name, minimum_clearance=clearance)
        centers = np.array([complex(*c.center) for c in state.components])
        radii = []
        for c in state.components:
            cosine = c.cosine_coefficients[1:, 0]+1j*c.cosine_coefficients[1:, 1]
            sine = c.sine_coefficients[1:, 0]+1j*c.sine_coefficients[1:, 1]
            radii.append(float(np.sum(abs((cosine-1j*sine)/2)+abs((cosine+1j*sine)/2))))
        for i in range(len(radii)):
            if any(abs(centers[i]-centers[j]) <= radii[i]+radii[j] for j in range(i)):
                return self._fallback(key, 'bounding_circles_overlap')
            for points in (problem.source_points, problem.receiver_points):
                if np.min(abs(points[:, 0]+1j*points[:, 1]-centers[i])) <= radii[i]:
                    return self._fallback(key, 'acquisition_inside_bounding_circle')
        # Same exact Cartesian direction evaluation as the ordinary bridge.
        from .analytic_jacobian import state_directions
        directions = [state_directions(state, boundary, d) for d in self.directions]
        weights = [np.array([np.sum(row[i].points*c.normals, axis=1)*c.arc_length_weights
                             for row in directions]) for i, c in enumerate(boundary.components)]
        predictions, derivatives, residuals, diagnostics = [], [], [], []
        try:
            for fi, (omega, strength) in enumerate(zip(problem.angular_frequencies, problem.source_strengths)):
                with analytic_work('compiled', float(omega)):
                    record_work(compiled_frequency_batch_count=1)
                    waves = [float(Material(epsr=s.epsr, sigma=s.sigma, mur=s.mur).wavenumber(
                        float(omega), problem.eps0, problem.mu0).real) for s in (problem.exterior, problem.interior)]
                    ko, ki = waves
                    for low, high in self.order_pairs:
                        templates = []
                        for i, (component, curve) in enumerate(zip(state.components, boundary.components)):
                            slot = (i, fi, high)
                            local_key = (component.component_id, component.cosine_coefficients[1:].tobytes(),
                                component.sine_coefficients[1:].tobytes(), curve.num_nodes, ko, ki,
                                repr(asdict(self.solve_config.assembly)), .1)
                            if slot not in self.cache or self.cache[slot][0] != local_key:
                                template = compile_local(curve, centers[i], ko, ki, order=high,
                                                         assembly=self.solve_config.assembly.self_assembly)
                                self.cache[slot] = (local_key, template)
                                record_work(compiled_local_factorization_count=1, compiled_local_rhs_count=2*high+1)
                                self.counts['local_compilations'] += 1
                            else:
                                record_work(compiled_local_cache_hit_count=1)
                                self.counts['local_cache_hits'] += 1
                            templates.append(self.cache[slot][1])
                        values = []
                        for order in (low, high):
                            values.append(reduced_paired_response([t.truncated(order) for t in templates], centers,
                                problem.source_points, problem.receiver_points, strength, ko, ki, weights))
                            record_work(compiled_reduced_solve_count=1,
                                        compiled_reduced_rhs_count=problem.num_pairs*2)
                            self.counts['reduced_solves'] += 1
                        small, large = values
                        forward_error = float(np.linalg.norm(small[0]-large[0]) /
                                              max(np.linalg.norm(large[0]), np.finfo(float).tiny))
                        derivative_errors = relative_columns(small[1].T, large[1].T)
                        check = dict(frequency_hz=float(omega/(2*np.pi)), low_order=low, high_order=high,
                            forward_error=forward_error, jacobian_error=derivative_errors[0],
                            worst_column=derivative_errors[1], maximum_system_residual=large[2])
                        diagnostics.append(check)
                        if forward_error <= 1e-11 and max(derivative_errors) <= 1e-7:
                            predictions.append(large[0]); derivatives.append(large[1]); residuals.append(large[2])
                            break
                    else:
                        raise CompiledScatteringFailure('angular_convergence')
        except CompiledScatteringFailure as exc:
            self.events.append(dict(state_sha256=hashlib.sha256(key).hexdigest(), angular_checks=diagnostics))
            return self._fallback(key, str(exc))
        prediction = np.stack(predictions, axis=1)
        dy = np.stack(derivatives, axis=-1)
        observed = self.data.observed_scattered_response
        jacobian = np.column_stack([normalized_complex_residual(observed+d, observed,
                                     self.data.frequency_weights)[0] for d in dy])
        self.last_result = dict(prediction=prediction, jacobian=jacobian,
                                maximum_system_residual=max(residuals))
        prediction.setflags(write=False)
        jacobian.setflags(write=False)
        self.last_key = key
        self.events.append(dict(state_sha256=hashlib.sha256(key).hexdigest(), backend='compiled',
                                angular_checks=diagnostics))
        return self.last_result

    def snapshot(self):
        return dict(counts=dict(self.counts), events=list(self.events))
