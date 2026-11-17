"""Explicit B5/B8 frequency-block layout; no padding or unmeasured entries."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class FrequencyBlocks:
    observed: tuple
    scales: np.ndarray
    roots: np.ndarray
    offsets: np.ndarray

    @classmethod
    def from_observations(cls, observations, weights, floor=1e-12):
        observed = tuple(np.asarray(o.scattered).reshape(-1) for o in observations)
        norms = np.array([np.linalg.norm(o) for o in observed])
        reference = max(float(max(norms)), float(np.linalg.norm(norms))/np.sqrt(len(norms)), 1.)
        scales = np.maximum(norms, max(floor*reference, np.finfo(float).tiny))
        return cls(observed, scales, np.sqrt(np.asarray(weights, float)),
                   np.cumsum([0]+[o.size for o in observed]))

    def normalize(self, blocks):
        """Frequency-major complex rows, then all real followed by all imaginary."""
        if len(blocks) != len(self.observed):
            raise ValueError('One data block is required per frequency.')
        scaled = []
        for value, observed, scale, root in zip(blocks, self.observed, self.scales, self.roots):
            value = np.asarray(value)
            if value.shape[0] != observed.size:
                raise ValueError('Data block rows must match the measured pairs.')
            scaled.append(value/scale*root)
        joined = np.concatenate(scaled, axis=0)
        return np.concatenate((joined.real, joined.imag), axis=0)

    def differences(self, prediction):
        if len(prediction) != len(self.observed):
            raise ValueError('One prediction is required per frequency.')
        return tuple(np.asarray(p).reshape(-1)-o for p, o in zip(prediction, self.observed))

    def relative(self, prediction):
        norms = [np.linalg.norm(d) for d in self.differences(prediction)]
        return float(np.linalg.norm(norms)/np.linalg.norm([np.linalg.norm(o) for o in self.observed]))

    def maximum_relative(self, prediction):
        return float(max(np.linalg.norm(d)/np.linalg.norm(o)
                         for d, o in zip(self.differences(prediction), self.observed)))
