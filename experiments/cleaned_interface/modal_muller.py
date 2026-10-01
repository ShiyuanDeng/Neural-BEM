"""Node-free modal Müller physics service, with the same contract as NodalKress.

One evaluation runs six separately timed stages:

1. geometry: frequency-independent Laurent arrays, the certified log|W|^2
   interval, and Chebyshev/regular-wave bases (cached per curve and window);
2. waves: Graf source and receiver coefficients at one wavenumber;
3. assembly: the modal Müller matrix;
4. factorization: dense LU;
5. fields: traces and paired receiver data;
6. jacobian: reciprocal solve and Hadamard contraction (derivative only).

Resolution tokens are 8*K_trace, where K_trace is the trace cutoff. The factor
only satisfies the shared FitStage guard token > 2*K_geometry, which dates from
nodal counts; the service never samples nodes. The coefficient window is
K_trace+window_margin, so a refined token raises both the trace cutoff and the
window. Log, radial, Graf and wave-series lengths are chosen from explicit
error bounds or coefficient decay. When a bound fails, the service raises
ValueError, and LM records a numerical refusal.

Execution.device selects where geometry preparation and assembly run.
``cpu`` is the reference path. ``auto`` uses CUDA when available and falls back
to the CPU after device out-of-memory, recording it. ``cuda`` fails instead of
falling back. On CUDA, geometry preparation and assembly run in modal_cuda.
Scalar Bessel/Hankel values, Graf waves, LU, fields and the Jacobian stay on the
CPU, so handles hold no device memory.

Selecting ``solver='modal_muller'`` needs ``register()``, or
``python -m experiments.cleaned_interface.modal_muller <command> --solver modal_muller``.
Registration is explicit, so the frozen CI-001 sources stay unchanged.
"""
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from threading import Lock
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from experiments.shape_continuation import forward as F
from experiments.shape_continuation.geometry import FourierCurve
from gpr_bem_kress import cuda_assembly as CA
from .modal_geometry import ModalGeometry, real_product
from .modal_operator import hadamard, muller_matrix, point_kernels
from .physics import NodalKress, Prediction, register_backend


TOKENS_PER_MODE = 8


def token(trace_cutoff):
    """Opaque resolution token for a trace cutoff K_trace."""
    return TOKENS_PER_MODE*int(trace_cutoff)


def trace_cutoff(resolution):
    if resolution % TOKENS_PER_MODE or resolution <= 0:
        raise ValueError(f'modal_muller resolution tokens are positive multiples of {TOKENS_PER_MODE} (8*K_trace).')
    return resolution//TOKENS_PER_MODE


@dataclass(frozen=True)
class ModalSettings:
    trace_minimum: int = 64
    trace_step: int = 32
    window_margin: int = 64
    log_tolerance: float = 1e-16
    radial_tolerance: float = 1e-15
    graf_tolerance: float = 1e-16
    series_loss: float = 1e-9
    max_log_degree: int = 4000
    cached_geometries: int = 4

    def __post_init__(self):
        if min(self.trace_minimum, self.trace_step, self.window_margin, self.cached_geometries) < 1:
            raise ValueError('Modal trace, window and cache settings must be positive.')


@dataclass(frozen=True)
class ModalState:
    """Opaque handle: only this service reads it."""
    wavenumber: complex
    interior_wavenumber: complex
    acquisition: object
    cutoff: int
    coefficients: np.ndarray
    factors: tuple
    traces: np.ndarray
    reciprocal_rhs: np.ndarray


