"""Smooth layered corrections to the existing full-space Muller/Kress BIE.

Air occupies y>0; soil and the buried interface occupy y<0. Equal mu and
e^{-i omega t} imply continuity of u and its normal derivative. All sources
and receivers are in air. This is a Sommerfeld formulation, not WGF.
"""
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.linalg import lu_factor, lu_solve

from experiments.support_certificates.layered import Layered
from gpr_bem_kress import build_muller_system


def outgoing_beta(k, xi):
    beta = np.sqrt(complex(k)**2-np.asarray(xi)**2+0j)
    return np.where(beta.imag<0,-beta,beta)


def fresnel(kair, ksoil, horizontal):
    ba,bg = outgoing_beta(kair,horizontal),outgoing_beta(ksoil,horizontal)
    return (ba-bg)/(ba+bg),2*ba/(ba+bg)


class Sommerfeld(Layered):
    """Reuse established spectral representation with both branch points resolved.

    Sin-squared segment maps cluster at both endpoints; unlike the historical
    volume screen's air-only square map, this also resolves the real soil
    branch point for a lossless background.
    """
    def __init__(self,kair,ksoil,order=64,cutoff=400.):
        self.ka,self.kg=complex(kair),complex(ksoil)
        if any(k.real<=0 or k.imag<0 for k in (self.ka,self.kg)):
            raise ValueError('Require positive-real passive outgoing wavenumbers.')
        if order<4 or int(order)!=order or cutoff<=2*max(self.ka.real,self.kg.real):
            raise ValueError('Order>=4 and cutoff>2 max(Re k) are required.')
        self.order,self.cutoff=int(order),float(cutoff)
        t,w=leggauss(self.order)
        t,w=(t+1)/2,w/2
        breaks=sorted(set([0.,self.ka.real,self.kg.real,2*max(self.ka.real,self.kg.real),self.cutoff]))
        q=np.sin(np.pi*t/2)**2
        jac=np.pi*np.sin(np.pi*t)/2
        self.xi=np.concatenate([a+(b-a)*q for a,b in zip(breaks[:-1],breaks[1:])])
        self.weights=np.concatenate([(b-a)*w*jac for a,b in zip(breaks[:-1],breaks[1:])])
        self.ba=outgoing_beta(self.ka,self.xi)
        self.bg=outgoing_beta(self.kg,self.xi)
        self.reflection=(self.bg-self.ba)/(self.bg+self.ba)

    @staticmethod
    def _side(points, soil):
        p=np.asarray(points,float)
        if p.ndim!=2 or p.shape[1]!=2 or not np.isfinite(p).all():
            raise ValueError('Points must be finite (N,2).')
        if np.any(p[:,1]>=0) if soil else np.any(p[:,1]<=0):
            raise ValueError('Buried points must be strictly below, and air points strictly above, y=0.')
        return p

    def transmitted_traces(self,soil,air,normals):
        soil,air=self._side(soil,True),self._side(air,False)
        normals=np.asarray(normals)
        if normals.shape!=soil.shape:
            raise ValueError('Normals must match soil points.')
        factor=1j/(2*np.pi)*self.weights/(self.ba+self.bg)
        field=np.zeros((len(soil),len(air)),complex)
        normal=field.copy()
        for sign in (-1,1):
            left=self.features(soil,self.bg,sign)
            right=self.features(air,self.ba,-sign)
            derivative=1j*(sign*self.xi[None,:]*normals[:,0,None]-self.bg[None,:]*normals[:,1,None])
            field+=(left*factor)@right.T
            normal+=(left*derivative*factor)@right.T
        return field,normal

    def reflected_blocks(self,points,normals,weights):
        """Return weighted S, source-normal D, target-normal K', mixed N."""
        points=self._side(points,True)
        normals=np.asarray(normals)
        if normals.shape!=points.shape or np.shape(weights)!=(len(points),):
            raise ValueError('One normal and arc weight per point is required.')
        factor=1j/(4*np.pi)*self.weights*self.reflection/self.bg
        blocks=[np.zeros((len(points),len(points)),complex) for _ in range(4)]
        for sign in (-1,1):
            left=self.features(points,self.bg,sign)
            right=self.features(points,self.bg,-sign)
            dt=1j*(sign*self.xi[None,:]*normals[:,0,None]-self.bg[None,:]*normals[:,1,None])
            ds=1j*(-sign*self.xi[None,:]*normals[:,0,None]-self.bg[None,:]*normals[:,1,None])
            blocks[0]+=(left*factor)@right.T
            blocks[1]+=(left*factor)@(right*ds).T
            blocks[2]+=(left*dt*factor)@right.T
            blocks[3]+=(left*dt*factor)@(right*ds).T
        return tuple(block*np.asarray(weights)[None,:] for block in blocks)


@dataclass
class BoundaryResult:
    scattered: np.ndarray  # receivers by sources; interface-only background excluded
    traces: np.ndarray
    residual: float
    seconds: float
    nodes: int
    spectral_nodes: int


def buried_scattering(curve,kair,ksoil,kobject,sources,receivers,*,order=64,cutoff=400.):
    """Solve one homogeneous buried smooth dielectric interface, air antennas."""
    started=perf_counter()
    layer=Sommerfeld(kair,ksoil,order,cutoff)
    layer._side(curve.points,True)
    layer._side(sources,False)
    layer._side(receivers,False)
    n=curve.num_nodes
    weights=curve.speeds*curve.parameter_step
    base=build_muller_system(curve,ksoil,kobject).system_matrix
    s,d,kp,h=layer.reflected_blocks(curve.points,curve.normals,weights)
    matrix=base+np.block([[-d,s],[-h,kp]])
    field,normal=layer.transmitted_traces(curve.points,sources,curve.normals)
    rhs=np.vstack((field,normal))
    traces=lu_solve(lu_factor(matrix),rhs)
    receiver_s,receiver_d=layer.transmitted_traces(curve.points,receivers,curve.normals)
    receiver=np.hstack((receiver_d.T*weights,-receiver_s.T*weights))
    return BoundaryResult(receiver@traces,traces,
        float(np.linalg.norm(matrix@traces-rhs)/np.linalg.norm(rhs)),
        perf_counter()-started,n,len(layer.xi))
