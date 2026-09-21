"""Local response operators S_j = R_j A_j^-1 B_j, and the monolithic control.

The report's strongest alternative direction: each object's Muller solve is
eliminated once into a reusable local response mapping incident cylindrical
coefficients to outgoing ones, interactions are carried by translation
operators, and only the objects that moved are rebuilt:

    b_j = S_j a_j ,   a_j = a_j^inc + sum_{l != j} U_{jl} b_l ,
    (I - S U) b = S a^inc .

Everything is built on the FFT Fourier-Galerkin Muller assembler, so the same
code runs at any electrical size.  The monolithic two-object Muller system is
assembled here too, as the control the report asks for.
"""
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1, h1vp, jv, jvp

from experiments.modal_muller_research.coefficient_operator import kernel_matrix
from .assembler import FourierGalerkinMuller, curve_values, spectrum


def polar_gradient(radial, angular, normal, offset):
    """J * n.grad(f) from the polar components of grad(f).

    The pairing with the real normal is bilinear, not Hermitian: f is complex.
    """
    unit = offset / np.abs(offset)
    return radial * (normal * unit.conj()).real + angular * (
        normal * (1j * unit).conj()).real


def regular_traces(coefficients, wave, order, cutoff, grid, sign=1):
    """Modal (psi, J d_n psi) for psi_p = J_p(k rho) e^{i sign p theta}."""
    t = 2 * np.pi * np.arange(grid) / grid
    z, normal = curve_values(coefficients, t)
    centre = coefficients.get(0, 0j)
    offset = z - centre
    rho, theta = np.abs(offset), np.angle(offset)
    orders = np.arange(-order, order + 1)
    phase = np.exp(1j * sign * orders[None, :] * theta[:, None])
    value = jv(orders[None, :], wave * rho[:, None]) * phase
    flux = polar_gradient(
        wave * jvp(orders[None, :], wave * rho[:, None]) * phase,
        1j * sign * orders[None, :] / rho[:, None]
        * jv(orders[None, :], wave * rho[:, None]) * phase,
        normal[:, None], offset[:, None])
    index = np.arange(-cutoff, cutoff + 1) % grid
    return (np.fft.fft(value, axis=0)[index] / grid,
            np.fft.fft(flux, axis=0)[index] / grid)


def incident_operator(coefficients, wave, order, cutoff, grid):
    """B: incident regular coefficients -> Muller right-hand side."""
    value, flux = regular_traces(coefficients, wave, order, cutoff, grid, sign=1)
    return np.concatenate((value, flux), axis=0)


def outgoing_operator(coefficients, wave, order, cutoff, grid):
    """R: solved modal traces -> outgoing coefficients of H_p(k rho) e^{i p th}."""
    value, flux = regular_traces(coefficients, wave, order, cutoff, grid, sign=-1)
    # b_p = (i/4) int [ (J d_n chi_p) u - chi_p (J d_n u) ] dt, and
    # int f(t) g(t) dt = 2 pi sum_m fhat_{-m} ghat_m.
    # row m holds coefficient m-cutoff, so f_{-m} is the row-reversed array.
    return .25j * 2 * np.pi * np.concatenate(
        (flux[::-1].T, -value[::-1].T), axis=1)


def mie_response(radius, k_exterior, k_interior, order):
    """Analytic transmission coefficients of a circle; S is diagonal."""
    p = np.arange(-order, order + 1)
    jo, ji = jv(p, k_exterior * radius), jv(p, k_interior * radius)
    djo = k_exterior * jvp(p, k_exterior * radius)
    dji = k_interior * jvp(p, k_interior * radius)
    ho, dho = hankel1(p, k_exterior * radius), k_exterior * h1vp(p, k_exterior * radius)
    return np.diag((dji * jo - ji * djo) / (ji * dho - dji * ho))


class LocalResponse:
    """S_j = R_j A_j^-1 B_j for one object, in its own local coordinates."""

    def __init__(self, coefficients, k_exterior, k_interior, cutoff, order,
                 grid=512):
        started = perf_counter()
        self.centre = coefficients.get(0, 0j)
        local = dict(coefficients)
        local[0] = 0j
        operator = FourierGalerkinMuller(local, grid=grid)
        matrix, _ = operator.assemble(k_exterior, k_interior, cutoff)
        assembled = perf_counter()
        factors = lu_factor(matrix)
        factored = perf_counter()
        self.b = incident_operator(local, k_exterior, order, cutoff, grid)
        self.r = outgoing_operator(local, k_exterior, order, cutoff, grid)
        self.matrix, self.factors = matrix, factors
        self.s = self.r @ lu_solve(factors, self.b)
        self.order, self.cutoff = order, cutoff
        self.seconds = dict(assemble=assembled - started,
                            factor=factored - assembled,
                            respond=perf_counter() - factored,
                            total=perf_counter() - started)


