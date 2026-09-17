"""Read-only wrappers over the qualified Laurent and Kress solvers.

This is the ONLY module in the package that imports modal_muller_research, and
it imports library modules only -- never run_*, plot_* or probe. Those files are
hash-pinned by 11 recorded result bundles and are never modified here.

The split used throughout comes from linearity of kernel_matrix:

    block[m,n] = 2*pi*( S[m,-n] + sum_l L_l * P[m-l, l-n] ),  L_l = -1/|l|

so kernel_matrix(P, 0) is the exact log-symbol contribution and
kernel_matrix(0, S) is the smooth polynomial lookup. The Maue term -m*n*V
inherits V's own split; it is a reweighting of V, not an independent kernel.

Perturbed geometries keep the base center and scale (dataclasses.replace), so
the FixedAcquisition cache stays valid and 'dz' means a fixed physical
displacement scale*dz regardless of step.
"""
from dataclasses import replace
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from experiments.modal_muller_research.coefficient_operator import (
    CoefficientGeometry, LaurentGeometry, dense_product, kernel_matrix, sparse_product, times)
from experiments.modal_muller_research.coefficient_derivative import (
    FixedAcquisition, NativeShapeForward, ShapeOperator, prepare_direction)
from experiments.modal_muller_research.scattering_library import parameterization
from experiments.bie002_modal_diagnostic.fixtures import inputs

BLOCK_NAMES = ('K', 'V', 'T', 'Kp')


def relative(a, b):
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(b), 1e-300))


def waves(frequency, acq):
    for region in ('exterior', 'interior'):
        material = acq[region]
        if material.get('mur', 1) != 1 or material.get('sigma', 0) != 0:
            raise ValueError('This screen requires lossless materials with mur=1.')
    factor = 2 * np.pi * frequency * np.sqrt(acq['eps0'] * acq['mu0'])
    return factor * np.sqrt(acq['exterior']['epsr']), factor * np.sqrt(acq['interior']['epsr'])


def nodal_reference(parameterizations, frequency, acq, nodes, ledger=None):
    """Independent single-component Kress oracle. Imports solvers/ read-only."""
    from ordered_boundary import OrderedBoundary2D  # noqa: F401  (kept for parity)
    from gpr_bem_kress import Material
    from gpr_bem_kress.execution import execution
    from gpr_bem_kress.system import build_kress_tmz_frequency_system
    from gpr_bem_kress.forward import (kress_incident_trace_on_boundary,
                                       build_exterior_receiver_operator)
    if ledger is not None:
        ledger.charge(assemblies=1, factorizations=1, rhs_batches=1,
                      rhs_columns=len(acq['source_points']))
    started = perf_counter()
    curves = [p.discretize(nodes, require_even=True) for p in parameterizations]
    if len(curves) != 1:
        raise ValueError('LAU-001 is a single-component screen.')
    geometry = curves[0]
    with execution(kernels='real_bessel'):
        system = build_kress_tmz_frequency_system(
            geometry, 2 * np.pi * frequency,
            **{n: Material(**acq[n]) for n in ('exterior', 'interior')},
            **{n: acq[n] for n in ('eps0', 'mu0')})
        d, n = kress_incident_trace_on_boundary(
            geometry, np.array(acq['source_points']), system.k_exterior, acq['source_strength'])
        b = np.concatenate((d, n), axis=1).T
        c = build_exterior_receiver_operator(
            geometry, np.array(acq['receiver_points']), system.k_exterior).state_rows
    a = system.system_matrix
    factors = lu_factor(a)
    state = lu_solve(factors, b)
    return dict(y=c @ state, state=state, a=a, b=b, c=c, curves=curves,
                system=system, factors=factors, acquisition=acq, ledger=ledger,
                seconds=perf_counter() - started)


def direction_values(geometry, dz, theta):
    """Physical Cartesian displacement in the same fixed Laurent chart."""
    return geometry.scale * sum((v * np.exp(1j * j * theta) for j, v in dz.items()),
                                np.zeros_like(theta, dtype=complex))


