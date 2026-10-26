"""Modal Müller functions: forward_solve runs A1–A4; ModalMuller retains fit-local state.

Read forward_solve() → _solve() for A1–A4. The context class below holds
execution settings, caches and counters, and owns the derivative, the
resolution profile and the frontier.

Stored coefficients c → predicted measurements, with the factors and traces
that B7 reuses. One evaluation runs these separately timed stages:

1. geometry (A1): frequency-independent Laurent arrays, the certified log|W|^2
   interval and Chebyshev/regular-wave bases, cached per curve and window;
2. assembly (A2): the modal Müller matrix A_f at one frequency;
3. waves (A3): Graf source, receiver and reciprocal coefficients;
4. factorization (A4): dense LU of A_f;
5. fields (A4): traces u_D and q, then paired receiver data;
6. jacobian (B7, derivative only): reciprocal solve and Hadamard contraction.

Resolution tokens are 8*K_trace, where K_trace is the trace cutoff. The factor
only satisfies the shared FitStage guard token > 2*K_geometry, which dates from
nodal counts; the service never samples nodes. The coefficient window is
K_trace+window_margin, so a refined token raises both the trace cutoff and the
window. Log, radial, Graf and wave-series lengths are chosen from explicit
error bounds or coefficient decay. When a bound fails, the service raises
ValueError, and fit_stage records a numerical refusal.

Execution.device selects where A1 preparation and A2 assembly run. ``cpu`` is
the reference path. ``auto`` uses CUDA when available and falls back to the CPU
after device out-of-memory, recording it. ``cuda`` fails instead of falling
back. On CUDA, A1 and A2 run in modal_cuda. Scalar Bessel/Hankel values, Graf
waves, LU, fields and the Jacobian stay on the CPU, so handles hold no device
memory.

Selecting ``solver='modal_muller'`` needs ``register()``. Campaign entry points
live under experiments/cleaned_interface.
"""
from .. import checks
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from threading import Lock
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from bem_inverse.continuation import forward as F
from bem_inverse.continuation.geometry import FourierCurve
from gpr_bem_kress import cuda_assembly as CA
from ..a1_geometry import ModalGeometry, real_product
from ..a2_muller import muller_matrix
from ..a3_waves import point_kernels
from .. import a4_fields, b7_data_jacobian
from ..physics import Counters, Prediction, register_backend


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
    # Experimental independent accuracy slots. None preserves the historical
    # storage-to-trace profile and cutoff+margin coefficient window.
    coefficient_workspace: object = None
    trace_cutoff: object = None

    def __post_init__(self):
        if min(self.trace_minimum, self.trace_step, self.window_margin, self.cached_geometries) < 1:
            raise ValueError('Modal trace, window and cache settings must be positive.')
        for name in ('coefficient_workspace', 'trace_cutoff'):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or int(value) != value or value < 1):
                raise ValueError(f'{name} must be a positive integer or None.')


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


def forward_solve(curve, observation, contrast, resolution, *, context=None):
    """A1–A4 for one frequency; retain factors/traces for B7.

    Pass a fit-local ModalMuller context to reuse geometry and execution settings.
    Without one, use a fresh default context. Observations supply acquisition and
    wavenumber; measured data are not used by this calculation.
    """
    if context is None:
        from ..physics import Execution
        context = ModalMuller(Execution())
    started = perf_counter()
    context.counters.record('evaluation_attempts')
    try:
        prediction = _solve(curve, observation, contrast, trace_cutoff(int(resolution)), context=context)
    except Exception:
        context.counters.record('failed_evaluations', perf_counter()-started)
        raise
    context.counters.record('evaluations', perf_counter()-started, prediction.diagnostics['device'],
                            prediction.diagnostics['fallback'])
    return prediction


def _solve(curve, observation, contrast, cutoff, *, context):
    s = context.settings
    k = complex(observation.wavenumber)
    k = k.real if k.imag == 0 else k
    checks.require_material_frequency(k, contrast)
    acquisition = observation.acquisition
    if not isinstance(acquisition, F.PointSourceAcquisition) or not acquisition.paired:
        raise ValueError('modal_muller supports paired point-source acquisition only.')
    ki = k*np.sqrt(contrast)
    window = s.coefficient_workspace or cutoff+s.window_margin
    checks.require_geometry_workspace(window, cutoff, curve.band)
    # A1–A2. Exact geometry cache, then device-selected Müller assembly.
    geometry, (A_f, radial, device, fallback) = assemble_matrix(curve, window, k, ki, cutoff, context=context)
    # A3. Graf source and receiver trace/flux coefficients.
    with context._stage('waves'):
        options = dict(tolerance=s.graf_tolerance, series_loss=s.series_loss)
        sources, receivers = point_kernels(geometry, k, (acquisition.sources, acquisition.receivers), **options)
    # A4. Factor once; retain factors and traces for B7.
    with context._stage('factorization'):
        factors = a4_fields.factorize(A_f)
    with context._stage('fields'):
        window = geometry.band
        fields = a4_fields.solve_and_predict(
            A_f, factors, sources, receivers, cutoff, window, acquisition.strength)
        rhs, traces, residual, receiver, prediction, test = fields
    checks.require_finite_prediction(prediction)
    state = ModalState(k, ki, acquisition, cutoff, curve.coefficients.copy(), factors, traces,
                       np.vstack((receivers[0][test], receivers[1][test])))
    if context.observer is not None:
        with context._stage('recording_io'):
            context.observer('field', dict(state=state, observation=observation,
                contrast=contrast, execution=asdict(context.execution),
                calculation_role=getattr(context,'calculation_role','production'),
                workspace=window, A=A_f, B_s=rhs, B_r=state.reciprocal_rhs,
                R=receiver, X_s=traces, prediction=prediction,
                system_residual=residual))
    interval = geometry.log_interval
    return Prediction(prediction, dict(solver=context.name, device=device, resolution=token(cutoff),
        K_trace=cutoff, window=window, system_residual=residual, fallback=fallback, log_degree=interval['degree'],
        log_lower=interval['lower'], log_upper=interval['upper'], radial_upper=geometry.radial_upper,
        **radial, graf_order=max(sources[2]['graf_order'], receivers[2]['graf_order']),
        series_terms=sources[2]['series_terms'], series_loss=sources[2]['series_loss']), state)


