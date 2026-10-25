"""Public solver contract and nodal service. Solver state stays behind a handle.

Resolution integers are opaque backend profile tokens to the runner. The
nodal service maps them to nodes; future modal services own their trace and
assembly workspace settings. Neither the policy nor LM may inspect handles.
"""
from . import checks
from dataclasses import dataclass, field, asdict
from threading import Lock
from typing import Protocol
from time import perf_counter

import numpy as np

from bem_inverse.continuation import forward as F
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.geometry_runtime import geometry_validated
from gpr_bem_kress import cuda_assembly as CA


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


class PhysicsBackend(Protocol):
    name: str
    execution: Execution

    def validate(self, problem): ...
    def resolution_profile(self, storage_band): ...
    def evaluate(self, curve, observation, contrast, resolution) -> Prediction: ...
    def derivative(self, prediction, update, space): ...
    def ordered_calls(self, function, items): ...
    def observable_frontier(self, curve, observation, contrast, top, threshold): ...
    def disk_landscape(self, observations, contrast, centers, radii, cutoff): ...
    def receipt(self): ...


_BACKENDS = {}


def register_backend(name, factory):
    """Register a physics service once, without changing policy or optimizer."""
    if name in _BACKENDS:
        raise ValueError(f'Backend already registered: {name}')
    _BACKENDS[name] = factory


def make_backend(solver='nodal_kress', execution_settings=None):
    if solver == 'modal_muller' and solver not in _BACKENDS:
        raise ValueError("modal_muller is not registered. Call "
                         "bem_inverse.forward_solvers.modal_muller.register() first, or use a named "
                         "pipeline. No nodal fallback was selected.")
    if solver not in _BACKENDS:
        raise ValueError(f'Unknown solver {solver!r}; registered: {sorted(_BACKENDS)}')
    return _BACKENDS[solver](execution_settings or Execution())


