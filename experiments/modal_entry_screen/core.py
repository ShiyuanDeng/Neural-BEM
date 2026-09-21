"""Entry diagnostics with a read-only hybrid Galerkin and independent Kress.

The new directional assembly differentiates closed-form Hankel/log amplitudes.
Its signs, geometry weights and acquisition derivatives are checked by full
reassembly finite differences; physical derivatives use independent Kress traces.
"""
from dataclasses import dataclass
import time

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1, jv

from experiments.laurent_fgm.assembler import (
    FourierGalerkinMuller, curve_values, spectrum, point_source_traces,
    receiver_operator,
)
from experiments.laurent_fgm.curves import evaluate, tangent, diameter, crescent
from experiments.modal_muller_research.coefficient_operator import (
    LaurentGeometry, kernel_matrix,
)
from experiments.modal_muller_research.scattering_library import parameterization

BLOCK_NAMES = ('DD', 'DN', 'ND', 'NN')


def relative(value, reference, floor=1e-300):
    return float(np.linalg.norm(value-reference)/max(np.linalg.norm(reference), floor))


def serialize(c):
    return {str(j): [float(complex(v).real), float(complex(v).imag)]
            for j, v in c.items()}


def deserialize(c):
    return {int(j): complex(*v) for j, v in c.items()}


def fixtures():
    raw = dict(circle={1: .5}, ellipse={1: .65, -1: .35},
               asymmetric_star={1: 1., 6: .12, -4: .12,
                                2: .025+.015j, -2: -.018+.012j},
               crescent=crescent())
    result = {}
    for name, c in raw.items():
        # Translation is fixed at the Fourier center, not an approximate area
        # centroid. Sources surround every unit-diameter fixture.
        d = diameter(c)
        result[name] = {j: complex(v/d) for j, v in c.items() if j != 0}
    return result


def acquisition(count=12, angle_shift=0.):
    theta = 2*np.pi*np.arange(count)/count + angle_shift
    return tuple(np.column_stack((1.5*np.cos(theta+s), 1.5*np.sin(theta+s)))
                 for s in (0., np.pi/count))


def normal_direction(c, p, kind='cos'):
    """Finite Laurent pure-normal displacement N(t)*cos(pt), unit RMS speed."""
    harmonics = {p: .5, -p: .5} if kind == 'cos' else {p: -.5j, -p: .5j}
    dz = {}
    for j, v in c.items():
        for q, w in harmonics.items():
            dz[j+q] = dz.get(j+q, 0j) + j*v*w
    norm = np.sqrt(sum(abs(v)**2 for v in dz.values()))
    return {j: v/norm for j, v in dz.items() if abs(v) > 1e-16}


def directions(c):
    result = {f'p{p}_{kind}': normal_direction(c, p, kind)
              for p in (1, 3, 6) for kind in ('cos', 'sin')}
    norm = np.sqrt(sum(abs(j*v)**2 for j, v in c.items()))
    result['tangent'] = {j: 1j*j*v/norm for j, v in c.items()}
    return result


def moved(c, dz, step):
    keys = set(c) | set(dz)
    return {j: c.get(j, 0j)+step*dz.get(j, 0j) for j in keys}


def blocks(a):
    n = a.shape[0]//2
    return (a[:n, :n], a[:n, n:], a[n:, :n], a[n:, n:])


def stacked(parts):
    return np.block([[parts[0], parts[1]], [parts[2], parts[3]]])


def crop_indices(kmax, cutoff):
    n = 2*kmax+1
    index = np.arange(kmax-cutoff, kmax+cutoff+1)
    return np.concatenate((index, n+index))


@dataclass
class System:
    a: np.ndarray
    b: np.ndarray
    c: np.ndarray
    receiver_rhs: np.ndarray
    cutoff: int

    def crop(self, cutoff):
        idx = crop_indices(self.cutoff, cutoff)
        return System(self.a[np.ix_(idx, idx)], self.b[idx], self.c[:, idx],
                      self.receiver_rhs[idx], cutoff)


