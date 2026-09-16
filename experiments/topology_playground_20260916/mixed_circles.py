"""Experimental heterogeneous circular T-matrix: dielectric or PEC per object.

Uses the same H1/G=i*H0/4 convention and normalized Graf translations as
multicylinder_ref. PEC means scalar TMz Dirichlet (Ez=0), not finite conductivity.
Graf identity: https://dlmf.nist.gov/10.23#ii
The six geometry derivatives include translations, source/receiver operators,
radius-dependent scattering coefficients, and the implicit coupled solve.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1, h1vp, jv, jvp


def wave(frequency, epsr):
    from config.base_config import EPS0, MU0
    return 2*np.pi*frequency*np.sqrt(EPS0*MU0*epsr)


def coefficients(modes, ke, radius, interior):
    """Return H(ka), dH/da, H(ka)*R, and its radius derivative."""
    z = ke*radius
    scale, ds = hankel1(modes,z), ke*h1vp(modes,z)
    je, dje = jv(modes,z), jvp(modes,z)
    if interior is None:
        return scale, ds, -je, -ke*dje
    zi=interior*radius
    ji,dji=jv(modes,zi),jvp(modes,zi)
    he,dhe=scale,h1vp(modes,z)
    numerator=interior*dji*je-ke*dje*ji
    denominator=ke*dhe*ji-interior*dji*he
    dn=interior**2*jvp(modes,zi,2)*je-ke**2*jvp(modes,z,2)*ji
    dd=ke**2*h1vp(modes,z,2)*ji-interior**2*jvp(modes,zi,2)*he
    ratio=numerator/denominator
    derivative=(dn-ratio*dd)/denominator
    return scale, ds, scale*ratio, ds*ratio+scale*derivative


def polar(displacement):
    radius=np.linalg.norm(displacement,axis=-1)
    angle=np.arctan2(displacement[...,1],displacement[...,0])
    dr=displacement/radius[...,None]
    dt=np.stack((-displacement[...,1],displacement[...,0]),axis=-1)/radius[...,None]**2
    return radius,angle,dr,dt


def one_frequency(parameters, kinds, sources, receivers, frequency, *,
                  order=12, sand_epsr=6., plastic_epsr=3., jacobian=False,
                  return_details=False):
    q=np.asarray(parameters,float).reshape(-1,3)
    sources,receivers=np.asarray(sources,float),np.asarray(receivers,float)
    count=len(q); size=2*order+1; modes=np.arange(-order,order+1)
    if len(kinds)!=count or any(k not in ('plastic','metal') for k in kinds):
        raise ValueError('One plastic/metal label is required per circle')
    if np.any(q[:,2]<=0): raise ValueError('Positive radii required')
    for i in range(count):
        for j in range(i):
            if np.linalg.norm(q[i,:2]-q[j,:2]) <= q[i,2]+q[j,2]:
                raise ValueError('Circles must be disjoint')
        if min(np.linalg.norm(sources-q[i,:2],axis=1).min(),
               np.linalg.norm(receivers-q[i,:2],axis=1).min()) <= q[i,2]:
            raise ValueError('Acquisition must be exterior')
    ke=wave(frequency,sand_epsr)
    ki=wave(frequency,plastic_epsr)
    values=[coefficients(modes,ke,row[2],None if kind=='metal' else ki)
            for row,kind in zip(q,kinds)]
    scales,dscales,ratios,dratios=map(np.array,zip(*values))
    matrix=np.eye(count*size,dtype=complex)
    rhs=np.empty((count*size,len(sources)),complex)
    receiver=np.empty((len(receivers),count*size),complex)
    if jacobian:
        dm=np.zeros((3*count,count*size,count*size),complex)
        db=np.zeros((3*count,count*size,len(sources)),complex)
        de=np.zeros((3*count,len(receivers),count*size),complex)
    for i,row in enumerate(q):
        sl=slice(i*size,(i+1)*size)
        rad,theta,dr,dt=polar(sources-row[:2])
        hs=hankel1(modes[:,None],ke*rad)
        phase=np.exp(-1j*modes[:,None]*theta)
        incident=.25j*hs*phase
        rhs[sl]=ratios[i,:,None]*incident
        rad_r,theta_r,dr_r,dt_r=polar(receivers-row[:2])
        hr=hankel1(modes[None,:],ke*rad_r[:,None])
        phase_r=np.exp(1j*modes[None,:]*theta_r[:,None])
        receiver[:,sl]=hr*phase_r/scales[i]
        if jacobian:
            for axis in (0,1):
                db[3*i+axis,sl]=ratios[i,:,None]*.25j*phase*(
                    -ke*h1vp(modes[:,None],ke*rad)*dr[:,axis]
                    +1j*modes[:,None]*hs*dt[:,axis])
                de[3*i+axis,:,sl]=phase_r/scales[i]*(
                    -ke*h1vp(modes[None,:],ke*rad_r[:,None])*dr_r[:,axis,None]
                    -1j*modes[None,:]*hr*dt_r[:,axis,None])
            db[3*i+2,sl]=dratios[i,:,None]*incident
            de[3*i+2,:,sl]=-receiver[:,sl]*dscales[i]/scales[i]
        for j,other in enumerate(q):
            if i==j:continue
            sj=slice(j*size,(j+1)*size)
            distance,angle,dr_t,dt_t=polar(other[:2]-row[:2])
            orders=modes[:,None]-modes[None,:]
            ht=hankel1(orders,ke*distance)
            phase_t=np.exp(-1j*orders*angle)
            translation=ht*phase_t
            multiplier=-ratios[i,:,None]/scales[j,None,:]
            block=multiplier*translation
            matrix[sl,sj]=block
            if jacobian:
                for axis in (0,1):
                    derivative=multiplier*phase_t*(
                        ke*h1vp(orders,ke*distance)*dr_t[axis]
                        -1j*orders*ht*dt_t[axis])
                    dm[3*i+axis,sl,sj]=-derivative
                    dm[3*j+axis,sl,sj]=derivative
                dm[3*i+2,sl,sj]=-dratios[i,:,None]*translation/scales[j,None,:]
                dm[3*j+2,sl,sj]=-block*dscales[j,None,:]/scales[j,None,:]
    lu=lu_factor(matrix)
    outgoing=lu_solve(lu,rhs)
    prediction=np.einsum('pi,ip->p',receiver,outgoing)
    result=(prediction,)
    if jacobian:
        tangent_rhs=db-np.einsum('aij,jp->aip',dm,outgoing)
        tangent=lu_solve(lu,tangent_rhs.transpose(1,0,2).reshape(count*size,-1))
        tangent=tangent.reshape(count*size,3*count,len(sources)).transpose(1,0,2)
        derivative=(np.einsum('api,ip->pa',de,outgoing)
                    +np.einsum('pi,aip->pa',receiver,tangent))
        result+=(derivative,)
    if return_details:
        result+=(dict(matrix=matrix,rhs=rhs,outgoing=outgoing,scales=scales,modes=modes,
                      linear_residual=np.linalg.norm(matrix@outgoing-rhs)/np.linalg.norm(rhs)),)
    return result[0] if len(result)==1 else result


def predict(parameters,kinds,sources,receivers,frequencies,*,order=12,jacobian=False):
    values=[one_frequency(parameters,kinds,sources,receivers,f,order=order,jacobian=jacobian)
            for f in frequencies]
    if jacobian:
        return np.stack([v[0] for v in values],axis=1),np.stack([v[1] for v in values],axis=1)
    return np.stack(values,axis=1)
