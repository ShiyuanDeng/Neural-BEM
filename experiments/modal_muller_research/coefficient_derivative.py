"""Analytic shape derivatives entirely in Laurent/Fourier coefficient space.

Fixed canonical scale and expansion center: translations live in z_0.
The log derivative is 2 Re(delta W / W). Reusing that reciprocal avoids
rebuilding the logarithm for each direction. Coefficient-window refinement
and finite-difference tests separately check the truncation of this identity.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1
from scipy.signal import fftconvolve

from .coefficient_operator import (CoefficientGeometry, add, conjugate, dense_product,
    embed, kernel_matrix, multiply, sparse_product, times)
from .coefficient_fields import RegularWaves, convolve_sparse


def geometry_polynomials(z):
    target, source = {(j,0):v for j,v in z.items()}, {(0,j):v for j,v in z.items()}
    delta = add(target,source,-1)
    nt, ns = {(j,0):j*v for j,v in z.items()}, {(0,j):j*v for j,v in z.items()}
    return delta,nt,ns


def dot(a,b):
    return times(add(multiply(a,conjugate(b)),multiply(conjugate(a),b)),.5)


@dataclass
class GeometryDirection:
    radius_squared: dict
    source_dot: dict
    target_dot: dict
    normal_dot: dict
    log_quotient: np.ndarray


def prepare_direction(prepared, dz):
    d,nt,ns=geometry_polynomials(prepared.geometry.coefficients)
    dd,dnt,dns=geometry_polynomials(dz)
    quotient={}
    for j,value in dz.items():
        if j>0:
            for r in range(j):
                key=(j-1-r,r)
                quotient[key]=quotient.get(key,0)+value
        elif j<0:
            for r in range(-j):
                key=(-1-r,j+r)
                quotient[key]=quotient.get(key,0)-value
    log_delta=sparse_product(prepared.inverse_quotient,quotient)
    return GeometryDirection(times(dot(d,dd),2),add(dot(dd,ns),dot(d,dns)),
        add(dot(dd,nt),dot(d,dnt)),add(dot(dnt,ns),dot(nt,dns)),
        log_delta+log_delta[::-1,::-1].conj())


class ShapeOperator:
    """One-frequency radial coefficients cached for any number of shape directions."""
    def __init__(self,prepared,ko,ki,cutoff=32,terms=24,powers=None):
        self.prepared,self.cutoff=prepared,cutoff
        ko,ki=ko*prepared.geometry.scale,ki*prepared.geometry.scale
        b=prepared.bandwidth
        shape=(2*b+1,2*b+1)
        # P,Q and first polynomial derivatives for each of F, F_R, k^2 G.
        coeff=np.zeros((3,2,terms),complex)
        ao=ai=1.
        harmonic=0.
        for p in range(terms):
            if p:
                ao*=-(ko*ko/4)/(p*p)
                ai*=-(ki*ki/4)/(p*p)
                harmonic+=1/p
            po,pi=-ao/(4*np.pi),-ai/(4*np.pi)
            qo=ao*(.25j+(harmonic-np.euler_gamma-np.log(ko/2))/(2*np.pi))
            qi=ai*(.25j+(harmonic-np.euler_gamma-np.log(ki/2))/(2*np.pi))
            coeff[0,:,p]=(po-pi,qo-qi)
            coeff[2,:,p]=(ko*ko*po-ki*ki*pi,ko*ko*qo-ki*ki*qi)
            if p:
                coeff[1,:,p-1]=(p*(po-pi),po-pi+p*(qo-qi))
        if powers is None:
            powers=geometry_powers(prepared,terms)
        values=np.einsum('abp,pij->abij',coeff,powers,optimize=False)
        derivatives=np.einsum('abp,pij->abij',coeff[:,:,1:]*np.arange(1,terms),
                              powers[:-1],optimize=False)
        self.p,self.q=values[:,0],values[:,1]
        self.dp,self.dq=derivatives[:,0],derivatives[:,1]
        self.smooth=np.array([q+dense_product(p,prepared.log_quotient) for p,q in zip(self.p,self.q)])
        v=kernel_matrix(self.p[0],self.smooth[0],cutoff)
        k=kernel_matrix(sparse_product(self.p[1],times(prepared.source_dot,-2)),
                        sparse_product(self.smooth[1],times(prepared.source_dot,-2)),cutoff)
        kp=k[::-1,::-1].T
        self.modes=np.arange(-cutoff,cutoff+1)
        t=-self.modes[:,None]*self.modes[None,:]*v+kernel_matrix(
            sparse_product(self.p[2],prepared.normal_dot),
            sparse_product(self.smooth[2],prepared.normal_dot),cutoff)
        eye=np.eye(len(self.modes))
        self.a=np.block([[eye-k,v],[-t,eye+kp]])

    def derivative(self,direction):
        if not direction.radius_squared and not direction.source_dot and not direction.normal_dot:
            return np.zeros_like(self.a)
        p=np.array([sparse_product(v,direction.radius_squared) for v in self.dp])
        q=np.array([sparse_product(v,direction.radius_squared) for v in self.dq])
        smooth=np.array([qq+dense_product(pp,self.prepared.log_quotient)
                          +dense_product(orig,direction.log_quotient)
                          for pp,qq,orig in zip(p,q,self.p)])
        v=kernel_matrix(p[0],smooth[0],self.cutoff)
        k=kernel_matrix(-2*(sparse_product(p[1],self.prepared.source_dot)
                            +sparse_product(self.p[1],direction.source_dot)),
                        -2*(sparse_product(smooth[1],self.prepared.source_dot)
                            +sparse_product(self.smooth[1],direction.source_dot)),self.cutoff)
        kp=k[::-1,::-1].T
        t=-self.modes[:,None]*self.modes[None,:]*v+kernel_matrix(
            sparse_product(p[2],self.prepared.normal_dot)+sparse_product(self.p[2],direction.normal_dot),
            sparse_product(smooth[2],self.prepared.normal_dot)+sparse_product(self.smooth[2],direction.normal_dot),self.cutoff)
        return np.block([[-k,v],[-t,kp]])


class FixedAcquisition:
    """Center-to-acquisition Graf weights survive every shape update."""
    def __init__(self,center,scale,wave,sources,receivers,strengths=1e-6,angular_order=24):
        self.center,self.scale,self.wave=center,scale,wave
        self.sources,self.receivers=np.asarray(sources),np.asarray(receivers)
        self.angular_order=angular_order
        self.strengths=np.asarray(strengths)
        modes=np.arange(-angular_order,angular_order+1)
        def weights(points):
            delta=points[:,0]+1j*points[:,1]-center
            return .25j*hankel1(modes[:,None],wave*np.abs(delta)[None,:])*np.exp(
                -1j*modes[:,None]*np.angle(delta)[None,:])
        self.source_weights,self.receiver_weights=weights(self.sources),weights(self.receivers)


class ShapeFields:
    def __init__(self,geometry,acquisition,bandwidth,cutoff,terms):
        if geometry.center!=acquisition.center or geometry.scale!=acquisition.scale:
            raise ValueError('Fixed expansion center and scale must match the acquisition cache.')
        self.geometry,self.acquisition,self.cutoff=geometry,acquisition,cutoff
        self.bandwidth=bandwidth
        radius=geometry.scale*sum(abs(v) for v in geometry.coefficients.values())
        for points in (acquisition.sources,acquisition.receivers):
            distance=np.abs(points[:,0]+1j*points[:,1]-geometry.center)
            if np.any(distance<=radius):
                raise ValueError('Geometry leaves the fixed-center Graf convergence disk.')
        self.waves=RegularWaves(geometry,acquisition.wave,bandwidth,acquisition.angular_order+2,terms)
        self.b,self.c=self.maps(self.waves.values[:,2:-2],self.waves.flux[:,2:-2])

    def maps(self,f,q):
        test=self.bandwidth+np.arange(-self.cutoff,self.cutoff+1)
        trial=self.bandwidth-np.arange(-self.cutoff,self.cutoff+1)
        acq=self.acquisition
        b=np.concatenate((f[test]@acq.source_weights,q[test]@acq.source_weights))*acq.strengths
        c=2*np.pi*np.concatenate(((q[trial]@acq.receiver_weights).T,
                                  -(f[trial]@acq.receiver_weights).T),axis=1)
        return b,c

    def derivative(self,dz):
        z=self.geometry.coefficients
        zbar={-j:v.conjugate() for j,v in z.items()}
        dzbar={-j:v.conjugate() for j,v in dz.items()}
        h=self.geometry.scale*self.acquisition.wave
        f=self.waves.values
        df=h/2*(convolve_sparse(f[:,:-2],dz)-convolve_sparse(f[:,2:],dzbar))
        dq=h/2*(convolve_sparse(f[:,1:-3],{j:j*v for j,v in dz.items()})
                 +convolve_sparse(f[:,3:-1],{j:j*v for j,v in dzbar.items()})
                 +convolve_sparse(df[:,:-2],{j:j*v for j,v in z.items()})
                 +convolve_sparse(df[:,2:],{j:j*v for j,v in zbar.items()}))
        return self.maps(df[:,1:-1],dq)


class NativeShapeForward:
    def __init__(self,geometry,acquisitions,interior_waves,*,cutoff=32,bandwidth=64,terms=24):
        tick=perf_counter()
        self.prepared=CoefficientGeometry(geometry,bandwidth)
        self.interior_waves=tuple(interior_waves)
        powers=geometry_powers(self.prepared,terms)
        self.states=[]
        self.outputs=[]
        for acquisition,ki in zip(acquisitions,interior_waves):
            operator=ShapeOperator(self.prepared,acquisition.wave,ki,cutoff,terms,powers)
            fields=ShapeFields(geometry,acquisition,bandwidth,cutoff,terms)
            factors=lu_factor(operator.a)
            u=lu_solve(factors,fields.b)
            self.outputs.append(fields.c@u)
            self.states.append((operator,fields,factors,u))
        self.seconds=perf_counter()-tick

    def jacobian(self,directions):
        tick=perf_counter()
        geometries=[prepare_direction(self.prepared,dz) for dz in directions]
        result=[]
        for operator,fields,factors,u in self.states:
            # Transfer C A^-1 permits all parameter contractions after one adjoint-side solve.
            transfer=lu_solve(factors,fields.c.T,trans=1).T
            columns=[]
            for dz,direction in zip(directions,geometries):
                da=operator.derivative(direction)
                db,dc=fields.derivative(dz)
                columns.append(dc@u+transfer@(db-da@u))
            result.append(np.stack(columns,axis=-1))
        self.jacobian_seconds=perf_counter()-tick
        return result

    def hadamard_jacobian(self,directions):
        """Continuum shape derivative using reciprocity, with modal integration.

        For equal permeability and fixed source strengths:
        dY_rs=(ki^2-ko^2) int u_s u_r (delta x dot n) ds.
        Receiver illumination is unit strength; no complex conjugation occurs
        in this reciprocal bilinear identity. At finite trace cutoff this is
        not exactly the derivative of the discrete Galerkin solve. Check
        mode convergence and operator-Jacobian agreement before relying on it.
        """
        tick=perf_counter()
        z=self.prepared.geometry.coefficients
        normal={(j,):j*v for j,v in z.items()}
        weights=[]
        for dz in directions:
            delta={(j,):v for j,v in dz.items()}
            weights.append(times(add(multiply(delta,conjugate(normal)),
                                     multiply(conjugate(delta),normal)),
                                 .5*self.prepared.geometry.scale**2))
        result=[]
        for ki,(operator,fields,factors,u) in zip(self.interior_waves,self.states):
            cutoff=operator.cutoff
            indices=fields.bandwidth+operator.modes
            f,q=fields.waves.values[:,2:-2],fields.waves.flux[:,2:-2]
            br=np.concatenate((f[indices]@fields.acquisition.receiver_weights,
                               q[indices]@fields.acquisition.receiver_weights))
            receiver_trace=lu_solve(factors,br)[:2*cutoff+1]
            source_trace=u[:2*cutoff+1]
            moments=fftconvolve(receiver_trace[:,:,None],source_trace[:,None,:],axes=0)
            columns=[]
            for weight in weights:
                column=np.zeros(moments.shape[1:],complex)
                for (mode,),value in weight.items():
                    if abs(mode)<=2*cutoff:
                        column+=value*moments[2*cutoff-mode]
                columns.append(2*np.pi*(ki**2-fields.acquisition.wave**2)*column)
            result.append(np.stack(columns,axis=-1))
        self.jacobian_seconds=perf_counter()-tick
        return result


def geometry_powers(prepared,terms):
    """Frequency-independent kernel moments; rebuild once per candidate shape."""
    powers=[embed({(0,0):1},prepared.bandwidth)]
    for _ in range(1,terms):
        powers.append(sparse_product(powers[-1],prepared.radius_squared))
    return np.stack(powers)
