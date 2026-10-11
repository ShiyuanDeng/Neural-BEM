"""Paired shape sensitivities from coupled primal and reciprocal Kress traces.

For the high-level lossless, nonmagnetic transmission problem, the shape
identity is (ki**2-ko**2) integral(u_source*u_receiver*normal_motion ds).
It is bilinear, with no complex conjugation. Quadrature approximates the
continuous derivative; coarse grids need independent qualification.
"""
from time import perf_counter
import numpy as np
from .execution import record
from .multicomponent import multicomponent_incident_trace_on_boundary


def reciprocal_paired_response(base, normal_weights):
    """Return (directions, pairs), reusing the base LU for unit receiver RHSs.

    ``normal_weights`` has shape (directions, boundary nodes) and already
    includes arc-length weights. Source strengths are present in ``base.U``;
    applying them to the reciprocal illumination would count them twice.
    """
    boundary = base.system.geometry
    weights = np.asarray(normal_weights, dtype=float)
    if (weights.ndim != 2 or weights.shape[1] != boundary.num_nodes
            or not np.all(np.isfinite(weights))):
        raise ValueError("Normal weights must have shape (directions, boundary nodes).")
    if len(base.sources) != len(base.receivers):
        raise ValueError("Paired sensitivities require equal source and receiver counts.")
    started = perf_counter()
    d, n = multicomponent_incident_trace_on_boundary(
        boundary, base.receivers, base.system.k_exterior, 1.)
    rhs = np.concatenate((d, n), axis=1).T
    receiver_traces = base.factors.solve(rhs)
    if (not np.all(np.isfinite(receiver_traces))
            or np.linalg.norm(base.A @ receiver_traces-rhs)/np.linalg.norm(rhs) > 1e-10):
        raise FloatingPointError("Unqualified reciprocal solve.")
    record("reciprocal_traces", perf_counter()-started)
    started = perf_counter()
    count = boundary.num_nodes
    products = receiver_traces[:count] * base.U[:count]
    value = (base.system.k_interior**2-base.system.k_exterior**2) * (weights @ products)
    if not np.all(np.isfinite(value)):
        raise FloatingPointError("Nonfinite reciprocal derivative.")
    record("reciprocal_contraction", perf_counter()-started)
    return value