def prepare_geometry(curve, window, device, *, context):
    key = (curve.coefficients.tobytes(), window, device)
    with context._lock:
        slot = context._geometries.get(key)
        if slot is None:
            slot = context._geometries[key] = [Lock(), None]
            while len(context._geometries) > context.settings.cached_geometries:
                context._geometries.popitem(last=False)
        else:
            context._geometries.move_to_end(key)
            context.counters.count('geometry_cache_hits')
    with slot[0]:
        if slot[1] is None:
            options = dict(log_tolerance=context.settings.log_tolerance, max_log_degree=context.settings.max_log_degree)
            with context._stage('geometry'):
                if device == 'cpu':
                    slot[1] = ModalGeometry(curve, window, workers=context.execution.frequency_threads, **options)
                else:
                    from ..modal_cuda import DeviceModalGeometry
                    with CA._device_work:
                        slot[1] = DeviceModalGeometry(curve, window, device=device, **options)
        return slot[1]


def assemble_matrix(curve, window, k, ki, cutoff, *, context):
    """Geometry and assembly on the selected device; auto retries on the CPU after OOM."""
    device = context._device()
    if device == 'cpu':
        geometry = prepare_geometry(curve, window, 'cpu', context=context)
        with context._stage('assembly'):
            return geometry, (*muller_matrix(geometry, k, ki, cutoff, tolerance=context.settings.radial_tolerance,
                                             basis_workers=context.execution.frequency_threads), 'cpu-modal',
                              'CUDA unavailable' if context.execution.device == 'auto' else None)
    from .. import modal_cuda
    try:
        geometry = prepare_geometry(curve, window, device, context=context)
        with context._stage('assembly'):
            queued = perf_counter()
            with CA._device_work:
                context.counters.record('assembly_gpu_queue', perf_counter()-queued)
                timing = {}
                try:
                    matrix = modal_cuda.muller_matrix(geometry, k, ki, cutoff,
                        tolerance=context.settings.radial_tolerance, timing=timing)
                finally:
                    for kind, elapsed in timing.items():
                        context.counters.record(kind, elapsed)
                return geometry, (*matrix, 'cuda-modal', None)
    except Exception as exc:
        if context.execution.device != 'auto' or not CA.out_of_memory(exc):
            raise
        with context._lock:
            context._geometries.pop((curve.coefficients.tobytes(), window, device), None)
        CA.record_fallback('modal geometry/assembly')
    geometry = prepare_geometry(curve, window, 'cpu', context=context)
    with context._stage('assembly'):
        return geometry, (*muller_matrix(geometry, k, ki, cutoff, tolerance=context.settings.radial_tolerance,
                                         basis_workers=context.execution.frequency_threads),
                          'cpu-modal', 'modal CUDA OOM')


