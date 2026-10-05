"""Full Tx/Rx adapter over the maintained modal Müller operators.

The active inverse's paired-observation and real/damped policy is unchanged.
This research adapter exposes every archived Tx/Rx pair without repeating the
16 source solves for each of 32 receivers. Coordinates may coincide between
source and receiver sets: only scattered fields are evaluated there.
"""

from dataclasses import dataclass

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from bem_inverse.modal_muller import ModalMuller, token
from bem_inverse.modal_operator import hadamard, point_kernels
from bem_inverse.physics import Prediction


@dataclass(frozen=True)
class FullAcquisition:
    sources: np.ndarray
    receivers: np.ndarray
    strength: complex

    def __post_init__(self):
        for name in ("sources", "receivers"):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if value.ndim != 2 or value.shape[1] != 2 or not len(value) or not np.isfinite(value).all():
                raise ValueError("Finite nonempty (N,2) sensor arrays required")
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not np.isfinite(self.strength):
            raise ValueError("Finite source strength required")

    @property
    def data_shape(self):
        return len(self.sources), len(self.receivers)


@dataclass(frozen=True)
class FullState:
    wavenumber: complex
    interior_wavenumber: complex
    acquisition: FullAcquisition
    cutoff: int
    coefficients: np.ndarray
    factors: tuple
    traces: np.ndarray
    reciprocal_rhs: np.ndarray


class FullMatrixModal(ModalMuller):
    name = "modal_muller_full_matrix_research_adapter"

    def _evaluate(self, curve, observation, contrast, cutoff):
        k = complex(observation.wavenumber)
        k = k.real if k.imag == 0 else k
        if not (np.isfinite(k) and np.real(k) > 0 and np.imag(k) >= 0 and
                np.isfinite(contrast) and contrast > 0):
            raise ValueError("Finite physical wavenumbers and material ratio required")
        acquisition = observation.acquisition
        if not isinstance(acquisition, FullAcquisition):
            raise TypeError("FullAcquisition required")
        ki = k * np.sqrt(contrast)
        geometry, (matrix, radial, device, fallback) = self._matrix(
            curve, cutoff + self.settings.window_margin, k, ki, cutoff)
        with self._stage("waves"):
            sources, receivers = point_kernels(geometry, k,
                (acquisition.sources, acquisition.receivers),
                tolerance=self.settings.graf_tolerance, series_loss=self.settings.series_loss)
        with self._stage("factorization"):
            factors = lu_factor(matrix, check_finite=True)
        with self._stage("fields"):
            window = geometry.band
            test = window + np.arange(-cutoff, cutoff + 1)
            trial = window - np.arange(-cutoff, cutoff + 1)
            rhs = np.vstack((sources[0][test], sources[1][test])) * acquisition.strength
            traces = lu_solve(factors, rhs)
            residual = float(np.linalg.norm(matrix @ traces - rhs) / np.linalg.norm(rhs))
            readout = 2 * np.pi * np.hstack((receivers[1][trial].T, -receivers[0][trial].T))
            prediction = (readout @ traces).T
        if not np.isfinite(prediction).all():
            raise FloatingPointError("Nonfinite full-matrix scattered fields")
        state = FullState(k, ki, acquisition, cutoff, curve.coefficients.copy(), factors,
                         traces, np.vstack((receivers[0][test], receivers[1][test])))
        return Prediction(prediction, {
            "solver": self.name, "device": device, "fallback": fallback,
            "resolution": token(cutoff), "K_trace": cutoff, "window": window,
            "system_dimension": 2 * (2 * cutoff + 1),
            "source_rhs_columns": len(acquisition.sources),
            "receiver_rhs_columns": len(acquisition.receivers),
            "system_residual": residual, **radial,
        }, state)

    def _contract(self, state, weights):
        count = 2 * state.cutoff + 1
        with self._stage("reciprocal_solve"):
            reciprocal = lu_solve(state.factors, state.reciprocal_rhs)
        # Source-first flattening matches the prepared observation arrays.
        source_values = np.repeat(state.traces[:count], len(state.acquisition.receivers), axis=1)
        receiver_values = np.tile(reciprocal[:count], (1, len(state.acquisition.sources)))
        derivative = hadamard(source_values, receiver_values, weights, state.cutoff,
                             state.interior_wavenumber**2 - state.wavenumber**2)
        if not np.isfinite(derivative).all():
            raise FloatingPointError("Nonfinite full-matrix shape derivative")
        return derivative
