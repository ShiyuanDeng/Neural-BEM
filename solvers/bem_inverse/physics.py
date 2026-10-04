"""Public solver contract and nodal service. Solver state stays behind a handle.

Resolution integers are opaque backend profile tokens to the runner. The
nodal service maps them to nodes; future modal services own their trace and
assembly workspace settings. Neither the policy nor LM may inspect handles.
"""
from dataclasses import dataclass, field, asdict
from threading import Lock
from typing import Protocol
from contextlib import contextmanager
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor

from bem_inverse.continuation import forward as F
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.geometry_runtime import geometry_validated
from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.execution import execution


@dataclass(frozen=True)
class Execution:
    device: str = 'auto'
    frequency_threads: int = 4
    acceleration: str = 'spd016'
    geometry: str = 'both'
    resolution: int = 512
    nodal_geometry_reuse: str = 'off'
    nodal_resolution_profile: str = 'fixed'

    def __post_init__(self):
        if self.device not in ('auto', 'cpu', 'cuda'):
            raise ValueError('device must be auto, cpu or cuda')
        if self.acceleration not in ('reference', 'spd016'):
            raise ValueError('acceleration must be reference or spd016')
        if self.frequency_threads < 1 or int(self.frequency_threads) != self.frequency_threads:
            raise ValueError('frequency_threads must be a positive integer')
        if self.geometry not in ('reference', 'cache', 'spatial', 'both'):
            raise ValueError('Unknown geometry runtime')
        if self.nodal_geometry_reuse not in ('off', 'per_curve'):
            raise ValueError('Unknown nodal geometry reuse')
        if self.nodal_resolution_profile not in ('fixed', 'band_matched'):
            raise ValueError('Unknown nodal resolution profile')
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
    def refine_resolution(self, resolution): ...
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
        raise NotImplementedError('Native modal_muller is not yet qualified for the complete-trial '
                                  'derivative/complex-frequency contract. No nodal fallback was selected.')
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
                        refinement='stage-selected fields and Jacobian; next +64 nodes, then 2048')
        n = max(self.execution.resolution, 2 * (storage_band + 1))
        return dict(production=n, refined=2*n, kind='nodal_kress',
                    nodal_resolution=n, K_trace=None, coefficient_workspace=None,
                    refinement='double nodes; refuse candidates outside per-frequency tolerance')

    def ordered_calls(self, function, items):
        return F.ordered_calls(function, items, threads=self.execution.frequency_threads)

    def refine_resolution(self, resolution):
        return 2*resolution

    def _ray_table(self):
        # Assembly callers also hold the device lock; publication is serialized.
        if self._table is None:
            from .damped_cuda import RayTable
            started = perf_counter()
            self._table = RayTable(.25)
            self._record('ray_table_setup', perf_counter()-started)
        return self._table

    @geometry_validated
    def evaluate(self, curve, observation, contrast, resolution):
        started = perf_counter()
        self._record('evaluation_attempts')
        try:
            if complex(observation.wavenumber).imag == 0 and self.execution.nodal_geometry_reuse == 'off':
                state = F.solve(curve, float(np.real(observation.wavenumber)), contrast,
                                observation.acquisition, resolution, execution_backend=self.execution.device)
                fallback = 'real CUDA OOM' if state.backend == 'cpu-fallback' else None
            else:
                state, fallback = self._damped(curve, observation, contrast, resolution)
            self._record('evaluations', perf_counter()-started, state.backend, fallback)
            if getattr(state.factors, 'fallback_count', 0):
                self._record('factor_fallbacks', fallback='forward device solve OOM; retained host LU')
            return Prediction(state.prediction, dict(solver=self.name, device=state.backend,
                resolution=resolution, system_residual=state.system_residual, fallback=fallback), state)
        except Exception:
            self._record('failed_evaluations', perf_counter()-started)
            raise

    def _damped(self, shape, observation, contrast, nodes):
        k = complex(observation.wavenumber)
        if k.real <= 0 or k.imag < 0 or not np.isfinite(k) or contrast <= 0 or not np.isfinite(contrast):
            raise ValueError('Invalid damped material/wavenumber')
        curve, adapter, prepared = self._geometry_cache.get(shape, nodes, self.execution.device,
            enabled=self.execution.nodal_geometry_reuse == 'per_curve')
        assemble, receivers, incident = F._operators(curve)
        ki, acquisition = k * np.sqrt(contrast), observation.acquisition
        selected = self.execution.device
        available = CA.available() if selected != 'cpu' else False
        if selected == 'cuda' and not available:
            raise RuntimeError('Explicit CUDA requested, but no CUDA device is available.')
        device = selected != 'cpu' and available and self.execution.acceleration == 'spd016'
        reason = None
        if selected == 'auto' and not available:
            reason = 'CUDA unavailable'
        elif self.execution.acceleration == 'reference':
            if selected == 'cuda':
                raise ValueError('Damped reference execution requires CPU')
            reason = 'reference damped execution requested'
        with execution(kernels='reference', device='cpu'):
            if device:
                try:
                    from .damped_cuda import gpu_matrix
                    with CA._device_work:
                        if k.imag:
                            matrix = gpu_matrix(curve, k, ki, self._ray_table(), adapter=adapter, prepared=prepared)
                        else:
                            from gpr_bem_kress.operators import MullerAssemblyConfig
                            if adapter is None:
                                from gpr_bem_kress.geometry import adapt_periodic_curve
                                adapter = adapt_periodic_curve(curve)
                            blocks = CA._difference_blocks(adapter, k, complex(ki), MullerAssemblyConfig(),
                                                           'cuda', prepared=prepared)
                            matrix = CA._compose(blocks, nodes, 'cuda')
                    factors = CA.DeviceFactors(matrix, fallback=selected == 'auto')
                    matrix = factors.host
                except Exception as exc:
                    outside = isinstance(exc, ValueError) and ('tabulated' in str(exc))
                    if selected != 'auto' or not (outside or CA.out_of_memory(exc)):
                        raise
                    reason = 'damped ray envelope: '+str(exc) if outside else 'damped CUDA OOM'
                    device = False
                    if not outside:
                        CA.record_fallback('damped assembly/factorization')
            if not device:
                matrix = np.asarray(assemble(curve, k, ki).system_matrix)
                factors = lu_factor(matrix)
            receiver = receivers(curve, acquisition.receivers, k)
            field, normal = incident(curve, acquisition.sources, k, acquisition.strength)
            traces, residual = F._solve(matrix, factors, np.vstack((field.T, normal.T)))
            prediction = receiver.apply_state(traces)
            if acquisition.paired:
                prediction = np.diag(prediction).copy()
        if not np.isfinite(prediction).all():
            raise FloatingPointError('Nonfinite damped prediction')
        state = F.ForwardState(curve, k, ki, acquisition, matrix, factors, traces,
                               prediction, residual, ('cuda-damped' if k.imag else 'cuda') if device else 'cpu-damped')
        return state, reason

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
    def relaxation_components(self, prediction):
        """Reuse the forward LU for H=A^{-H}C^H; return backend-owned receiver rows."""
        from scipy.linalg import lu_solve
        started = perf_counter()
        state = prediction._handle
        if hasattr(state, '_relaxation_components'):
            return state._relaxation_components
        self._record('relaxation_adjoint_attempts')
        try:
            with execution(kernels='reference', device='cpu'):
                rows = F._operators(state.curve)[1](state.curve, state.acquisition.receivers,
                                                    state.wavenumber).state_rows
            rhs = rows.conj().T
            if isinstance(state.factors, CA.DeviceFactors):
                h, residual = state.factors.solve(rhs, adjoint=True)
            else:
                h = lu_solve(state.factors, rhs, trans=2)
                residual = np.linalg.norm(state.matrix.conj().T@h-rhs)/np.linalg.norm(rhs)
            if not np.isfinite(h).all() or residual > 1e-10:
                raise FloatingPointError('Unqualified adjoint Mueller solve')
        except Exception:
            self._record('failed_relaxation_adjoints', perf_counter()-started)
            raise
        self._record('relaxation_adjoints', perf_counter()-started)
        state._relaxation_components = (h, rows)
        return h, rows

    @geometry_validated
    def relaxation_gradient(self, prediction, observed, tau, update, space):
        from .relaxed_gradient import reduced_gradient
        started = perf_counter()
        self._record('relaxed_gradient_attempts')
        state = prediction._handle
        h, rows = self.relaxation_components(prediction)
        before = getattr(state.factors, 'fallback_count', 0)
        try:
            gradient, diagnostics = reduced_gradient(state, observed, tau, h, rows, space)
        except Exception:
            self._record('failed_relaxed_gradients', perf_counter()-started)
            raise
        if getattr(state.factors, 'fallback_count', 0) > before:
            self._record('factor_fallbacks', fallback='relaxed correction device solve OOM; retained host LU')
        prediction.diagnostics['relaxed_gradient'] = diagnostics
        self._record('relaxed_gradients', perf_counter()-started)
        return gradient

    def relaxation_weights(self, prediction, tau):
        from .full_matrix import receiver_weights
        h, rows = self.relaxation_components(prediction)
        return receiver_weights(h, rows, tau, paired=prediction._handle.acquisition.paired)

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
        if not np.isfinite(paired).all() or paired.max() <= 0:
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

    def select_stage(self, curve, stage, config, contrast, update, ledger):
        if self.execution.nodal_resolution_profile == 'fixed':
            return stage, None
        from .nodal_resolution import select_stage
        return select_stage(self, curve, stage, config, contrast, update, ledger)

    def audit_stage(self, stage):
        if self.execution.nodal_resolution_profile == 'band_matched':
            from dataclasses import replace
            return replace(stage, refined_nodes=max(2048, stage.refined_nodes))
        return stage

    def audit_reference_resolution(self, stage):
        return 1024 if self.execution.nodal_resolution_profile == 'band_matched' else None

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
