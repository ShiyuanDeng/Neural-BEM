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

from experiments.shape_continuation import forward as F
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.geometry_runtime import geometry_validated
from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.execution import execution


@dataclass(frozen=True)
class Execution:
    device: str = 'auto'
    frequency_threads: int = 4
    acceleration: str = 'spd016'
    geometry: str = 'both'
    resolution: int = 512

    def __post_init__(self):
        if self.device not in ('auto', 'cpu', 'cuda'):
            raise ValueError('device must be auto, cpu or cuda')
        if self.acceleration not in ('reference', 'spd016'):
            raise ValueError('acceleration must be reference or spd016')
        if self.frequency_threads < 1 or int(self.frequency_threads) != self.frequency_threads:
            raise ValueError('frequency_threads must be a positive integer')
        if self.geometry not in ('reference', 'cache', 'spatial', 'both'):
            raise ValueError('Unknown geometry runtime')
        if self.resolution < 512 or self.resolution % 2:
            raise ValueError('The nodal accuracy profile needs an even resolution >=512')


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
            if complex(observation.wavenumber).imag == 0:
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
        if k.real <= 0 or k.imag <= 0 or not np.isfinite(k) or contrast <= 0 or not np.isfinite(contrast):
            raise ValueError('Invalid damped material/wavenumber')
        curve = shape.nodes(nodes)
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
                        matrix = gpu_matrix(curve, k, ki, self._ray_table())
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
                               prediction, residual, 'cuda-damped' if device else 'cpu-damped')
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
        return h, rows

    def relaxation_weights(self, prediction, tau):
        from .full_matrix import receiver_weights
        h, rows = self.relaxation_components(prediction)
        return receiver_weights(h, rows, tau, paired=prediction._handle.acquisition.paired)

    @geometry_validated
    def observable_frontier(self, curve, observation, contrast, top, threshold):
        from experiments.shape_continuation.atlas import orthonormal_normal_basis
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
        from experiments.modal_atlas.mie_localize import landscape
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

    def receipt(self):
        with self._lock:
            return dict(solver=self.name, execution=asdict(self.execution), counts=dict(self._counts),
                devices=dict(self._devices), fallback_reasons=dict(self._fallbacks), seconds=dict(self._seconds),
                work_semantics='actual dispatched evaluations and derivative batches, including speculative threads; '
                               'optimizer ledger separately retains SPD reservation/charge semantics',
                localization_model='exact homogeneous disk Mie series, qualified by selected backend',
                ray=dict(gamma=.25, lo=.01, hi=100., panels=111, degree=24),
                retained_device_state='one ray table; matrix and reusable LU factors retained on host')


register_backend('nodal_kress', NodalKress)