def observation_derivative(c, dz, points, wave, cutoff, grid):
    theta = 2*np.pi*np.arange(grid)/grid
    z, normal = curve_values(c, theta)
    velocity, dnormal = curve_values(dz, theta)
    points = np.asarray(points)
    delta = z[:, None] - (points[:, 0]+1j*points[:, 1])[None, :]
    ddelta = velocity[:, None]
    radius = np.abs(delta)
    dr2 = 2*(delta.conj()*ddelta).real
    dgreen = -.125j*wave*hankel1(1, wave*radius)/radius
    d2green = .0625j*wave**2*hankel1(2, wave*radius)/radius**2
    dot = (delta*normal[:, None].conj()).real
    ddot = (ddelta*normal[:, None].conj()
            + delta*dnormal[:, None].conj()).real
    value = dgreen*dr2
    flux = 2*(d2green*dr2*dot + dgreen*ddot)
    modes = np.arange(-cutoff, cutoff+1)
    rhs = np.concatenate((np.fft.fft(value, axis=0)[modes % grid],
                          np.fft.fft(flux, axis=0)[modes % grid]))/grid
    # Transpose of the same fields, evaluated against e^{+int}; no conjugation.
    basis = np.exp(1j*theta[:, None]*modes[None, :])
    obs = 2*np.pi/grid*np.concatenate((flux.T@basis, -value.T@basis), axis=1)
    return rhs, obs


def family(c, ko, ki, cutoff, grid, sources, receivers, direction_map=None):
    op = FourierGalerkinMuller(c, grid=grid)
    a, _ = op.assemble(ko, ki, cutoff)
    b = point_source_traces(c, sources, ko, cutoff, grid=grid)
    obs = receiver_operator(c, receivers, ko, cutoff, grid=grid)
    rb = point_source_traces(c, receivers, ko, cutoff, grid=grid)
    system = System(a, b, obs, rb, cutoff)
    if not direction_map:
        return system, {}
    step = 2*np.pi/grid
    zt, nt = curve_values(c, step*np.arange(grid))
    zs, ns = curve_values(c, step*(np.arange(grid)+.5))
    delta = zt[:, None]-zs[None, :]
    # Analytic d/d(R^2) and d^2/d(R^2)^2 for full and log amplitudes.
    outer, inner = op._amplitudes(ko), op._amplitudes(ki)
    g, gl, d, dl, h, hl = (x-y for x, y in zip(outer, inner))
    radius = op.radius
    d2 = sum(sign*.0625j*k*k*hankel1(2, k*radius)/radius**2
             for sign, k in ((1, ko), (-1, ki)))
    dl2 = sum(-sign*k*k*jv(2, k*radius)/(16*np.pi*radius**2)
              for sign, k in ((1, ko), (-1, ki)))
    hd = ko**2*outer[2] - ki**2*inner[2]
    hld = ko**2*outer[3] - ki**2*inner[3]
    modes = np.arange(-cutoff, cutoff+1)
    derivatives = {}
    for name, dz in direction_map.items():
        vt, dnt = curve_values(dz, step*np.arange(grid))
        vs, dns = curve_values(dz, step*(np.arange(grid)+.5))
        dv = vt[:, None]-vs[None, :]
        dr2 = 2*(delta.conj()*dv).real
        ds = (dv*ns[None, :].conj()+delta*dns[None, :].conj()).real
        dt = (dv*nt[:, None].conj()+delta*dnt[:, None].conj()).real
        dn = (dnt[:, None]*ns[None, :].conj()
              +nt[:, None]*dns[None, :].conj()).real
        amplitudes = (
            (d*dr2, dl*dr2),
            (-2*(d2*dr2*op.source_dot+d*ds),
             -2*(dl2*dr2*op.source_dot+dl*ds)),
            (2*(d2*dr2*op.target_dot+d*dt),
             2*(dl2*dr2*op.target_dot+dl*dt)),
            (hd*dr2*op.normal_dot+h*dn, hld*dr2*op.normal_dot+hl*dn),
        )
        pieces = [kernel_matrix(
            spectrum(log, op.bandwidth, op.shift),
            spectrum(full-log*op.log_symbol, op.bandwidth, op.shift), cutoff)
                  for full, log in amplitudes]
        v, k, kp, t2 = pieces
        t = -modes[:, None]*modes[None, :]*v+t2
        da = np.block([[-k, v], [-t, kp]])
        db, _ = observation_derivative(c, dz, sources, ko, cutoff, grid)
        _, dc = observation_derivative(c, dz, receivers, ko, cutoff, grid)
        derivatives[name] = (da, db, dc)
    return system, derivatives


def crop_derivatives(derivatives, kmax, cutoff):
    idx = crop_indices(kmax, cutoff)
    return {name: (da[np.ix_(idx, idx)], db[idx], dc[:, idx])
            for name, (da, db, dc) in derivatives.items()}