def nodal_derivatives(reference, geometry, directions):
    """Independent continuous Hadamard oracle, qualified in N and by nodal FD.

    No Laurent operator derivative enters this reference. Both primal and unit
    receiver traces come from the nodal Kress matrix; no complex conjugation.
    Returns full receiver-by-source matrices, allowing separate illuminations.
    """
    from gpr_bem_kress.execution import execution
    from gpr_bem_kress.forward import kress_incident_trace_on_boundary
    curve, = reference['curves']
    system, acq = reference['system'], reference['acquisition']
    if 'reciprocal_state' not in reference:
        if reference['ledger'] is not None:
            reference['ledger'].charge(rhs_batches=1, rhs_columns=len(acq['receiver_points']))
        with execution(kernels='real_bessel'):
            d, n = kress_incident_trace_on_boundary(
                curve, np.asarray(acq['receiver_points']), system.k_exterior, 1.)
        rhs = np.concatenate((d, n), axis=1).T
        reference['reciprocal_state'] = lu_solve(reference['factors'], rhs)
    count = curve.num_nodes
    us, ur = reference['state'][:count], reference['reciprocal_state'][:count]
    theta = (curve.parameters - curve.parameter_origin) * 2 * np.pi / curve.period
    result = []
    for dz in directions:
        velocity = direction_values(geometry, dz, theta)
        normal = velocity.real * curve.normals[:, 0] + velocity.imag * curve.normals[:, 1]
        weights = normal * curve.arc_length_weights
        result.append((system.k_interior**2 - system.k_exterior**2)
                      * (ur.T @ (weights[:, None] * us)))
    return result


def lift(state, curves, cutoff):
    """Modal coefficients -> nodal (u, d_n u). Independent of run_native.lift."""
    size = 2 * cutoff + 1
    values, fluxes = [], []
    for i, curve in enumerate(curves):
        theta = (curve.parameters - curve.parameter_origin) * 2 * np.pi / curve.period
        basis = np.exp(1j * theta[:, None] * np.arange(-cutoff, cutoff + 1))
        block = state[2 * i * size:2 * (i + 1) * size]
        values.append(basis @ block[:size])
        fluxes.append((basis @ block[size:]) / (curve.speeds * curve.period / (2 * np.pi))[:, None])
    return np.concatenate(values + fluxes)


def _blocks_from_arguments(prepared, modes, cutoff, p_args, s_args):
    """Assemble the four nonidentity blocks from explicit (P, S) arguments."""
    v = kernel_matrix(p_args[0], s_args[0], cutoff)
    k = kernel_matrix(p_args[1], s_args[1], cutoff)
    kp = k[::-1, ::-1].T
    t = -modes[:, None] * modes[None, :] * v + kernel_matrix(p_args[2], s_args[2], cutoff)
    return dict(K=k, V=v, T=t, Kp=kp)


def assemble_blocks(block_map):
    """[[-K, V], [-T, Kp]] -- the nonidentity part of the Muller system."""
    return np.block([[-block_map['K'], block_map['V']],
                     [-block_map['T'], block_map['Kp']]])


def forward_arguments(operator):
    prepared = operator.prepared
    negative_source = times(prepared.source_dot, -2)
    p_args = [operator.p[0],
              sparse_product(operator.p[1], negative_source),
              sparse_product(operator.p[2], prepared.normal_dot)]
    s_args = [operator.smooth[0],
              sparse_product(operator.smooth[1], negative_source),
              sparse_product(operator.smooth[2], prepared.normal_dot)]
    return p_args, s_args


def _derivative_arguments(operator, direction):
    prepared = operator.prepared
    dp = np.array([sparse_product(v, direction.radius_squared) for v in operator.dp])
    dq = np.array([sparse_product(v, direction.radius_squared) for v in operator.dq])
    dsmooth = np.array([qq + dense_product(pp, prepared.log_quotient)
                        + dense_product(orig, direction.log_quotient)
                        for pp, qq, orig in zip(dp, dq, operator.p)])
    p_args = [dp[0],
              -2 * (sparse_product(dp[1], prepared.source_dot)
                    + sparse_product(operator.p[1], direction.source_dot)),
              sparse_product(dp[2], prepared.normal_dot)
              + sparse_product(operator.p[2], direction.normal_dot)]
    s_args = [dsmooth[0],
              -2 * (sparse_product(dsmooth[1], prepared.source_dot)
                    + sparse_product(operator.smooth[1], direction.source_dot)),
              sparse_product(dsmooth[2], prepared.normal_dot)
              + sparse_product(operator.smooth[2], direction.normal_dot)]
    return p_args, s_args


