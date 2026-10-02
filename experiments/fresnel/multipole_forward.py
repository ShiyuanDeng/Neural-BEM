"""Experimental Kress RHS adapter for fixed calibrated multipole illumination.

Production operators and their analytic geometry derivatives are reused. Only
incident traces and their derivatives differ. Calibration coefficients remain
fixed during geometry fitting. No finite-difference shape Jacobian is used.
"""
from dataclasses import dataclass
import numpy as np
from scipy.constants import c, epsilon_0, mu_0
from gpr_bem_kress import Material, solve_kress_tmz_total_field_batch
from gpr_bem_kress.shape_derivative import _directional_operators
from .multipole_sources import multipole_basis


@dataclass(frozen=True)
class MultipoleForward:
    operator_base: object
    solution: np.ndarray
    incident: np.ndarray
    gradient: np.ndarray
    hessian: np.ndarray
    scattered_receiver: np.ndarray
    linear_system_relative_residual: float
    incident_representation_relative_leak: float


def solve_multipole_forward(curve, sources, receivers, wavenumber, coefficients, *, epsr=3.):
    coefficients=np.asarray(coefficients,complex)
    if coefficients.ndim!=1 or len(coefficients)%2!=1 or not np.isfinite(coefficients).all():
        raise ValueError('An odd finite coefficient vector is required.')
    # This unmodified line-source result provides the accepted matrices and
    # derivative primal checks. Its line-source RHS is not used in the new solve.
    base=solve_kress_tmz_total_field_batch(curve,sources,receivers,wavenumber*c,
        exterior=Material(1.),interior=Material(epsr),eps0=epsilon_0,mu0=mu_0)
    order=(len(coefficients)-1)//2
    values=[];gradients=[];hessians=[]
    for source in sources:
        value,gradient,hessian=multipole_basis(curve.points,source,wavenumber,order)
        values.append(value@coefficients)
        gradients.append(np.einsum('pmd,m->pd',gradient,coefficients))
        hessians.append(np.einsum('pmde,m->pde',hessian,coefficients))
    values,gradients,hessians=map(np.asarray,(values,gradients,hessians))
    normals=np.einsum('spd,pd->sp',gradients,curve.normals)
    rhs=np.concatenate((values,normals),axis=1).T
    solution=np.linalg.solve(base.system.system_matrix,rhs)
    prediction=(base.receiver_operator.state_rows@solution).T
    leak=(base.receiver_operator.state_rows@rhs).T
    return MultipoleForward(base,solution,values,gradients,hessians,prediction,
        float(np.linalg.norm(base.system.system_matrix@solution-rhs)/np.linalg.norm(rhs)),
        float(np.linalg.norm(leak)/np.linalg.norm(values)))


def linearize_multipole_forward(base, direction):
    """Exact discrete geometric JVP, including incident Hessian/normal terms."""
    curve=base.operator_base.system.geometry
    if direction.exterior_epsr or direction.interior_epsr or direction.source_strengths is not None:
        raise ValueError('This adapter qualifies fixed material and incident calibration only.')
    velocity=np.zeros_like(curve.points) if direction.points is None else direction.points
    dfirst=np.zeros_like(curve.points) if direction.first_derivatives is None else direction.first_derivatives
    tangent=curve.first_derivatives/curve.speeds[:,None]
    dt=(dfirst-tangent*np.sum(tangent*dfirst,axis=1)[:,None])/curve.speeds[:,None]
    dn=np.column_stack((dt[:,1],-dt[:,0]))
    dd=np.einsum('spd,pd->sp',base.gradient,velocity)
    dgradient=np.einsum('spde,pe->spd',base.hessian,velocity)
    dnormal=np.einsum('spd,pd->sp',dgradient,curve.normals)+np.einsum('spd,pd->sp',base.gradient,dn)
    db=np.concatenate((dd,dnormal),axis=1).T
    operators=_directional_operators(base.operator_base,direction)
    du=np.linalg.solve(base.operator_base.system.system_matrix,
        db-operators.d_system_matrix@base.solution)
    return (operators.d_receiver_matrix@base.solution+base.operator_base.receiver_operator.state_rows@du).T