class ModalMuller:
    name = 'modal_muller'

    def __init__(self, execution_settings, settings=None):
        self.execution = execution_settings
        self.settings = settings or ModalSettings()
        self._lock = Lock()
        self._geometries = OrderedDict()
        self._counts = dict(evaluation_attempts=0, evaluations=0, failed_evaluations=0,
                            derivative_attempts=0, derivatives=0, failed_derivatives=0, disk_batches=0,
                            geometry_cache_hits=0)
        self._devices = {}
        self._fallbacks = {}
        self._seconds = {}

    def _record(self, kind, seconds=0., device=None, fallback=None):
        with self._lock:
            self._counts[kind] = self._counts.get(kind, 0)+1
            self._seconds[kind] = self._seconds.get(kind, 0.)+seconds
            if device:
                self._devices[device] = self._devices.get(device, 0)+1
            if fallback:
                self._fallbacks[fallback] = self._fallbacks.get(fallback, 0)+1

    @contextmanager
    def _stage(self, kind):
        started = perf_counter()
        yield
        self._record(kind, perf_counter()-started)

    def validate(self, problem):
        if problem.material != 'equal_density_homogeneous' or not isinstance(problem.initial, FourierCurve):
            raise ValueError('modal_muller requires a single Fourier curve and equal-density homogeneous material.')
        if any(not isinstance(o.acquisition, F.PointSourceAcquisition) or not o.acquisition.paired
               for o in (*problem.real, *problem.damped)):
            raise ValueError('The modal Hadamard contraction and CI-001 localization require paired point sources.')
        if self.execution.device == 'cuda' and not CA.available():
            raise RuntimeError('Explicit CUDA execution requested, but no CUDA device is available.')

    def _device(self):
        selected = self.execution.device
        if selected == 'cuda' and not CA.available():
            raise RuntimeError('Explicit CUDA execution requested, but no CUDA device is available.')
        return 'cuda' if selected != 'cpu' and CA.available() else 'cpu'

    def resolution_profile(self, storage_band):
        s = self.settings
        production = max(s.trace_minimum, s.trace_step*(int(np.ceil(storage_band/64))+1))
        refined = production+s.trace_step
        return dict(production=token(production), refined=token(refined), kind='modal_muller',
                    nodal_resolution=None, token='8*K_trace', K_trace=production, K_trace_refined=refined,
                    coefficient_workspace=dict(production=production+s.window_margin,
                                               refined=refined+s.window_margin),
                    refinement=f'raise K_trace and coefficient window by {s.trace_step}; '
                               'refuse candidates outside per-frequency tolerance')

    def refine_resolution(self, resolution):
        return token(trace_cutoff(resolution)+self.settings.trace_step)

    def ordered_calls(self, function, items):
        return F.ordered_calls(function, items, threads=self.execution.frequency_threads)

    def _geometry(self, curve, window, device):
        key = (curve.coefficients.tobytes(), window, device)
        with self._lock:
            slot = self._geometries.get(key)
            if slot is None:
                slot = self._geometries[key] = [Lock(), None]
                while len(self._geometries) > self.settings.cached_geometries:
                    self._geometries.popitem(last=False)
            else:
                self._geometries.move_to_end(key)
                self._counts['geometry_cache_hits'] += 1
        with slot[0]:
            if slot[1] is None:
                options = dict(log_tolerance=self.settings.log_tolerance, max_log_degree=self.settings.max_log_degree)
                with self._stage('geometry'):
                    if device == 'cpu':
                        slot[1] = ModalGeometry(curve, window, workers=self.execution.frequency_threads, **options)
                    else:
                        from .modal_cuda import DeviceModalGeometry
                        with CA._device_work:
                            slot[1] = DeviceModalGeometry(curve, window, device=device, **options)
            return slot[1]

    def _matrix(self, curve, window, k, ki, cutoff):
        """Geometry and assembly on the selected device; auto retries on the CPU after OOM."""
        device = self._device()
        if device == 'cpu':
            geometry = self._geometry(curve, window, 'cpu')
            with self._stage('assembly'):
                return geometry, (*muller_matrix(geometry, k, ki, cutoff, tolerance=self.settings.radial_tolerance,
                                                 basis_workers=self.execution.frequency_threads), 'cpu-modal',
                                  'CUDA unavailable' if self.execution.device == 'auto' else None)
        from . import modal_cuda
        try:
            geometry = self._geometry(curve, window, device)
            with self._stage('assembly'), CA._device_work:
                return geometry, (*modal_cuda.muller_matrix(geometry, k, ki, cutoff,
                                                            tolerance=self.settings.radial_tolerance),
                                  'cuda-modal', None)
        except Exception as exc:
            if self.execution.device != 'auto' or not CA.out_of_memory(exc):
                raise
            with self._lock:
                self._geometries.pop((curve.coefficients.tobytes(), window, device), None)
            CA.record_fallback('modal geometry/assembly')
        geometry = self._geometry(curve, window, 'cpu')
        with self._stage('assembly'):
            return geometry, (*muller_matrix(geometry, k, ki, cutoff, tolerance=self.settings.radial_tolerance,
                                             basis_workers=self.execution.frequency_threads),
                              'cpu-modal', 'modal CUDA OOM')

    def evaluate(self, curve, observation, contrast, resolution):
        started = perf_counter()
        self._record('evaluation_attempts')
        try:
            prediction = self._evaluate(curve, observation, contrast, trace_cutoff(int(resolution)))
        except Exception:
            self._record('failed_evaluations', perf_counter()-started)
            raise
        self._record('evaluations', perf_counter()-started, prediction.diagnostics['device'],
                     prediction.diagnostics['fallback'])
        return prediction

    def _evaluate(self, curve, observation, contrast, cutoff):
        s = self.settings
        k = complex(observation.wavenumber)
        k = k.real if k.imag == 0 else k
        if not (np.isfinite(k) and np.real(k) > 0 and np.imag(k) >= 0 and np.isfinite(contrast) and contrast > 0):
            raise ValueError('Wavenumber and contrast must be finite and positive.')
        acquisition = observation.acquisition
        if not isinstance(acquisition, F.PointSourceAcquisition) or not acquisition.paired:
            raise ValueError('modal_muller supports paired point-source acquisition only.')
        ki = k*np.sqrt(contrast)
        geometry, (matrix, radial, device, fallback) = self._matrix(curve, cutoff+s.window_margin, k, ki, cutoff)
        with self._stage('waves'):
            options = dict(tolerance=s.graf_tolerance, series_loss=s.series_loss)
            sources, receivers = point_kernels(geometry, k, (acquisition.sources, acquisition.receivers), **options)
        with self._stage('factorization'):
            factors = lu_factor(matrix, check_finite=True)
        with self._stage('fields'):
            window = geometry.band
            test, trial = window+np.arange(-cutoff, cutoff+1), window-np.arange(-cutoff, cutoff+1)
            rhs = np.vstack((sources[0][test], sources[1][test]))*acquisition.strength
            traces = lu_solve(factors, rhs)
            residual = float(np.linalg.norm(matrix@traces-rhs)/np.linalg.norm(rhs))
            receiver = 2*np.pi*np.hstack((receivers[1][trial].T, -receivers[0][trial].T))
            prediction = np.einsum('ri,ir->r', receiver, traces)
        if not np.isfinite(prediction).all():
            raise FloatingPointError('Nonfinite modal prediction')
        state = ModalState(k, ki, acquisition, cutoff, curve.coefficients.copy(), factors, traces,
                           np.vstack((receivers[0][test], receivers[1][test])))
        interval = geometry.log_interval
        return Prediction(prediction, dict(solver=self.name, device=device, resolution=token(cutoff),
            K_trace=cutoff, window=window, system_residual=residual, fallback=fallback, log_degree=interval['degree'],
            log_lower=interval['lower'], log_upper=interval['upper'], radial_upper=geometry.radial_upper,
            **radial, graf_order=max(sources[2]['graf_order'], receivers[2]['graf_order']),
            series_terms=sources[2]['series_terms'], series_loss=sources[2]['series_loss']), state)

    def _contract(self, state, weights):
        count = 2*state.cutoff+1
        reciprocal = lu_solve(state.factors, state.reciprocal_rhs)
        factor = state.interior_wavenumber**2-state.wavenumber**2
        jacobian = hadamard(state.traces[:count], reciprocal[:count], weights, state.cutoff, factor)
        if not np.isfinite(jacobian).all():
            raise FloatingPointError('Nonfinite modal shape Jacobian.')
        return jacobian

    def _derivative(self, state, weights):
        started = perf_counter()
        self._record('derivative_attempts')
        try:
            with self._stage('jacobian'):
                result = self._contract(state, weights)
        except Exception:
            self._record('failed_derivatives', perf_counter()-started)
            raise
        self._record('derivatives', perf_counter()-started)
        return result

    def derivative(self, prediction, update, space):
        """Complete-trial derivative: w_i=Re(V_i conj N) from SC-035 coefficient velocities."""
        state = prediction._handle
        velocities = getattr(space, 'derivatives', None)
        if velocities is None:
            raise TypeError('modal_muller needs Cartesian coefficient velocities (ProjectedUpdate spaces).')
        if not np.array_equal(space.curve.coefficients, state.coefficients):
            raise ValueError('Update space and prediction belong to different curves.')
        band = len(state.coefficients)//2
        normal = np.arange(-band, band+1)*state.coefficients
        weights = real_product(velocities.T, normal[None, :], 1).T
        return self._derivative(state, weights)

    def observable_frontier(self, curve, observation, contrast, top, threshold):
        from experiments.shape_continuation.atlas import orthonormal_normal_basis
        state = self.evaluate(curve, observation, contrast,
                              self.resolution_profile(curve.band)['refined'])._handle
        # Geometry-side samples of h(s(t))|z'(t)|: arclength harmonics need the arclength map.
        width = 2*state.cutoff
        count = int(2**np.ceil(np.log2(max(1024, 4*(2*width+2*top+curve.band+1)))))
        nodes = curve.nodes(count)
        samples = orthonormal_normal_basis(nodes, top)*nodes.speeds[:, None]
        weights = (np.fft.fft(samples, axis=0)/count)[np.arange(-width, width+1) % count]
        jacobian = self._derivative(state, weights)
        norms = np.linalg.norm(jacobian, axis=0)
        paired = np.r_[norms[0], np.hypot(norms[1::2], norms[2::2])]
        if not np.isfinite(paired).all() or paired.max() <= 0:
            raise FloatingPointError('No finite nonzero observable frontier')
        frontier = int(np.flatnonzero(paired >= threshold*paired.max()).max())
        return dict(frontier=frontier, column_profile=paired, threshold=threshold, top=top, work_units=2)

    # The exact homogeneous-disk Mie grid does not depend on the boundary discretization.
    disk_landscape = NodalKress.disk_landscape

    def receipt(self):
        with self._lock:
            stages = ('geometry', 'waves', 'assembly', 'factorization', 'fields', 'jacobian')
            return dict(solver=self.name, execution=asdict(self.execution), settings=asdict(self.settings),
                counts=dict(self._counts), devices=dict(self._devices), fallback_reasons=dict(self._fallbacks),
                seconds=dict(self._seconds), stage_seconds={k: self._seconds.get(k, 0.) for k in stages},
                work_semantics='actual dispatched evaluations and derivative batches, including speculative threads; '
                               'optimizer ledger separately retains SPD reservation/charge semantics',
                localization_model='exact homogeneous disk Mie series, qualified by selected backend',
                discretization='Fourier-Galerkin traces |m|<=K_trace; Chebyshev radial and log|W|^2 '
                               'expansions on window K_trace+margin; Graf sources/receivers; no boundary nodes',
                execution_note='Execution.device selects geometry preparation and assembly (modal_cuda on CUDA); '
                               'scalar kernels, Graf waves, LU, fields and Jacobian on the CPU; '
                               'Execution.acceleration selects only the Mie grid; Execution.resolution is not used',
                retained_state=f'up to {self.settings.cached_geometries} prepared geometries per device '
                               '(device arrays for CUDA); LU factors on the host in handles')


def register():
    """Make ``solver='modal_muller'`` available through make_backend (idempotent)."""
    try:
        register_backend('modal_muller', ModalMuller)
    except ValueError:
        pass


if __name__ in ('__main__', '__mp_main__'):
    # Spawned campaign workers import this entry module as __mp_main__.
    register()
    if __name__ == '__main__':
        from .__main__ import main
        main()
