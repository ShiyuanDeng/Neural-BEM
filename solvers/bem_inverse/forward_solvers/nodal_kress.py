"""Nodal Kress forward functions and their fit-local context.

``forward_solve`` runs A1–A4 at one frequency. The ``NodalKress`` context holds
execution settings, counters and reusable geometry, and owns the reciprocal
derivative, the resolution profile and the frontier.
"""
from dataclasses import asdict
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor
from .. import checks
from ..physics import Counters, Execution, Prediction, register_backend
from ..continuation import forward as F
from ..continuation.geometry import FourierCurve
from ..continuation.geometry_runtime import geometry_validated
from ..nodal_geometry import GeometryCache
from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.execution import execution


@geometry_validated
def forward_solve(curve, observation, contrast, resolution, *, context=None):
    """Nodal forward fields for one frequency, with reusable factors for B7."""
    if context is None:
        context = NodalKress(Execution())
    started = perf_counter()
    context.counters.record('evaluation_attempts')
    try:
        if complex(observation.wavenumber).imag == 0 and context.execution.nodal_geometry_reuse == 'off':
            state = F.solve(curve, float(np.real(observation.wavenumber)), contrast,
                            observation.acquisition, resolution, execution_backend=context.execution.device)
            fallback = 'real CUDA OOM' if state.backend == 'cpu-fallback' else None
        else:
            state, fallback = damped_forward_solve(curve, observation, contrast, resolution, context=context)
        context.counters.record('evaluations', perf_counter()-started, state.backend, fallback)
        if getattr(state.factors, 'fallback_count', 0):
            context.counters.record('factor_fallbacks', fallback='forward device solve OOM; retained host LU')
        return Prediction(state.prediction, dict(solver=context.name, device=state.backend,
            resolution=resolution, system_residual=state.system_residual, fallback=fallback), state)
    except Exception:
        context.counters.record('failed_evaluations', perf_counter()-started)
        raise


def damped_forward_solve(shape, observation, contrast, nodes, *, context):
    k = complex(observation.wavenumber)
    if checks.invalid_nodal_material(k, contrast):
        raise ValueError('Invalid damped material/wavenumber')
    curve, adapter, prepared = context._geometry_cache.get(shape, nodes, context.execution.device,
        enabled=context.execution.nodal_geometry_reuse == 'per_curve')
    assemble, receivers, incident = F._operators(curve)
    ki, acquisition = k * np.sqrt(contrast), observation.acquisition
    selected = context.execution.device
    available = CA.available() if selected != 'cpu' else False
    if selected == 'cuda' and not available:
        raise RuntimeError('Explicit CUDA requested, but no CUDA device is available.')
    device = selected != 'cpu' and available and context.execution.acceleration == 'spd016'
    reason = None
    if selected == 'auto' and not available:
        reason = 'CUDA unavailable'
    elif context.execution.acceleration == 'reference':
        if selected == 'cuda':
            raise ValueError('Damped reference execution requires CPU')
        reason = 'reference damped execution requested'
    with execution(kernels='reference', device='cpu'):
        if device:
            try:
                from ..damped_cuda import gpu_matrix
                with CA._device_work:
                    if k.imag:
                        matrix = gpu_matrix(curve, k, ki, context._ray_table(), adapter=adapter, prepared=prepared)
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
    if checks.nonfinite_prediction(prediction):
        raise FloatingPointError('Nonfinite damped prediction')
    state = F.ForwardState(curve, k, ki, acquisition, matrix, factors, traces,
                           prediction, residual, ('cuda-damped' if k.imag else 'cuda') if device else 'cpu-damped')
    return state, reason


class NodalKress:
    name = 'nodal_kress'

    def __init__(self, execution_settings):
        self.execution = execution_settings
        self.counters = Counters(evaluation_attempts=0, evaluations=0, failed_evaluations=0,
                                 derivative_attempts=0, derivatives=0, failed_derivatives=0, disk_batches=0)
        self._table = None
        self._geometry_cache = GeometryCache()

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

    def _ray_table(self):
        # Assembly callers also hold the device lock; publication is serialized.
        if self._table is None:
            from ..damped_cuda import RayTable
            started = perf_counter()
            self._table = RayTable(.25)
            self.counters.record('ray_table_setup', perf_counter()-started)
        return self._table

    @geometry_validated
    def derivative(self, prediction, update, space):
        started = perf_counter()
        self.counters.record('derivative_attempts')
        state = prediction._handle
        before = getattr(state.factors, 'fallback_count', 0)
        try:
            result = F.shape_jacobian(state, update.velocities(space, state.curve))
        except Exception:
            self.counters.record('failed_derivatives', perf_counter()-started)
            raise
        if getattr(state.factors, 'fallback_count', 0) > before:
            self.counters.record('factor_fallbacks', fallback='reciprocal device solve OOM; retained host LU')
        self.counters.record('derivatives', perf_counter()-started)
        return result

    @geometry_validated
    def observable_frontier(self, prediction, top, threshold):
        """Highest normal mode whose paired Jacobian column passes ``threshold``, from a forward solve."""
        from ..normal_basis import orthonormal_normal_basis
        state = prediction._handle
        started = perf_counter()
        self.counters.record('derivative_attempts')
        before = getattr(state.factors, 'fallback_count', 0)
        try:
            jacobian = F.shape_jacobian(state, orthonormal_normal_basis(state.curve, top))
        except Exception:
            self.counters.record('failed_derivatives', perf_counter()-started)
            raise
        if getattr(state.factors, 'fallback_count', 0) > before:
            self.counters.record('factor_fallbacks', fallback='frontier device solve OOM; retained host LU')
        self.counters.record('derivatives', perf_counter()-started)
        norms = np.linalg.norm(jacobian.reshape(-1, jacobian.shape[-1]), axis=0)
        paired = np.r_[norms[0], np.hypot(norms[1::2], norms[2::2])]
        if checks.unobservable_frontier(paired):
            raise FloatingPointError('No finite nonzero observable frontier')
        frontier = int(np.flatnonzero(paired >= threshold * paired.max()).max())
        return dict(frontier=frontier, column_profile=paired, threshold=threshold, top=top, work_units=2)

    def close(self):
        self._geometry_cache.clear()

    def receipt(self):
        geometry_cache = self._geometry_cache.receipt()
        recorded = self.counters.snapshot()
        devices = recorded['devices']
        return dict(solver=self.name, execution=asdict(self.execution), geometry_cache=geometry_cache,
            component_devices=dict(assembly=dict(cuda=sum(v for k,v in devices.items() if k.startswith('cuda')),
                                                  cpu=sum(v for k,v in devices.items() if k.startswith('cpu'))),
                LU=dict(cuda=sum(v for k,v in devices.items() if k.startswith('cuda')),
                        cpu=sum(v for k,v in devices.items() if k.startswith('cpu'))),
                field_evaluation='cpu', jacobian_contraction='cpu', reciprocal_solve='same as forward factors'),
            **recorded,
            work_semantics='actual dispatched evaluations and derivative batches, including speculative threads; '
                           'optimizer ledger separately retains SPD reservation/charge semantics',
            localization_model='exact homogeneous disk Mie series, qualified by selected backend',
            ray=dict(gamma=.25, lo=.01, hi=100., panels=111, degree=24),
            retained_device_state='ray table and bounded geometry cache; matrix and reusable LU factors retained on host')


register_backend('nodal_kress', NodalKress, forward_solve)