def solve(system, mask=None):
    a = system.a if mask is None else np.eye(len(system.a)) + mask*(
        system.a-np.eye(len(system.a)))
    factors = lu_factor(a)
    x = lu_solve(factors, system.b)
    rx = lu_solve(factors, system.receiver_rhs)
    return dict(a=a, factors=factors, x=x, rx=rx, y=system.c@x)


def data_derivatives(system, derivatives, solution, mask=None):
    result = {}
    for name, (da, db, dc) in derivatives.items():
        da = da if mask is None else da*mask
        dx = lu_solve(solution['factors'], db-da@solution['x'])
        result[name] = dc@solution['x'] + system.c@dx
    return result


def hadamard(c, direction_map, ko, ki, solution, cutoff, grid=2048):
    theta = 2*np.pi*np.arange(grid)/grid
    _, normal = curve_values(c, theta)
    basis = np.exp(1j*theta[:, None]*np.arange(-cutoff, cutoff+1))
    count = 2*cutoff+1
    us, ur = basis@solution['x'][:count], basis@solution['rx'][:count]
    result = {}
    for name, dz in direction_map.items():
        velocity = evaluate(dz, theta)
        weight = (velocity*normal.conj()).real*(2*np.pi/grid)
        result[name] = (ki**2-ko**2)*(ur.T@(weight[:, None]*us))
    return result


def nodal(c, ko, ki, nodes, sources, receivers, direction_map=None, cutoff=None):
    from gpr_bem_kress.execution import execution
    from gpr_bem_kress.system import build_muller_system
    from gpr_bem_kress.forward import (
        kress_incident_trace_on_boundary, build_exterior_receiver_operator)
    curve = parameterization(LaurentGeometry.from_coefficients(c)).discretize(
        nodes, require_even=True)
    with execution(kernels='real_bessel'):
        system = build_muller_system(curve, ko, ki)
        u, n = kress_incident_trace_on_boundary(curve, sources, ko, 1.)
        ru, rn = kress_incident_trace_on_boundary(curve, receivers, ko, 1.)
        obs = build_exterior_receiver_operator(curve, receivers, ko).state_rows
    b = np.concatenate((u, n), axis=1).T
    rb = np.concatenate((ru, rn), axis=1).T
    factors = lu_factor(system.system_matrix)
    x, rx = lu_solve(factors, b), lu_solve(factors, rb)
    theta = (curve.parameters-curve.parameter_origin)*2*np.pi/curve.period
    result = dict(y=obs@x, x=x, rx=rx, matrix=system.system_matrix,
                  b=b, obs=obs, curve=curve, derivatives={})
    for name, dz in (direction_map or {}).items():
        velocity = evaluate(dz, theta)
        normal = velocity.real*curve.normals[:, 0]+velocity.imag*curve.normals[:, 1]
        weight = normal*curve.arc_length_weights
        result['derivatives'][name] = (ki**2-ko**2)*(rx[:nodes].T@(weight[:, None]*x[:nodes]))
    if cutoff is not None:
        e = np.exp(1j*theta[:, None]*np.arange(-cutoff, cutoff+1))
        zero = np.zeros_like(e)
        lift = np.block([[e, zero], [zero, e/curve.speeds[:, None]]])
        restrict = np.block([[e.conj().T, zero.conj().T],
                             [zero.conj().T, e.conj().T*curve.speeds[None, :]]])/nodes
        result['projected'] = restrict@system.system_matrix@lift
    return result


def tail_mask(a, tolerance):
    """Fewest entries for a relative Frobenius tail; stable reverse summation."""
    values = np.abs(a).ravel()
    order = np.argsort(-values, kind='stable')
    squares = values[order]**2
    tail2 = np.concatenate((np.cumsum(squares[::-1])[::-1], [0.]))
    count = int(np.flatnonzero(tail2 <= tolerance*tolerance*tail2[0])[0])
    mask = np.zeros(values.size, bool)
    mask[order[:count]] = True
    return mask.reshape(a.shape)


def block_mask(a, tolerance):
    return stacked([tail_mask(b, tolerance) for b in blocks(a)])


def curve_counts(a, tolerances):
    return [int(block_mask(a, tol).sum()) for tol in tolerances]


def block_errors(a, b):
    scale = max(np.linalg.norm(q) for q in blocks(b))
    return {name: relative(x, y, 1e-12*max(scale, 1e-300))
            for name, x, y in zip(BLOCK_NAMES, blocks(a), blocks(b))}
