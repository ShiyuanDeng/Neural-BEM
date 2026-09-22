"""Equal-density transmission, dimensionless k, plane waves, full aperture."""
from dataclasses import dataclass, field
from contextlib import contextmanager
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from gpr_bem_kress import (build_muller_system, build_exterior_receiver_operator,
                           kress_incident_trace_on_boundary)
from gpr_bem_kress.execution import execution


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


def _solve(matrix, factors, rhs):
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
        # Explicit scope prevents ambient acceleration/device contexts changing the model.
        with execution(kernels="reference", device="cpu"):
            ki = wavenumber * np.sqrt(contrast)
            with timed(work, "assembly"):
                system = build_muller_system(curve, wavenumber, ki)
            with timed(work, "receiver_operator"):
                receiver = build_exterior_receiver_operator(curve, acquisition.receivers, wavenumber)
            field = np.exp(1j * wavenumber * (curve.points @ acquisition.directions.T))
            normal = 1j * wavenumber * (curve.normals @ acquisition.directions.T) * field
            rhs = np.vstack((field, normal))
            with timed(work, "factorization"):
                factors = lu_factor(system.system_matrix)
            if work is not None:
                work.factorizations += 1
                work.rhs_columns += rhs.shape[1]
            with timed(work, "forward_solve"):
                traces, residual = _solve(system.system_matrix, factors, rhs)
                prediction = receiver.apply_state(traces)
        if not np.isfinite(prediction).all():
            raise FloatingPointError("Nonfinite scattered field.")
    except Exception:
        if work is not None:
            work.failed += 1
        raise
    if work is not None:
        work.completed += 1
    return ForwardState(curve, wavenumber, ki, acquisition, system.system_matrix,
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
            d, n = kress_incident_trace_on_boundary(state.curve, state.acquisition.receivers, state.wavenumber)
        reciprocal, _ = _solve(state.matrix, state.factors, np.concatenate((d, n), axis=1).T)
    count = state.curve.num_nodes
    with timed(work, "jacobian_contraction"):
        value = (state.interior_wavenumber ** 2 - state.wavenumber ** 2) * np.einsum(
            "nr,np,nd,n->drp", reciprocal[:count], h, state.traces[:count],
            state.curve.arc_length_weights, optimize=True)
    if not np.isfinite(value).all():
        raise FloatingPointError("Nonfinite shape Jacobian.")
    return value