def _split(operator, p_args, s_args):
    """(log blocks, smooth blocks) by linearity of kernel_matrix."""
    prepared, modes, cutoff = operator.prepared, operator.modes, operator.cutoff
    zeros = [np.zeros_like(a) for a in p_args]
    log = _blocks_from_arguments(prepared, modes, cutoff, p_args, zeros)
    smooth = _blocks_from_arguments(prepared, modes, cutoff, zeros, s_args)
    return log, smooth


def split_operator(operator):
    log, smooth = _split(operator, *forward_arguments(operator))
    size = len(operator.modes)
    zero = np.zeros((size, size))
    identity = np.block([[np.eye(size), zero], [zero, np.eye(size)]])
    return identity, assemble_blocks(log), assemble_blocks(smooth), log, smooth


def split_derivative(operator, direction):
    if not direction.radius_squared and not direction.source_dot and not direction.normal_dot:
        size = len(operator.modes)
        empty = {n: np.zeros((size, size), complex) for n in BLOCK_NAMES}
        zero = np.zeros_like(operator.a)
        return zero, zero, empty, dict(empty)
    log, smooth = _split(operator, *_derivative_arguments(operator, direction))
    return assemble_blocks(log), assemble_blocks(smooth), log, smooth


class NativeCase:
    """One geometry at one frequency: operator, acquisition, split and derivatives."""

    def __init__(self, geometry, acq, frequency, cutoff, bandwidth, terms, angular_order=36,
                 ledger=None):
        if ledger is not None:
            ledger.charge(assemblies=1, factorizations=1, rhs_batches=1,
                          rhs_columns=len(acq['source_points']))
        started = perf_counter()
        self.geometry, self.acq, self.frequency = geometry, acq, frequency
        self.cutoff, self.bandwidth, self.terms = cutoff, bandwidth, terms
        self.ko, self.ki = waves(frequency, acq)
        self.acquisition = FixedAcquisition(geometry.center, geometry.scale, self.ko,
                                            acq['source_points'], acq['receiver_points'],
                                            acq['source_strength'], angular_order)
        self.forward = NativeShapeForward(geometry, [self.acquisition], [self.ki],
                                          cutoff=cutoff, bandwidth=bandwidth, terms=terms)
        self.operator, self.fields, self.factors, self.u = self.forward.states[0]
        self.a, self.b, self.c = self.operator.a, self.fields.b, self.fields.c
        self.y = self.forward.outputs[0]
        (self.identity, self.log, self.smooth,
         self.log_blocks, self.smooth_blocks) = split_operator(self.operator)
        self.assembly_seconds = perf_counter() - started
        self.reconstruction_error = relative(self.identity + self.log + self.smooth, self.a)

    def parts(self, label):
        if label == 'IDENTITY_ONLY':
            return self.identity, self.log + self.smooth
        if label == 'VERIFIED_SINGULAR_SPLIT':
            return self.identity + self.log, self.smooth
        raise ValueError(label)

    def remainder_blocks(self, label):
        if label == 'IDENTITY_ONLY':
            return {n: self.log_blocks[n] + self.smooth_blocks[n] for n in BLOCK_NAMES}
        if label == 'VERIFIED_SINGULAR_SPLIT':
            return dict(self.smooth_blocks)
        raise ValueError(label)

    def derivative(self, dz):
        direction = prepare_direction(self.operator.prepared, dz)
        log, smooth, log_blocks, smooth_blocks = split_derivative(self.operator, direction)
        db, dc = self.fields.derivative(dz)
        return dict(log=log, smooth=smooth, log_blocks=log_blocks, smooth_blocks=smooth_blocks,
                    total=log + smooth, db=db, dc=dc)

    def derivative_parts(self, derivative, label):
        if label == 'IDENTITY_ONLY':
            return np.zeros_like(derivative['total']), derivative['total']
        if label == 'VERIFIED_SINGULAR_SPLIT':
            return derivative['log'], derivative['smooth']
        raise ValueError(label)

    def derivative_remainder_blocks(self, derivative, label):
        if label == 'IDENTITY_ONLY':
            return {n: derivative['log_blocks'][n] + derivative['smooth_blocks'][n]
                    for n in BLOCK_NAMES}
        if label == 'VERIFIED_SINGULAR_SPLIT':
            return dict(derivative['smooth_blocks'])
        raise ValueError(label)