def translation(target_centre, source_centre, wave, order):
    """U: outgoing coefficients about the source -> regular ones about target.

    Graf: H_q(k rho_s) e^{i q th_s} = sum_p J_p(k rho_t) e^{i p th_t}
          H_{q-p}(k d) e^{i (q-p) phi},  d = |c_t - c_s|, phi = arg(c_t - c_s).
    """
    delta = target_centre - source_centre
    p = np.arange(-order, order + 1)[:, None]
    q = np.arange(-order, order + 1)[None, :]
    return hankel1(q - p, wave * abs(delta)) * np.exp(1j * (q - p) * np.angle(delta))


def incident_coefficients(centre, sources, wave, order, strengths=1.):
    """Regular expansion about `centre` of point sources outside it."""
    points = np.asarray(sources, dtype=float)
    delta = (points[:, 0] + 1j * points[:, 1]) - centre
    p = np.arange(-order, order + 1)[:, None]
    return .25j * hankel1(p, wave * np.abs(delta)[None, :]) * np.exp(
        -1j * p * np.angle(delta)[None, :]) * np.asarray(strengths)


def evaluate_outgoing(centre, points, wave, coefficients):
    """Field at points from outgoing coefficients about `centre`."""
    points = np.asarray(points, dtype=float)
    delta = (points[:, 0] + 1j * points[:, 1]) - centre
    order = (coefficients.shape[0] - 1) // 2
    p = np.arange(-order, order + 1)[None, :]
    basis = hankel1(p, wave * np.abs(delta)[:, None]) * np.exp(
        1j * p * np.angle(delta)[:, None])
    return basis @ coefficients


def local_solve(responses, wave, sources, receivers, strengths=1.):
    """(I - S U) b = S a^inc, then the scattered field at the receivers."""
    started = perf_counter()
    order = responses[0].order
    size = 2 * order + 1
    count = len(responses)
    system = np.eye(count * size, dtype=complex)
    rhs = np.zeros((count * size, np.shape(sources)[0]), dtype=complex)
    for i, target in enumerate(responses):
        rows = slice(i * size, (i + 1) * size)
        rhs[rows] = target.s @ incident_coefficients(
            target.centre, sources, wave, order, strengths)
        for j, source in enumerate(responses):
            if i == j:
                continue
            system[rows, j * size:(j + 1) * size] -= target.s @ translation(
                target.centre, source.centre, wave, order)
    outgoing = lu_solve(lu_factor(system), rhs)
    field = sum(evaluate_outgoing(r.centre, receivers, wave,
                                  outgoing[i * size:(i + 1) * size])
                for i, r in enumerate(responses))
    return field, perf_counter() - started


def cross_block(target, source, k_exterior, cutoff, grid):
    """Off-diagonal Muller block: exterior Green kernels between two boundaries.

    Disjoint boundaries make every kernel smooth, so no singular extraction is
    needed and the log amplitude is zero.  The hypersingular block keeps the
    same Maue form as the diagonal so the two are consistent.
    """
    t = 2 * np.pi * np.arange(grid) / grid
    s = 2 * np.pi * (np.arange(grid) + .5) / grid
    zt, nt = curve_values(target, t)
    zs, ns = curve_values(source, s)
    delta = zt[:, None] - zs[None, :]
    radius = np.abs(delta)
    green = .25j * hankel1(0, k_exterior * radius)
    derivative = -.125j * k_exterior * hankel1(1, k_exterior * radius) / radius
    source_dot = (delta * ns[None, :].conj()).real
    target_dot = (delta * nt[:, None].conj()).real
    normal_dot = (nt[:, None] * ns[None, :].conj()).real
    bandwidth = grid // 2 - 1
    zero = np.zeros((2 * bandwidth + 1, 2 * bandwidth + 1), complex)
    project = lambda a: kernel_matrix(zero, spectrum(a, bandwidth, .5), cutoff)
    v = project(green)
    k = project(derivative * (-2 * source_dot))
    kp = project(derivative * (2 * target_dot))
    modes = np.arange(-cutoff, cutoff + 1)
    hyper = -modes[:, None] * modes[None, :] * v + project(
        k_exterior**2 * green * normal_dot)
    return np.block([[-k, v], [-hyper, kp]])


def monolithic(objects, k_exterior, k_interior, cutoff, grid=512):
    """Full multi-object Muller matrix, diagonal blocks plus cross blocks."""
    started = perf_counter()
    blocks = []
    for i, target in enumerate(objects):
        row = []
        for j, source in enumerate(objects):
            if i == j:
                own, _ = FourierGalerkinMuller(target, grid=grid).assemble(
                    k_exterior, k_interior, cutoff)
                row.append(own)
            else:
                row.append(cross_block(target, source, k_exterior, cutoff, grid))
        blocks.append(row)
    return np.block(blocks), perf_counter() - started
