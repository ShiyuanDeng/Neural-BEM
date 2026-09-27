"""Equal-density transmission, dimensionless k, plane waves, full aperture."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from contextlib import contextmanager, nullcontext
from contextvars import copy_context
from functools import partial
import os
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from gpr_bem_kress import (build_muller_system, build_exterior_receiver_operator,
                           kress_incident_trace_on_boundary)
from gpr_bem_kress import cuda_assembly
from gpr_bem_kress.execution import execution
from ordered_boundary import OrderedBoundary2D
from ordered_boundary.validation_cache import current_validation_cache, validation_cache
from gpr_bem_kress.multicomponent import (
    build_multicomponent_muller_system,
    build_multicomponent_exterior_receiver_operator,
    multicomponent_incident_trace_on_boundary,
)


def _operators(curve):
    if isinstance(curve, OrderedBoundary2D):
        return (build_multicomponent_muller_system,
                build_multicomponent_exterior_receiver_operator,
                multicomponent_incident_trace_on_boundary)
    return build_muller_system, build_exterior_receiver_operator, kress_incident_trace_on_boundary


@dataclass(frozen=True)
class Acquisition:
    directions: np.ndarray
    receivers: np.ndarray

    def __post_init__(self):
        for name in ("directions", "receivers"):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if value.ndim != 2 or value.shape[1] != 2 or len(value) == 0 or not np.isfinite(value).all():
                raise ValueError(f"{name} must be a finite, nonempty (N,2) array.")
            if name == "directions" and not np.allclose(np.linalg.norm(value, axis=1), 1, rtol=0, atol=1e-12):
                raise ValueError("Incident directions must be unit vectors.")
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    @classmethod
    def ring(cls, illuminations, receivers, radius=10.0):
        from .geometry import integer
        illuminations = integer(illuminations, "illuminations")
        receivers = integer(receivers, "receivers")
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError("Receiver radius must be positive.")
        def points(n):
            t = 2 * np.pi * np.arange(n) / n
            return np.column_stack((np.cos(t), np.sin(t)))
        return cls(points(illuminations), radius * points(receivers))

    @property
    def data_shape(self):
        return (len(self.directions), len(self.receivers))


@dataclass(frozen=True)
class PointSourceAcquisition:
    """Line-source illumination, optionally retaining only paired receivers.

    Strength multiplies the outgoing Green function i H0^(1)(k r)/4.
    Coordinates and wavenumber must use the same length unit. A paired scan
    exposes only its diagonal to the inverse, never unmeasured cross pairs.
    """
    sources: np.ndarray
    receivers: np.ndarray
    strength: complex = 1.0
    paired: bool = True

    def __post_init__(self):
        for name in ("sources", "receivers"):
            value = np.array(getattr(self, name), dtype=float, copy=True)
            if value.ndim != 2 or value.shape[1] != 2 or not len(value) or not np.isfinite(value).all():
                raise ValueError(f"{name} must be a finite, nonempty (N,2) array.")
            value.setflags(write=False)
            object.__setattr__(self, name, value)
        if not np.isfinite(self.strength):
            raise ValueError("Source strength must be finite.")
        if self.paired and len(self.sources) != len(self.receivers):
            raise ValueError("Paired acquisition requires equally many sources and receivers.")
        if np.any(np.linalg.norm(self.sources[:, None] - self.receivers[None, :], axis=-1) == 0):
            raise ValueError("Sources and receivers must be distinct.")

    @property
    def data_shape(self):
        return ((len(self.sources),) if self.paired
                else (len(self.sources), len(self.receivers)))


def same_acquisition(first, second):
    if type(first) is not type(second):
        return False
    if not np.array_equal(first.receivers, second.receivers):
        return False
    if isinstance(first, PointSourceAcquisition):
        return (np.array_equal(first.sources, second.sources)
                and first.strength == second.strength and first.paired == second.paired)
    return np.array_equal(first.directions, second.directions)


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Work:
    max_forwards: int = 600
    max_seconds: float = 600.0
    attempted: int = 0
    completed: int = 0
    failed: int = 0
    jacobians: int = 0
    factorizations: int = 0
    rhs_columns: int = 0
    seconds: dict = field(default_factory=dict)
    started: float = field(default_factory=perf_counter, repr=False)

    def check(self):
        if self.attempted >= self.max_forwards or perf_counter() - self.started >= self.max_seconds:
            raise BudgetExceeded("Forward/time budget exhausted.")

    def summary(self):
        counters = {name: getattr(self, name) for name in
                    ("attempted", "completed", "failed", "jacobians", "factorizations", "rhs_columns")}
        return dict(counters, seconds=dict(self.seconds))


@contextmanager
def timed(work, name):
    started = perf_counter()
    try:
        yield
    finally:
        if work is not None:
            work.seconds[name] = work.seconds.get(name, 0.0) + perf_counter() - started


def frequency_threads(threads=None):
    """Threads for independent frequency systems: SC_FREQUENCY_THREADS, default 8."""
    count = int(os.environ.get("SC_FREQUENCY_THREADS", "8") if threads is None else threads)
    if count < 1:
        raise ValueError("Frequency threads must be positive.")
    return count


@contextmanager
def ordered_calls(function, items, threads=None):
    """Deferred ``function(item)`` calls, to be consumed strictly in order (SPD-010).

    With one thread each call runs when it is consumed, exactly as a loop.
    Otherwise a thread pool starts every call; consuming one waits for it and
    re-raises its exception. A consumer that stops early cancels calls not yet
    started and discards the rest, so ledger charges and failures keep their
    serial order. Each call runs in a copy of the caller's context, so an
    active fit-local geometry-validation cache is shared (it is thread-safe).
    With one BLAS thread each solve is deterministic, so values do not depend
    on the thread count.
    """
    items = list(items)
    count = min(frequency_threads(threads), len(items))
    if count <= 1:
        yield [partial(function, item) for item in items]
        return
    pool = ThreadPoolExecutor(count)
    futures = [pool.submit(copy_context().run, function, item) for item in items]
    try:
        yield [future.result for future in futures]
    finally:
        for future in futures:
            future.cancel()
        pool.shutdown(wait=True)


@dataclass
class ForwardState:
    curve: object
    wavenumber: float
    interior_wavenumber: float
    acquisition: Acquisition
    matrix: np.ndarray
    factors: tuple
    traces: np.ndarray
    prediction: np.ndarray  # (illumination, receiver)
    system_residual: float


def forward_backend():
    """Dense-system backend: SC_FORWARD_BACKEND=cpu (reference, default) or cuda (SPD-011, opt-in)."""
    value = os.environ.get("SC_FORWARD_BACKEND", "cpu")
    if value not in ("cpu", "cuda"):
        raise ValueError("SC_FORWARD_BACKEND must be 'cpu' or 'cuda'.")
    return value


def _solve(matrix, factors, rhs):
    if isinstance(factors, cuda_assembly.DeviceFactors):
        solution, residual = factors.solve(rhs)
    else:
        solution = lu_solve(factors, rhs)
        residual = np.linalg.norm(matrix @ solution - rhs) / max(np.linalg.norm(rhs), np.finfo(float).tiny)
    if not np.isfinite(solution).all() or residual > 1e-10:
        raise FloatingPointError("Unqualified dense Müller solve.")
    return solution, float(residual)


def solve(shape, wavenumber, contrast, acquisition, nodes, *, work=None):
    """contrast=ki²/k²; geometry and all lengths are in one declared unit."""
    if not np.isfinite(wavenumber) or wavenumber <= 0 or not np.isfinite(contrast) or contrast <= 0:
        raise ValueError("Wavenumber and contrast must be positive.")
    if work is not None:
        work.check()
        work.attempted += 1
    try:
        curve = shape.nodes(nodes)
        assemble, receivers, incident = _operators(curve)
        ki = wavenumber * np.sqrt(contrast)
        # The CUDA backend covers single periodic curves with real wavenumbers; others stay on CPU.
        device = forward_backend() == "cuda" and cuda_assembly.supported(curve, wavenumber, ki)
        # Outside a fit cache, a CUDA solve validates its boundary once for all three builders (exact reuse).
        local = device and current_validation_cache() is None
        # Explicit scope prevents ambient acceleration/device contexts changing the model.
        with (validation_cache("cache") if local else nullcontext()), execution(kernels="reference", device="cpu"):
            with timed(work, "assembly"):
                matrix = (cuda_assembly.build_muller_matrix(curve, wavenumber, ki) if device
                          else assemble(curve, wavenumber, ki).system_matrix)
            with timed(work, "receiver_operator"):
                receiver = receivers(curve, acquisition.receivers, wavenumber)
            if isinstance(acquisition, PointSourceAcquisition):
                field, normal = incident(
                    curve, acquisition.sources, wavenumber, acquisition.strength)
                field, normal = field.T, normal.T
            else:
                field = np.exp(1j * wavenumber * (curve.points @ acquisition.directions.T))
                normal = 1j * wavenumber * (curve.normals @ acquisition.directions.T) * field
            rhs = np.vstack((field, normal))
            with timed(work, "factorization"):
                factors = cuda_assembly.DeviceFactors(matrix) if device else lu_factor(matrix)
            if work is not None:
                work.factorizations += 1
                work.rhs_columns += rhs.shape[1]
            with timed(work, "forward_solve"):
                traces, residual = _solve(matrix, factors, rhs)
                prediction = receiver.apply_state(traces)
                if isinstance(acquisition, PointSourceAcquisition) and acquisition.paired:
                    prediction = np.diag(prediction).copy()
        if not np.isfinite(prediction).all():
            raise FloatingPointError("Nonfinite scattered field.")
    except Exception:
        if work is not None:
            work.failed += 1
        raise
    if work is not None:
        work.completed += 1
    return ForwardState(curve, wavenumber, ki, acquisition, matrix,
                        factors, traces, prediction, residual)


def shape_jacobian(state, normal_displacements, *, work=None):
    """Continuous Hadamard derivative with Kress traces and periodic quadrature.

    This is bilinear reciprocity, without conjugation. It is qualified against
    independently rebuilt finite differences, not claimed exact at finite N.
    """
    h = np.asarray(normal_displacements, float)
    if h.ndim != 2 or h.shape[0] != state.curve.num_nodes or not np.isfinite(h).all():
        raise ValueError("Normal displacement basis must have shape (nodes, parameters).")
    if work is not None:
        if perf_counter() - work.started >= work.max_seconds:
            raise BudgetExceeded("Time budget exhausted before Jacobian.")
        work.jacobians += 1
        work.rhs_columns += len(state.acquisition.receivers)
    with timed(work, "reciprocal_solve"):
        with execution(kernels="reference", device="cpu"):
            incident = _operators(state.curve)[2]
            d, n = incident(state.curve, state.acquisition.receivers, state.wavenumber)
        reciprocal, _ = _solve(state.matrix, state.factors, np.concatenate((d, n), axis=1).T)
    count = state.curve.num_nodes
    with timed(work, "jacobian_contraction"):
        # Dense matrix products are much faster than the four-index einsum at
        # large illumination/update counts. Cap the temporary at about 32 MiB.
        sources = state.traces[:count]
        receivers = reciprocal[:count].T
        value = np.empty((sources.shape[1], receivers.shape[0], h.shape[1]), complex)
        block = max(1, (32 * 1024 ** 2) // (16 * count * sources.shape[1]))
        for start in range(0, h.shape[1], block):
            stop = min(start + block, h.shape[1])
            weighted = (h[:, start:stop, None] * state.curve.arc_length_weights[:, None, None]
                        * sources[:, None, :])
            product = receivers @ weighted.reshape(count, -1)
            value[:, :, start:stop] = product.reshape(receivers.shape[0], stop-start, sources.shape[1]).transpose(2, 0, 1)
        value *= state.interior_wavenumber ** 2 - state.wavenumber ** 2
        if isinstance(state.acquisition, PointSourceAcquisition) and state.acquisition.paired:
            indices = np.arange(len(state.acquisition.sources))
            value = value[indices, indices, :]
    if not np.isfinite(value).all():
        raise FloatingPointError("Nonfinite shape Jacobian.")
    return value