class NodalKress:
    name = 'nodal_kress'

    def __init__(self, execution_settings):
        self.execution = execution_settings
        self._lock = Lock()
        self._table = None
        self._counts = dict(evaluation_attempts=0, evaluations=0, failed_evaluations=0,
                            derivative_attempts=0, derivatives=0, failed_derivatives=0, disk_batches=0)
        self._devices = {}
        self._fallbacks = {}
        self._seconds = {}
        from .nodal_geometry import GeometryCache
        self._geometry_cache = GeometryCache()

    def _record(self, kind, seconds=0., device=None, fallback=None):
        with self._lock:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            self._seconds[kind] = self._seconds.get(kind, 0.) + seconds
            if device:
                self._devices[device] = self._devices.get(device, 0) + 1
            if fallback:
                self._fallbacks[fallback] = self._fallbacks.get(fallback, 0) + 1

    def validate(self, problem):
        if problem.material != 'equal_density_homogeneous' or not isinstance(problem.initial, FourierCurve):
            raise ValueError('nodal_kress requires a single Fourier curve and equal-density homogeneous material.')
        if any(not isinstance(o.acquisition, F.PointSourceAcquisition) or
               len(o.acquisition.sources) != len(o.acquisition.receivers)
               for o in (*problem.real, *problem.damped)):
            raise ValueError('CI-001 disk localization requires point sources with a matched receiver diagonal.')
        if self.execution.device == 'cuda' and not CA.available():
            raise RuntimeError('Explicit CUDA execution requested, but no CUDA device is available.')
        if self.execution.device == 'cuda' and self.execution.acceleration == 'reference':
            raise ValueError('Reference damped execution is CPU. Use device=cpu or auto, or enable spd016.')

    def resolution_profile(self, storage_band):
        if self.execution.nodal_resolution_profile == 'band_matched':
            trace = max(64, 32*(int(np.ceil(storage_band/64))+1))
            n = 2*int(np.ceil(max(8, 2*trace+1, 2*storage_band+1)/2))
            return dict(production=n, refined=min(n+64, 1024) if n < 1024 else 2*n, kind='nodal_kress',
                        nodal_resolution=n, K_trace=trace, coefficient_workspace=None,
                        refinement='next +64 nodes up to 1024, then double; frontier and endpoint audit only')
        n = max(self.execution.resolution, 2 * (storage_band + 1))
        return dict(production=n, refined=2*n, kind='nodal_kress',
                    nodal_resolution=n, K_trace=None, coefficient_workspace=None,
                    refinement='double nodes; frontier and endpoint audit only')

    def ordered_calls(self, function, items):
        return F.ordered_calls(function, items, threads=self.execution.frequency_threads)

    def _ray_table(self):
        # Assembly callers also hold the device lock; publication is serialized.
        if self._table is None:
            from .damped_cuda import RayTable
            started = perf_counter()
            self._table = RayTable(.25)
            self._record('ray_table_setup', perf_counter()-started)
        return self._table

    def evaluate(self, curve, observation, contrast, resolution):
        """Compatibility entry point for the standalone nodal solver."""
        from .forward_solvers.nodal_kress import forward_solve
        return forward_solve(curve, observation, contrast, resolution, context=self)

    @geometry_validated
    def derivative(self, prediction, update, space):
        started = perf_counter()
        self._record('derivative_attempts')
        state = prediction._handle
        before = getattr(state.factors, 'fallback_count', 0)
        try:
            result = F.shape_jacobian(state, update.velocities(space, state.curve))
        except Exception:
            self._record('failed_derivatives', perf_counter()-started)
            raise
        if getattr(state.factors, 'fallback_count', 0) > before:
            self._record('factor_fallbacks', fallback='reciprocal device solve OOM; retained host LU')
        self._record('derivatives', perf_counter()-started)
        return result

    @geometry_validated
    def observable_frontier(self, curve, observation, contrast, top, threshold):
        from bem_inverse.normal_basis import orthonormal_normal_basis
        state = self.evaluate(curve, observation, contrast,
                              self.resolution_profile(curve.band)['refined'])._handle
        started = perf_counter()
        self._record('derivative_attempts')
        before = getattr(state.factors, 'fallback_count', 0)
        try:
            jacobian = F.shape_jacobian(state, orthonormal_normal_basis(state.curve, top))
        except Exception:
            self._record('failed_derivatives', perf_counter()-started)
            raise
        if getattr(state.factors, 'fallback_count', 0) > before:
            self._record('factor_fallbacks', fallback='frontier device solve OOM; retained host LU')
        self._record('derivatives', perf_counter()-started)
        norms = np.linalg.norm(jacobian.reshape(-1, jacobian.shape[-1]), axis=0)
        paired = np.r_[norms[0], np.hypot(norms[1::2], norms[2::2])]
        if checks.unobservable_frontier(paired):
            raise FloatingPointError('No finite nonzero observable frontier')
        frontier = int(np.flatnonzero(paired >= threshold * paired.max()).max())
        return dict(frontier=frontier, column_profile=paired, threshold=threshold, top=top, work_units=2)

    def disk_landscape(self, observations, contrast, centers, radii, cutoff):
        from bem_inverse.mie_localize import landscape
        started = perf_counter()
        reason, device = None, 'cpu-mie'
        if len(centers) == 1 or self.execution.acceleration == 'reference':
            value = landscape(observations, contrast, centers, radii, cutoff=cutoff)
        else:
            from .mie_grid import landscape_variant
            use_cuda = self.execution.device != 'cpu' and CA.available()
            if self.execution.device == 'cuda' and not use_cuda:
                raise RuntimeError('Explicit CUDA localization requested without a device')
            try:
                with CA._device_work:
                    value = landscape_variant(observations, contrast, centers, radii, cutoff,
                                              device='cuda' if use_cuda else None)
                device = 'cuda-mie' if use_cuda else 'cpu-mie-recurrence'
            except Exception as exc:
                if self.execution.device != 'auto' or not CA.out_of_memory(exc):
                    raise
                CA.record_fallback('Mie grid contraction')
                reason = 'Mie CUDA OOM'
                value = landscape_variant(observations, contrast, centers, radii, cutoff)
        self._record('disk_batches', perf_counter()-started, device, reason)
        return value

    def close(self):
        self._geometry_cache.clear()

    def receipt(self):
        geometry_cache = self._geometry_cache.receipt()
        with self._lock:
            return dict(solver=self.name, execution=asdict(self.execution), geometry_cache=geometry_cache,
                component_devices=dict(assembly=dict(cuda=sum(v for k,v in self._devices.items() if k.startswith('cuda')),
                                                      cpu=sum(v for k,v in self._devices.items() if k.startswith('cpu'))),
                    LU=dict(cuda=sum(v for k,v in self._devices.items() if k.startswith('cuda')),
                            cpu=sum(v for k,v in self._devices.items() if k.startswith('cpu'))),
                    field_evaluation='cpu', jacobian_contraction='cpu', reciprocal_solve='same as forward factors'),
                counts=dict(self._counts),
                devices=dict(self._devices), fallback_reasons=dict(self._fallbacks), seconds=dict(self._seconds),
                work_semantics='actual dispatched evaluations and derivative batches, including speculative threads; '
                               'optimizer ledger separately retains SPD reservation/charge semantics',
                localization_model='exact homogeneous disk Mie series, qualified by selected backend',
                ray=dict(gamma=.25, lo=.01, hi=100., panels=111, degree=24),
                retained_device_state='ray table and bounded geometry cache; matrix and reusable LU factors retained on host')


register_backend('nodal_kress', NodalKress)