def solve_masked(protected, remainder, mask, b, c, ledger=None):
    if ledger is not None:
        ledger.charge(factorizations=1, rhs_batches=1, rhs_columns=b.shape[1])
    matrix = protected + mask * remainder
    factors = lu_factor(matrix)
    state = lu_solve(factors, b)
    return dict(a=matrix, factors=factors, state=state, y=c @ state, ledger=ledger)


def masked_data_derivative(solved, case, derivative, mask, label):
    """D_v Y for the SAME frozen-mask model: D_v A~ = D_v S + Pi_S D_v R."""
    d_protected, d_remainder = case.derivative_parts(derivative, label)
    da = d_protected + mask * d_remainder
    if 'transfer' not in solved:
        if solved.get('ledger') is not None:
            solved['ledger'].charge(rhs_batches=1, rhs_columns=case.c.shape[0])
        solved['transfer'] = lu_solve(solved['factors'], case.c.T, trans=1).T
    transfer = solved['transfer']
    return derivative['dc'] @ solved['state'] + transfer @ (derivative['db'] - da @ solved['state'])


def masked_hadamard_derivatives(solved, case, directions):
    """Continuous identity on compressed traces; distinct from its discrete tangent.

    Periodic quadrature integrates the finite trigonometric product exactly.
    These diagnostic samples are not part of the node-free forward assembler.
    """
    fields, cutoff = case.fields, case.cutoff
    if 'reciprocal_state' not in solved:
        if solved.get('ledger') is not None:
            solved['ledger'].charge(rhs_batches=1, rhs_columns=case.c.shape[0])
        idx = fields.bandwidth + case.operator.modes
        f, q = fields.waves.values[:, 2:-2], fields.waves.flux[:, 2:-2]
        rhs = np.concatenate((f[idx] @ fields.acquisition.receiver_weights,
                              q[idx] @ fields.acquisition.receiver_weights))
        solved['reciprocal_state'] = lu_solve(solved['factors'], rhs)
    degree = max([abs(j) for j in case.geometry.coefficients]
                 + [abs(j) for dz in directions for j in dz])
    count = 4 * cutoff + 2 * degree + 1
    theta = 2 * np.pi * np.arange(count) / count
    basis = np.exp(1j * theta[:, None] * case.operator.modes)
    us = basis @ solved['state'][:2 * cutoff + 1]
    ur = basis @ solved['reciprocal_state'][:2 * cutoff + 1]
    normal_speed = case.geometry.scale * sum(
        j * v * np.exp(1j * j * theta) for j, v in case.geometry.coefficients.items())
    return [(case.ki**2 - case.ko**2) * 2 * np.pi / count
            * (ur.T @ (np.real(direction_values(case.geometry, dz, theta)
                              * normal_speed.conj())[:, None] * us))
            for dz in directions]


def moved_geometry(geometry, dz, step):
    """Base geometry displaced by step*scale*dz, with center and scale FIXED."""
    moved = dict(geometry.coefficients)
    for j, value in dz.items():
        moved[j] = moved.get(j, 0) + step * value
    return replace(geometry, coefficients={j: v for j, v in moved.items() if abs(v) > 1e-30})


def operator_at(geometry, ko, ki, cutoff, bandwidth, terms):
    prepared = CoefficientGeometry(geometry, bandwidth)
    return ShapeOperator(prepared, ko, ki, cutoff, terms)
