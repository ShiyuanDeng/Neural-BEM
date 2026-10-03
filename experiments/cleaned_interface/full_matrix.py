"""Opt-in receiver-coupled relaxation; ordinary CI-001 remains the default.

Matrices use (source, receiver) order and flatten in C order. For each source,
min_q ||C q-d||² + lambda ||A q-b||² = ||W(A^{-1}b-d)||²,
W²=lambda (C A^{-1} A^{-H} C^H+lambda I)^{-1}. The frozen-W
linearization is deliberately approximate; every accepted trial uses the
exact reduced loss at both resolutions. No truth enters this module.
"""
from dataclasses import dataclass, fields, replace
import numpy as np

from experiments.shape_continuation.lm_backend import (
    Objective, Evaluation, FitStage, normalize)
from experiments.shape_continuation.geometry_runtime import geometry_validated
from .policy import CumulativePolicy


def receiver_weights(h, rows, tau, *, paired=False):
    """Compute the positive Hermitian square root from H=A^{-H}C^H."""
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError('Relaxation tau must be finite and positive, or None for the ordinary objective.')
    h, rows = np.asarray(h), np.asarray(rows)
    lam = float(tau*np.median(np.sum(abs(rows)**2, axis=1)))
    if not np.isfinite(lam) or lam <= 0 or not np.isfinite(h).all():
        raise FloatingPointError('Nonpositive/nonfinite receiver relaxation scale')
    if paired:
        return np.sqrt(lam/(np.sum(abs(h)**2, axis=0)+lam))
    gram = h.conj().T@h
    values, vectors = np.linalg.eigh((gram+gram.conj().T)/2)
    if values.min() < -1e-12*max(float(values.max()), np.finfo(float).tiny):
        raise FloatingPointError('Receiver Gram matrix is not positive semidefinite')
    return (vectors*np.sqrt(lam/(np.maximum(values, 0)+lam)))@vectors.conj().T


def apply_receiver_weights(values, weights, shape):
    """Apply W to receiver columns, keeping sources and parameter axes distinct."""
    values = np.asarray(values)
    tail = values.shape[1:]
    if len(shape) == 1:
        return values*weights.reshape((-1,)+(1,)*len(tail))
    blocks = values.reshape(tuple(shape)+tail)
    return np.einsum('ij,sj...->si...', weights, blocks).reshape(values.shape)


@dataclass(frozen=True)
class RelaxedStage(FitStage):
    relaxed_tau: object = None

    def __post_init__(self):
        super().__post_init__()
        if self.relaxed_tau is not None and (not np.isfinite(self.relaxed_tau) or self.relaxed_tau <= 0):
            raise ValueError('Relaxation tau must be finite and positive, or None.')

    @classmethod
    def from_stage(cls, stage, tau):
        return cls(**{f.name:getattr(stage, f.name) for f in fields(FitStage)}, relaxed_tau=tau)


@dataclass(frozen=True)
class RelaxedEvaluation(Evaluation):
    receiver_weights: tuple = ()


class RelaxedObjective(Objective):
    def __init__(self, stage, contrast, config, ledger, *, physics=None):
        super().__init__(stage, contrast, config, ledger, physics=physics)
        self.tau = stage.relaxed_tau
        if physics is None or not hasattr(physics, 'relaxation_weights'):
            raise ValueError('Relaxation requires a physics service exposing receiver weights.')

    @geometry_validated
    def _predict(self, curve, nodes, category, keep):
        # One factorized forward plus one adjoint RHS batch per frequency.
        self.ledger.reserve(2*self.count)
        forwards, columns, residuals, weights = [], [], [], []
        def predict(observation):
            state = self.physics.evaluate(curve, observation, self.contrast, nodes)
            weight = self.physics.relaxation_weights(state, self.tau)
            prediction = state.prediction.reshape(-1)
            residual = apply_receiver_weights(prediction-observation.scattered.reshape(-1),
                                               weight, observation.acquisition.data_shape)
            return (state if keep else prediction), residual, weight
        with self.physics.ordered_calls(predict, self.stage.observations) as calls:
            for call in calls:
                self.ledger.reserve(2)
                self.ledger.charge('solve', category)
                self.ledger.charge('reciprocal', category+'_relaxation_adjoint')
                try:
                    state, residual, weight = call()
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    self.ledger.fail(category)
                    return None
                columns.append(state.prediction.reshape(-1) if keep else state)
                residuals.append(residual)
                if keep:
                    forwards.append(state)
                    weights.append(weight)
        prediction = np.column_stack(columns)
        residual = normalize(np.column_stack(residuals), self.observed, self.stage.weights,
                             self.config.residual_floor)
        relative = float(np.linalg.norm(prediction-self.observed)/np.linalg.norm(self.observed))
        return RelaxedEvaluation(curve, .5*float(residual@residual), relative, residual,
                                 prediction, tuple(forwards), tuple(weights))

    @geometry_validated
    def jacobian(self, evaluation, update, space):
        blocks = []
        def derivative(item):
            state, weight, observation = item
            jac = self.physics.derivative(state, update, space)
            return apply_receiver_weights(jac.reshape(-1, jac.shape[-1]), weight,
                                          observation.acquisition.data_shape)
        items = zip(evaluation.forwards, evaluation.receiver_weights, self.stage.observations)
        with self.physics.ordered_calls(derivative, items) as calls:
            for call in calls:
                self.ledger.reserve(1)
                self.ledger.charge('reciprocal', 'derivative')
                blocks.append(call())
        return normalize(np.stack(blocks, axis=1), self.observed, self.stage.weights,
                         self.config.residual_floor)


@dataclass(frozen=True)
class RealRelaxedPrefix(CumulativePolicy):
    name: str = 'fm001_real_relaxed_prefix'
    version: str = '1.0.0'

    def operations(self, problem, physics):
        operations = list(super().operations(problem, physics))
        real = {o.frequency_hz:o for o in problem.real}
        taus = iter((3., 3., 10., 30., 100.))
        for index, op in enumerate(operations):
            if op.kind != 'fit' or not op.label.endswith('_damped'):
                continue
            observations = tuple(real[o.frequency_hz] for o in op.stage.observations)
            config, weights, expected = self._config(problem, observations)
            label = op.label.removesuffix('_damped')+'_real_relaxed'
            stage = replace(op.stage, observations=observations, weights=weights, label=label)
            stage = RelaxedStage.from_stage(stage, next(taus))
            details = dict(op.details, relaxed_tau=stage.relaxed_tau,
                expected_noise_loss=expected, noise_threshold=config.loss_tolerance if expected else None,
                objective='exact reduced receiver-coupled relaxation; frozen W only in LM Jacobian',
                work='one additional adjoint batch per frequency evaluation; original total/stage caps')
            operations[index] = replace(op, label=label, stage=stage, optimizer=config,
                purpose='Real frequency prefix with receiver-coupled relaxation', details=details)
        return tuple(operations)
