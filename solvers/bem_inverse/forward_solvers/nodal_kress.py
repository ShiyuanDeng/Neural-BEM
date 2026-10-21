"""Nodal Kress forward functions; the context retains settings and reusable geometry."""
from time import perf_counter
import numpy as np
from scipy.linalg import lu_factor
from .. import checks
from ..physics import Execution, NodalKress, Prediction
from ..continuation import forward as F
from ..continuation.geometry_runtime import geometry_validated
from gpr_bem_kress import cuda_assembly as CA
from gpr_bem_kress.execution import execution


@geometry_validated
def forward_solve(curve, observation, contrast, resolution, *, context=None):
    """Nodal forward fields for one frequency, with reusable factors for B7."""
    if context is None:
        context = NodalKress(Execution())
    started = perf_counter()
    context._record('evaluation_attempts')
    try:
        if complex(observation.wavenumber).imag == 0 and context.execution.nodal_geometry_reuse == 'off':
            state = F.solve(curve, float(np.real(observation.wavenumber)), contrast,
                            observation.acquisition, resolution, execution_backend=context.execution.device)
            fallback = 'real CUDA OOM' if state.backend == 'cpu-fallback' else None
        else:
            state, fallback = damped_forward_solve(curve, observation, contrast, resolution, context=context)
        context._record('evaluations', perf_counter()-started, state.backend, fallback)
        if getattr(state.factors, 'fallback_count', 0):
            context._record('factor_fallbacks', fallback='forward device solve OOM; retained host LU')
        return Prediction(state.prediction, dict(solver=context.name, device=state.backend,
            resolution=resolution, system_residual=state.system_residual, fallback=fallback), state)
    except Exception:
        context._record('failed_evaluations', perf_counter()-started)
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

