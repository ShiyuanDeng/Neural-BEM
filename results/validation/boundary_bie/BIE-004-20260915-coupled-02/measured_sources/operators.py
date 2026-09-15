"""Coupled shape-only directional operators using existing analytic self jets.

Private Kress jet helpers are pinned dependencies, not a new production API.
The only new kernel differentiation is for smooth, directed exterior cross
blocks. No finite differences, solve, fitting or re-gauging occurs here.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.special import hankel1
from gpr_bem_kress.shape_derivative import (
    KressDirection, _Jet, _norm, _sum, _special, _stack, _difference_matrices,
)


@dataclass(frozen=True)
class DirectionalOperators:
    dA: np.ndarray
    dB: np.ndarray
    dC: np.ndarray
    diagnostics: dict


def component_jets(curve, direction):
    if not isinstance(direction, KressDirection):
        raise TypeError('Each component direction must be a KressDirection.')
    if direction.exterior_epsr or direction.interior_epsr or direction.source_strengths is not None:
        raise ValueError('BIE-004 supports shape directions only.')
    for name in ('points', 'first_derivatives', 'second_derivatives', 'third_derivatives'):
        values = getattr(direction, name)
        if values is not None and values.shape != (curve.num_nodes, 2):
            raise ValueError(f'{name} must match the component node grid.')
    points = _Jet(curve.points, 0.0 if direction.points is None else direction.points)
    first = _Jet(curve.first_derivatives,
                 0.0 if direction.first_derivatives is None else direction.first_derivatives)
    speed = _norm(first)
    tangent = first / speed[:, None]
    normal = _Jet(np.column_stack((tangent.v[:, 1], -tangent.v[:, 0])),
                  np.column_stack((tangent.d[:, 1], -tangent.d[:, 0])))
    theta_speed = speed * (curve.period / (2*np.pi))
    arc = theta_speed * (2*np.pi/curve.num_nodes)
    return points, normal, theta_speed, arc


def exterior_cross_jets(target, source, wave):
    """Analytic jets of the production exterior-only cross V/K/Kp/T blocks."""
    tp, tn, _, _ = target
    sp, sn, _, arc = source
    displacement = tp[:, None, :] - sp[None, :, :]
    radius = _norm(displacement)
    if np.any(radius.v <= 0):
        raise ValueError('Cross-component distances must be positive.')
    tx = _sum(displacement * tn[:, None, :])
    sy = _sum(displacement * sn[None, :, :])
    nn = _sum(tn[:, None, :] * sn[None, :, :])
    z = wave*radius
    green = .25j*_special(hankel1, 0, z)
    radial_first = -.25j*wave*_special(hankel1, 1, z)/radius
    anisotropy = .25j*wave**2*_special(hankel1, 2, z)
    projection = tx*sy/radius**2
    weights = arc[None, :]
    return (green*weights, -radial_first*sy*weights, radial_first*tx*weights,
            (-radial_first*nn-anisotropy*projection)*weights)


def directional_operators(base, directions):
    """Differentiate global A/B/C at fixed grids, topology and materials.

    ``base`` is the experiment's stored production-matrix record. Values and
    component ordering are checked against it on every invocation.
    """
    started = perf_counter()
    boundary = base.system.geometry
    if len(directions) != boundary.num_components:
        raise ValueError('One direction is required per component, in stored order.')
    jets = [component_jets(c, d) for c,d in zip(boundary.components, directions)]
    active = [bool(np.any(j[0].d) or np.any(j[1].d) or np.any(j[2].d)) for j in jets]
    ko, ki = _Jet(base.system.k_exterior), _Jet(base.system.k_interior)
    count = boundary.num_nodes
    primal = [np.zeros((count,count), complex) for _ in range(4)]
    derivative = [np.zeros((count,count), complex) for _ in range(4)]
    self_seconds, cross_seconds = 0., 0.
    self_calls, cross_calls = 0, 0
    branch_diagnostics = []
    self_blocks = base.system.difference_blocks.self_blocks
    for i,sl in enumerate(boundary.component_slices):
        if active[i]:
            tick = perf_counter()
            p,n,s,_ = jets[i]
            values, info = _difference_matrices(p,n,s,ko,ki,base.system.assembly_config.self_assembly)
            self_seconds += perf_counter()-tick
            self_calls += 1
            branch_diagnostics.append(dict(component=i, **info))
            for a,da,v in zip(primal,derivative,values):
                a[sl,sl], da[sl,sl] = v.v,v.d
        else:
            for a,name in zip(primal,('delta_v','delta_k','delta_kp','delta_t')):
                a[sl,sl] = getattr(self_blocks[i],name)
    for i,rs in enumerate(boundary.component_slices):
        for j,cs in enumerate(boundary.component_slices):
            if i==j:
                continue
            if active[i] or active[j]:
                tick = perf_counter()
                values = exterior_cross_jets(jets[i],jets[j],ko)
                cross_seconds += perf_counter()-tick
                cross_calls += 1
                for a,da,v in zip(primal,derivative,values):
                    a[rs,cs],da[rs,cs] = v.v,v.d
            else:
                for a,name in zip(primal,('delta_v','delta_k','delta_kp','delta_t')):
                    a[rs,cs] = getattr(base.system.difference_blocks,name)[rs,cs]
    v,k,kp,t = [_Jet(a,da) for a,da in zip(primal,derivative)]
    identity = np.eye(count)
    system = _stack((_stack((identity-k,v),1),_stack((-t,identity+kp),1)),0)
    tick = perf_counter()
    points = _stack([j[0] for j in jets],0)
    normals = _stack([j[1] for j in jets],0)
    arc = _stack([j[3] for j in jets],0)
    displacement = points[None,:,:]-base.sources[:,None,:]
    distance = _norm(displacement)
    projection = _sum(displacement*normals[None,:,:])/distance
    bd = base.strengths[:,None]*.25j*_special(hankel1,0,ko*distance)
    bn = -base.strengths[:,None]*.25j*ko*_special(hankel1,1,ko*distance)*projection
    rhs_rows = _stack((bd,bn),1)
    displacement = base.receivers[:,None,:]-points[None,:,:]
    distance = _norm(displacement)
    projection = _sum(displacement*normals[None,:,:])/distance
    single = .25j*_special(hankel1,0,ko*distance)*arc[None,:]
    double = .25j*ko*_special(hankel1,1,ko*distance)*projection*arc[None,:]
    receiver = _stack((double,-single),1)
    boundary_seconds = perf_counter()-tick
    checks = {}
    for name,actual,stored in (('A',system.v,base.A),('B',rhs_rows.v.T,base.B),
                               ('C',receiver.v,base.C)):
        rel = float(np.linalg.norm(actual-stored)/max(np.linalg.norm(stored),np.finfo(float).tiny))
        checks[name] = rel
        if not np.isfinite(rel) or rel>2e-11:
            raise ValueError(f'Analytic primal {name} mismatch: {rel:.3e}')
    results = [system.d, rhs_rows.d.T, receiver.d]
    for value in results:
        if not np.all(np.isfinite(value)):
            raise FloatingPointError('Nonfinite coupled derivative')
        value.setflags(write=False)
    return DirectionalOperators(*results,dict(
        total_seconds=perf_counter()-started, self_seconds=self_seconds,
        cross_seconds=cross_seconds, incident_receiver_seconds=boundary_seconds,
        self_primal_kernel_reassemblies=self_calls, cross_primal_kernel_reassemblies=cross_calls,
        skipped_self_blocks=len(jets)-self_calls,
        skipped_cross_blocks=len(jets)*(len(jets)-1)-cross_calls,
        active_components=active, primal_relative_errors=checks,
        branch_diagnostics=branch_diagnostics, finite_difference_probes=0,
        unknown_order='all components u_D, then all components u_N',
        shape_only=True, incident_receiver_derivative='exact zero: acquisition/materials fixed'))
