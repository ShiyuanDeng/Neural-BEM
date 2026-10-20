"""Frequency dispatch and cached production/refined stage evaluations.

The numerical maps are B5/B8; A1–A4 and B7 come from the selected physics.
Refined results keep predictions only, preserving the lifetime of LU factors.
"""
import hashlib
import traceback
import numpy as np
from .continuation.forward import ordered_calls, solve, shape_jacobian
from .continuation.geometry_runtime import geometry_validated
from .stage_types import Evaluation
from .recording import observe
from .b5_residual import normalize
from . import b5_residual, b8_gauss_newton

class Objective:
    """Stage objective at production and refined nodes; refined values cached."""

    def __init__(self, stage, contrast, config, ledger, *, physics=None):
        self.stage, self.contrast, self.config, self.ledger = stage, float(contrast), config, ledger
        self.physics = physics
        self.observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
        self.refined_cache = {}
        self.reusable_refined = {}  # exact refined predictions carried from the previous stage
        self.count = len(stage.observations)
        self.failures = []
        observe(physics, 'objective_setup', stage=stage, config=config, ledger=ledger)

    def _evaluation(self, curve, prediction, forwards):
        result = b5_residual.evaluate(curve, prediction, forwards, self.observed,
                                      self.stage.weights, self.config.residual_floor)
        observe(self.physics, 'objective', stage=self.stage, config=self.config, ledger=self.ledger,
                evaluation=result, observed=self.observed)
        return result

    def reused(self, curve, prediction, forwards, category):
        """``production`` for an exactly reused endpoint: the same charges, no dispatched solves."""
        self.ledger.reserve(self.count)
        self.ledger.replay("solve", category, self.count)
        return self._evaluation(curve, np.array(prediction, copy=True), forwards)

    @geometry_validated
    def _predict(self, curve, nodes, category, keep):
        self.ledger.reserve(self.count)
        forwards, columns = [], []

        def predict(observation):
            try:
                state = (solve(curve, observation.wavenumber, self.contrast, observation.acquisition, nodes)
                         if self.physics is None else
                         self.physics.evaluate(curve, observation, self.contrast, nodes))
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                failure = dict(exception_type=type(exc).__name__, message=str(exc),
                    traceback=traceback.format_exc(),
                    category=category, resolution=nodes,
                    frequency_hz=getattr(observation, 'frequency_hz', None),
                    wavenumber=dict(real=float(complex(observation.wavenumber).real),
                                    imag=float(complex(observation.wavenumber).imag)),
                    candidate_sha256=hashlib.sha256(curve.coefficients.tobytes()).hexdigest(),
                    candidate_coefficients=dict(real=curve.coefficients.real.tolist(),
                                                imag=curve.coefficients.imag.tolist()))
                with self.ledger._lock:
                    self.failures.append(failure)
                observe(self.physics, 'physics_failure', failure=failure, ledger=self.ledger)
                raise
            return state if keep else state.prediction  # release discarded systems early

        calls_for = ordered_calls if self.physics is None else self.physics.ordered_calls
        with self.ledger.calls(calls_for, predict, self.stage.observations, "solve", category) as calls:
            for call in calls:
                try:
                    value = call()
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    if not self.ledger.strict_dispatch:
                        self.ledger.fail(category)
                    return None
                columns.append(np.asarray(value.prediction if keep else value).reshape(-1))
                if keep:
                    forwards.append(value)
        return self._evaluation(curve, np.column_stack(columns), forwards)

    def production(self, curve, category):
        return self._predict(curve, self.stage.nodes, category, keep=True)

    def refined(self, curve):
        key = curve.coefficients.tobytes()
        if key not in self.refined_cache:
            if key in self.reusable_refined:
                # Charged where the original refined solve would have been charged.
                self.ledger.reserve(self.count)
                self.ledger.replay("solve", "acceptance_validation", self.count)
                self.refined_cache[key] = self._evaluation(curve, self.reusable_refined.pop(key), ())
            else:
                self.refined_cache[key] = self._predict(curve, self.stage.refined_nodes, "acceptance_validation",
                                                        keep=False)
        return self.refined_cache[key]

    @geometry_validated
    def jacobian(self, evaluation, update, space):
        """Residual Jacobian (rows as `normalize`) with respect to update coordinates."""
        blocks = []
        derivative_for = (lambda forward: shape_jacobian(forward, update.velocities(space, forward.curve))
                          if self.physics is None else self.physics.derivative(forward, update, space))
        calls_for = ordered_calls if self.physics is None else self.physics.ordered_calls
        with self.ledger.calls(calls_for, derivative_for, evaluation.forwards,
                               "reciprocal", "derivative") as calls:
            for call in calls:
                block = call()
                blocks.append(block.reshape(-1, block.shape[-1]))
        return b8_gauss_newton.residual_jacobian(
            blocks, self.observed, self.stage.weights, self.config.residual_floor)
