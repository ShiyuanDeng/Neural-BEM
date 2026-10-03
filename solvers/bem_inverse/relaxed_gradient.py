"""Complete discrete reduced-loss gradient by variable projection.

Differentiate 1/2 ||C q-d||² + lambda/2 ||A q-b||² at its minimizing q.
Stationarity eliminates dq, but not dA, dC, db or d(lambda). Kernel reverse
assembly reuses the qualified Kress geometry primitives. The outer curve
map supplies its complete position/first-jet tangent, including reparameterization.
"""
import numpy as np

from gpr_bem_kress.geometry_pullback import _difference_matrices, _special_function
from gpr_bem_kress.operators import MullerAssemblyConfig
from .continuation.forward import _solve
from .geometry import values


def reduced_gradient(state, observed, tau, h, rows, space):
    import torch

    if not hasattr(space, 'derivatives'):
        raise ValueError('Relaxed gradient requires complete coefficient tangents from the geometry update.')
    paired = state.acquisition.paired
    lam = float(tau*np.median(np.sum(abs(rows)**2, axis=1)))
    residual = state.prediction-np.asarray(observed)
    if paired:
        dual = residual/(np.sum(abs(h)**2, axis=0)+lam)
        equation_error = -h*dual[None, :]
    else:
        gram = h.conj().T@h
        dual = np.linalg.solve((gram+gram.conj().T)/2+lam*np.eye(len(rows)), residual.T)
        equation_error = -h@dual
    correction, solve_residual = _solve(state.matrix, state.factors, equation_error)
    relaxed = state.traces+correction
    data_error = (rows@relaxed).T-np.asarray(observed) if not paired else np.diag((rows@relaxed).T)-observed
    stationarity = (rows.conj().T@data_error.T if not paired else rows.conj().T*data_error[None, :])
    stationarity += lam*state.matrix.conj().T@equation_error
    scale = max(np.linalg.norm(rows)*np.linalg.norm(data_error), np.finfo(float).tiny)
    # Near an exact fit the data-error subtraction has absolute roundoff on
    # the signal scale; a purely residual-relative gate is meaningless there.
    roundoff = 200*np.finfo(float).eps*np.linalg.norm(rows)*max(
        np.linalg.norm(observed), np.linalg.norm(rows@relaxed))
    if not np.isfinite(relaxed).all() or np.linalg.norm(stationarity) > 1e-8*scale+roundoff:
        raise FloatingPointError('Unqualified relaxed-field stationarity.')

    curve = state.curve
    ko, ki = complex(state.wavenumber), complex(state.interior_wavenumber)
    special = _special_function(torch)
    with torch.enable_grad():
        points = torch.tensor(curve.points, dtype=torch.float64, requires_grad=True)
        first = torch.tensor(curve.first_derivatives, dtype=torch.float64, requires_grad=True)
        speed = torch.linalg.vector_norm(first, dim=-1)
        tangent = first/speed[:, None]
        normals = torch.stack((tangent[:, 1], -tangent[:, 0]), dim=1)
        theta_speed = speed*(curve.period/(2*np.pi))
        arc = theta_speed*(2*np.pi/curve.num_nodes)
        (v, k, kp, t), diagnostics = _difference_matrices(
            torch, special, points, normals, theta_speed, ko, ki, MullerAssemblyConfig())
        identity = torch.eye(curve.num_nodes, dtype=torch.complex128)
        system = torch.cat((torch.cat((identity-k, v), dim=1),
                            torch.cat((-t, identity+kp), dim=1)), dim=0)
        sources = torch.tensor(state.acquisition.sources, dtype=torch.float64)
        delta = points[None, :, :]-sources[:, None, :]
        radius = torch.linalg.vector_norm(delta, dim=-1)
        projection = torch.sum(delta*normals[None, :, :], dim=-1)/radius
        strength = state.acquisition.strength
        incident = strength*.25j*special(ko*radius, 0, 'hankel')
        normal = -strength*.25j*ko*special(ko*radius, 1, 'hankel')*projection
        rhs = torch.cat((incident, normal), dim=1).T
        receivers = torch.tensor(state.acquisition.receivers, dtype=torch.float64)
        delta = receivers[:, None, :]-points[None, :, :]
        radius = torch.linalg.vector_norm(delta, dim=-1)
        projection = torch.sum(delta*normals[None, :, :], dim=-1)/radius
        single = .25j*special(ko*radius, 0, 'hankel')*arc[None, :]
        double = .25j*ko*special(ko*radius, 1, 'hankel')*projection*arc[None, :]
        receiver = torch.cat((double, -single), dim=1)
        for name, rebuilt, stored in [('A', system, state.matrix), ('C', receiver, rows)]:
            relative = np.linalg.norm(rebuilt.detach().numpy()-stored)/max(np.linalg.norm(stored), np.finfo(float).tiny)
            diagnostics['primal_'+name+'_relative'] = float(relative)
            if relative > 2e-10:
                raise FloatingPointError('Relaxed reverse assembly differs from production '+name)
        # numpy.median averages the two central values for even receiver counts.
        row_norms = torch.sort(torch.sum(abs(receiver)**2, dim=1)).values
        count = len(row_norms)
        penalty = tau*(row_norms[(count-1)//2]+row_norms[count//2])/2
        q = torch.tensor(relaxed, dtype=torch.complex128)
        prediction = (receiver@q).T
        if paired:
            prediction = torch.diag(prediction)
        error = prediction-torch.tensor(np.asarray(observed), dtype=torch.complex128)
        defect = system@q-rhs
        loss = .5*torch.sum(abs(error)**2)+.5*penalty*torch.sum(abs(defect)**2)
        point_gradient, first_gradient = torch.autograd.grad(loss, (points, first))
    directions = np.asarray(space.derivatives)
    orders = np.arange(-(len(directions)//2), len(directions)//2+1)
    z = values(directions, curve.num_nodes)
    dz = values(1j*orders[:, None]*directions, curve.num_nodes)
    pg, fg = point_gradient.numpy(), first_gradient.numpy()
    gradient = pg[:, 0]@z.real+pg[:, 1]@z.imag+fg[:, 0]@dz.real+fg[:, 1]@dz.imag
    if not np.isfinite(gradient).all():
        raise FloatingPointError('Nonfinite complete relaxed gradient')
    diagnostics.update(stationarity_relative=float(np.linalg.norm(stationarity)/scale),
        stationarity_absolute=float(np.linalg.norm(stationarity)), stationarity_roundoff_allowance=float(roundoff),
        correction_solve_residual=solve_residual, variable_projection_loss=float(loss.detach()),
        derivative='complete reduced loss; exact kernel reverse pass and supplied geometry tangents',
        penalty_derivative='median row norm included; fixed ordering away from ties')
    return gradient, diagnostics
