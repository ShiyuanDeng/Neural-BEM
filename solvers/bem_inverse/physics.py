"""Public solver contract: execution settings, predictions, the registry and shared counters.

Each file in forward_solvers/ owns one physics context class and its
``forward_solve`` function, together with the derivative, the resolution
profile and the frontier. It registers the class and the function under one
name; ``make_backend`` returns the context with its forward solve bound to it.
Resolution integers are opaque backend profile tokens to the runner. Neither
the policy nor LM may inspect prediction handles.
"""
from dataclasses import dataclass, field
from functools import partial
from threading import Lock
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class Execution:
    device: str = 'auto'
    frequency_threads: int = 4
    acceleration: str = 'spd016'
    geometry: str = 'both'
    resolution: int = 512
    nodal_geometry_reuse: str = 'off'
    nodal_resolution_profile: str = 'fixed'
    audit_frequency_batch: int = 1
    # Decision-preserving work orderings (opt-in). 'sampled_first' runs the sampled
    # validity test before the full |W|^2 certificate; tiers only accept, so the
    # accept/refuse set is unchanged. Stage-entry reuse carries the previous stage's
    # evaluated endpoint across an unchanged curve, catalog and resolution.
    validity_order: str = 'certificate_first'
    stage_entry_reuse: bool = False

    def __post_init__(self):
        if self.device not in ('auto', 'cpu', 'cuda'):
            raise ValueError('device must be auto, cpu or cuda')
        if self.acceleration not in ('reference', 'spd016'):
            raise ValueError('acceleration must be reference or spd016')
        if self.frequency_threads < 1 or int(self.frequency_threads) != self.frequency_threads:
            raise ValueError('frequency_threads must be a positive integer')
        if self.audit_frequency_batch not in (1, 2, 3):
            raise ValueError('Audit frequency batches must be 1, 2 or 3 to bound system memory.')
        if self.geometry not in ('reference', 'cache', 'spatial', 'both'):
            raise ValueError('Unknown geometry runtime')
        if self.nodal_geometry_reuse not in ('off', 'per_curve'):
            raise ValueError('Unknown nodal geometry reuse')
        if self.nodal_resolution_profile not in ('fixed', 'band_matched'):
            raise ValueError('Unknown nodal resolution profile')
        if self.validity_order not in ('certificate_first', 'sampled_first'):
            raise ValueError('validity_order must be certificate_first or sampled_first')
        if not isinstance(self.stage_entry_reuse, bool):
            raise ValueError('stage_entry_reuse must be a bool')
        minimum = 512 if self.nodal_resolution_profile == 'fixed' else 8
        if self.resolution < minimum or self.resolution % 2:
            raise ValueError(f'The nodal accuracy profile needs an even resolution >={minimum}')


@dataclass(frozen=True)
class Prediction:
    prediction: np.ndarray
    diagnostics: dict
    _handle: object = field(repr=False)


class Counters:
    """Thread-safe call counts, seconds, devices and fallback reasons of one physics context."""

    def __init__(self, **counts):
        self.lock = Lock()
        self.counts, self.seconds, self.devices, self.fallbacks = dict(counts), {}, {}, {}

    def record(self, kind, seconds=0., device=None, fallback=None):
        with self.lock:
            self.counts[kind] = self.counts.get(kind, 0) + 1
            self.seconds[kind] = self.seconds.get(kind, 0.) + seconds
            if device:
                self.devices[device] = self.devices.get(device, 0) + 1
            if fallback:
                self.fallbacks[fallback] = self.fallbacks.get(fallback, 0) + 1

    def count(self, kind):
        with self.lock:
            self.counts[kind] = self.counts.get(kind, 0) + 1

    def snapshot(self):
        with self.lock:
            return dict(counts=dict(self.counts), devices=dict(self.devices),
                        fallback_reasons=dict(self.fallbacks), seconds=dict(self.seconds))


class PhysicsBackend(Protocol):
    name: str
    execution: Execution
    counters: Counters

    def validate(self, problem): ...
    def resolution_profile(self, storage_band): ...
    def derivative(self, prediction, update, space): ...
    def observable_frontier(self, prediction, top, threshold): ...
    def receipt(self): ...


_BACKENDS = {}


def register_backend(name, factory, forward_solve):
    """Register a physics context and its ``forward_solve(curve, observation, contrast, resolution, *, context)``."""
    if name in _BACKENDS:
        raise ValueError(f'Backend already registered: {name}')
    _BACKENDS[name] = (factory, forward_solve)


def make_backend(solver='nodal_kress', execution_settings=None):
    """The physics context for ``solver`` and its forward solve, bound to that context."""
    if solver == 'modal_muller' and solver not in _BACKENDS:
        raise ValueError("modal_muller is not registered. Call "
                         "bem_inverse.forward_solvers.modal_muller.register() first, or use a named "
                         "pipeline. No nodal fallback was selected.")
    if solver not in _BACKENDS:
        raise ValueError(f'Unknown solver {solver!r}; registered: {sorted(_BACKENDS)}')
    factory, forward_solve = _BACKENDS[solver]
    context = factory(execution_settings or Execution())
    return context, partial(forward_solve, context=context)