class ModalMuller:
    name = 'modal_muller'

    def __init__(self, execution_settings, settings=None, observer=None):
        self.execution = execution_settings
        self.settings = settings or ModalSettings()
        self.observer = observer
        self._lock = Lock()  # guards the geometry cache
        self._geometries = OrderedDict()
        self.counters = Counters(evaluation_attempts=0, evaluations=0, failed_evaluations=0,
                                 derivative_attempts=0, derivatives=0, failed_derivatives=0, disk_batches=0,
                                 geometry_cache_hits=0)

    @contextmanager
    def _stage(self, kind):
        started = perf_counter()
        try:
            yield
        finally:
            self.counters.record(kind, perf_counter()-started)

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

    def resolution_profile(self, storage_band, *, trace_cutoff=None):
        s = self.settings
        production = (s.trace_cutoff if s.trace_cutoff is not None else
                      max(s.trace_minimum, s.trace_step*(int(np.ceil(storage_band/64))+1)))
        if trace_cutoff is not None:
            if isinstance(trace_cutoff, bool) or not isinstance(trace_cutoff, int) or trace_cutoff < 1:
                raise ValueError('Trace cutoff must be a positive integer.')
            production = trace_cutoff
        refined = production+s.trace_step
        workspace = lambda k: s.coefficient_workspace or k+s.window_margin
        return dict(production=token(production), refined=token(refined), kind='modal_muller',
                    nodal_resolution=None, token='8*K_trace', K_trace=production, K_trace_refined=refined,
                    coefficient_workspace=dict(production=workspace(production),
                                               refined=workspace(refined)),
                    refinement=f'raise K_trace by {s.trace_step}; '
                               + ('hold coefficient workspace fixed; ' if s.coefficient_workspace else
                                  f'raise coefficient window by {s.trace_step}; ')+
                               'frontier and endpoint audit only')

    def _contract(self, state, weights):
        jacobian, reciprocal = b7_data_jacobian.reciprocal_jacobian(state, weights)
        checks.require_finite_data_jacobian(jacobian)
        if self.observer is not None:
            with self._stage('recording_io'):
                self.observer('reciprocal', dict(state=state, X_r=reciprocal,
                    normal_velocity_weights=weights, J=jacobian))
        return jacobian

    def _derivative(self, state, weights):
        started = perf_counter()
        self.counters.record('derivative_attempts')
        try:
            with self._stage('jacobian'):
                result = self._contract(state, weights)
        except Exception:
            self.counters.record('failed_derivatives', perf_counter()-started)
            raise
        self.counters.record('derivatives', perf_counter()-started)
        return result

    def derivative(self, prediction, update, space):
        """Complete-trial derivative: w_i=Re(V_i conj N) from SC-035 coefficient velocities."""
        state = prediction._handle
        velocities = getattr(space, 'derivatives', None)
        if velocities is None:
            raise TypeError('modal_muller needs Cartesian coefficient velocities (ProjectedUpdate spaces).')
        if not np.array_equal(space.curve.coefficients, state.coefficients):
            raise ValueError('Update space and prediction belong to different curves.')
        weights = b7_data_jacobian.normal_velocity_weights(state.coefficients, velocities)
        return self._derivative(state, weights)

    def observable_frontier(self, prediction, top, threshold):
        """Highest normal mode whose paired Jacobian column passes ``threshold``, from a forward solve."""
        from ..normal_basis import orthonormal_normal_basis
        state = prediction._handle
        curve = FourierCurve(state.coefficients)
        # Geometry-side samples of h(s(t))|z'(t)|: arclength harmonics need the arclength map.
        width = 2*state.cutoff
        count = int(2**np.ceil(np.log2(max(1024, 4*(2*width+2*top+curve.band+1)))))
        nodes = curve.nodes(count)
        samples = orthonormal_normal_basis(nodes, top)*nodes.speeds[:, None]
        weights = (np.fft.fft(samples, axis=0)/count)[np.arange(-width, width+1) % count]
        jacobian = self._derivative(state, weights)
        norms = np.linalg.norm(jacobian, axis=0)
        paired = np.r_[norms[0], np.hypot(norms[1::2], norms[2::2])]
        checks.require_observable_frontier(paired)
        frontier = int(np.flatnonzero(paired >= threshold*paired.max()).max())
        return dict(frontier=frontier, column_profile=paired, threshold=threshold, top=top, work_units=2)

    def receipt(self):
        recorded = self.counters.snapshot()
        stages = ('geometry', 'waves', 'assembly', 'factorization', 'fields', 'jacobian')
        return dict(solver=self.name, execution=asdict(self.execution), settings=asdict(self.settings),
            **recorded, stage_seconds={k: recorded['seconds'].get(k, 0.) for k in stages},
            work_semantics='actual dispatched evaluations and derivative batches, including speculative threads; '
                           'optimizer ledger separately retains SPD reservation/charge semantics',
            localization_model='exact homogeneous disk Mie series, qualified by selected backend',
            discretization='Fourier-Galerkin traces |m|<=K_trace; Chebyshev radial and log|W|^2 '
                           'expansions on window K_trace+margin; Graf sources/receivers; no boundary collocation',
            sampling=dict(operator_boundary_collocation=False, interval_proposal_torus_grid=True,
                          frontier_geometry_quadrature=True, end_to_end_sample_free=False),
            certificate_arithmetic='exact-arithmetic residual inequality with heuristic FFT allowance; '
                                   'not interval verified',
            execution_note='Execution.device selects geometry preparation and assembly (modal_cuda on CUDA); '
                           'scalar kernels, Graf waves, LU, fields and Jacobian on the CPU; '
                           'Execution.acceleration selects only the Mie grid; Execution.resolution is not used',
            retained_state=f'up to {self.settings.cached_geometries} prepared geometries per device '
                           '(device arrays for CUDA); LU factors on the host in handles')


def register():
    """Make ``solver='modal_muller'`` available through make_backend (idempotent)."""
    try:
        register_backend('modal_muller', ModalMuller, forward_solve)
    except ValueError:
        pass
