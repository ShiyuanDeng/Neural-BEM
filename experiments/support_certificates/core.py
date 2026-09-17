"""Scalar volume scattering and a local-conservation Lagrange dual.

The finite model has binary contrast {0, chi}; no Born approximation is used.
The shared multipliers sum constraints across illuminations, a valid relaxation
of a common physical geometry. Bounds refer to this discrete model, not the
continuum without a separate modelling-error allowance.
"""
from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.special import hankel1


def green(k, targets, sources):
    r = np.linalg.norm(np.asarray(targets)[:, None] - np.asarray(sources)[None], axis=-1)
    return .25j * hankel1(0, k*r)


def volume_operator(k, points, cell_area):
    r = np.linalg.norm(points[:, None] - points[None], axis=-1)
    np.fill_diagonal(r, 1.)
    g = k*k*cell_area*.25j*hankel1(0, k*r)
    a = np.sqrt(cell_area/np.pi)
    np.fill_diagonal(g, .5j*np.pi*k*a*hankel1(1, k*a)-1.)
    return g


def scatter(g, e, mask, chi):
    p = np.zeros_like(e, dtype=complex)
    ids = np.flatnonzero(mask)
    if len(ids):
        p[ids] = np.linalg.solve(np.eye(len(ids))/chi-g[np.ix_(ids,ids)], e[ids])
    return p


@dataclass
class Dual:
    d: np.ndarray
    e: np.ndarray
    a: np.ndarray
    y: np.ndarray
    groups: np.ndarray = None

    def __post_init__(self):
        n = len(self.d)
        self.n = n
        self.h0 = self.a.conj().T@self.a
        self.b0 = self.a.conj().T@self.y
        self.c = float(np.linalg.norm(self.y)**2)
        weights=np.eye(n) if self.groups is None else np.asarray(self.groups,float)
        tensor = weights[:,:,None]*self.d[None,:,:]
        self.qi = np.concatenate(((tensor+tensor.conj().transpose(0,2,1))/2,
                                  (-1j*tensor+1j*tensor.conj().transpose(0,2,1))/2))
        bt=weights[:,:,None]*self.e[None,:,:]/2
        self.bi=np.concatenate((bt,-1j*bt))
        self.variables=len(self.qi)
        self.constants=np.zeros(self.variables)
        self.positive=np.array([],int)
        self.start_pattern=np.ones(self.variables//2)

    def evaluate(self, x, barrier=0., hessian=False):
        if len(self.positive) and np.any(x[self.positive]<=0):return None
        q = self.h0 + np.einsum('i,ijk->jk',x,self.qi)
        b = self.b0+np.einsum('i,ijk->jk',x,self.bi)
        try:
            cf = cho_factor(q,lower=True,check_finite=False)
        except np.linalg.LinAlgError:
            return None
        p = cho_solve(cf,b,check_finite=False)
        value = self.c+float(x@self.constants)-float(np.vdot(b,p).real)
        gradient = np.einsum('jk,ijk->i',p.conj(),np.einsum('ijk,kl->ijl',self.qi,p)-2*self.bi).real
        gradient+=self.constants
        logdet = float(2*np.log(np.diag(cf[0]).real).sum())
        if len(self.positive):logdet+=float(np.log(x[self.positive]).sum())
        inv = cho_solve(cf,np.eye(self.n),check_finite=False) if barrier else None
        if barrier:
            gradient += barrier*np.einsum('ij,kji->k',inv,self.qi).real
            gradient[self.positive]+=barrier/x[self.positive]
        out = dict(value=value, objective=value+barrier*logdet, gradient=gradient,
                   q=q,b=b,p=p,logdet=logdet)
        if hessian:
            v = self.bi-self.qi@p
            vi = cho_solve(cf,v.transpose(1,0,2).reshape(self.n,-1),check_finite=False)
            vi = vi.reshape(self.n,self.variables,-1).transpose(1,0,2)
            neg_h = 2*(v.reshape(self.variables,-1).conj()@vi.reshape(self.variables,-1).T).real
            if barrier:
                iq = inv@self.qi
                neg_h += barrier*(iq.reshape(self.variables,-1)@iq.transpose(0,2,1).reshape(self.variables,-1).T).real
                neg_h[self.positive,self.positive]+=barrier/x[self.positive]**2
            out['neg_hessian'] = (neg_h+neg_h.T)/2
        return out

    def solve(self, max_steps=45, barriers=(1e-2,1e-3,1e-4,1e-5,1e-6,1e-7)):
        start=perf_counter()
        candidates=[]
        if hasattr(self,'start_vectors'):
            starts=self.start_vectors
        else:
            starts=[np.r_[self.start_pattern*real*scale,self.start_pattern*imag*scale]
                    for real,imag in [(1.,0.),(-1.,0.),(0.,-1.),(1.,-1.),(-1.,-1.),(1.,-10.),(1.,-100.),(1.,-1000.)]
                    for scale in (1e-3,1e-2,.1,1.)]
        for x in starts:
            ev=self.evaluate(x)
            if ev is not None:candidates.append((ev['value'],x))
        if not candidates:
            return dict(success=False,reason='No positive-definite dual start found')
        _,x=max(candidates,key=lambda pair:pair[0])
        best=(-np.inf,None)
        history=[]
        for mu in barriers:
            for step in range(max_steps):
                ev=self.evaluate(x,mu,True)
                if ev['value']>best[0]:best=(ev['value'],x.copy())
                h=ev['neg_hessian']
                ridge=max(1e-14,1e-12*np.linalg.norm(h,ord=np.inf))
                direction=np.linalg.solve(h+ridge*np.eye(len(x)),ev['gradient'])
                ascent=float(ev['gradient']@direction)
                if ascent<max(1e-12,mu*1e-3):break
                alpha=1.
                for backtrack in range(65):
                    trial=self.evaluate(x+alpha*direction,mu)
                    if trial is not None and trial['objective']>=ev['objective']+1e-4*alpha*ascent:
                        break
                    alpha*=.5
                else:break
                x+=alpha*direction
            history.append(dict(barrier=mu,steps=step+1,bound=self.evaluate(x)['value']))
        ev=self.evaluate(x)
        if ev['value']>best[0]:best=(ev['value'],x.copy())
        x=best[1];ev=self.evaluate(x)
        eig=np.linalg.eigvalsh(ev['q'])
        # Residual-corrected numerical lower bound: completing the square gives
        # inf L >= L(p) - ||Qp-b||^2 / lambda_min(Q). The small eigenvalue margin
        # is a floating-point safeguard, not an interval-arithmetic proof.
        scale=float(eig[-1])
        margin=100*np.finfo(float).eps*self.n*scale
        mineig=float(eig[0]-margin)
        residual=ev['q']@ev['p']-ev['b']
        lp=self.c+x@self.constants+np.vdot(ev['p'],ev['q']@ev['p']).real-2*np.vdot(ev['p'],ev['b']).real
        correction=float(np.linalg.norm(residual)**2/mineig) if mineig>0 else np.inf
        lower=float(lp-correction-100*np.finfo(float).eps*(1+abs(lp)+self.c))
        return dict(success=mineig>0,bound=lower,raw_bound=float(ev['value']),
                    relative_residual_bound=float(np.sqrt(max(0.,lower)/self.c)),
                    minimum_eigenvalue=float(eig[0]),eigenvalue_margin=float(margin),
                    condition=float(eig[-1]/eig[0]),correction=correction,
                    seconds=perf_counter()-start,history=history,multipliers=x.tolist())


class SectorDual(Dual):
    """Allow independent real contrast in [lo,hi], including vacuum 0.

    The pointwise sector inequality |p|^2-(lo+hi)Re(p*E)+lo*hi|E|^2<=0
    and Im(p*E)=0 are necessary for all such materials. We sum over sources.
    This deliberately permits heterogeneous material and relaxed consistency
    between source fields, hence any exclusion is stronger evidence.
    """
    def __init__(self,g,e,a,y,lo,hi,groups=None):
        if not lo<=0<=hi or lo==hi:raise ValueError('Contrast interval must contain vacuum')
        self.g=g;self.lo=lo;self.hi=hi
        super().__init__(-g,e,a,y,groups)
        n=len(g);weights=np.eye(n) if groups is None else np.asarray(groups,float)
        sector=[];linear=[];constant=[]
        for w in weights:
            wg=w[:,None]*g;we=w[:,None]*e
            sector.append(np.diag(w)-(lo+hi)*(wg+wg.conj().T)/2+lo*hi*(g.conj().T@wg))
            linear.append((lo+hi)*we/2-lo*hi*(g.conj().T@we))
            constant.append(lo*hi*float(np.sum(w[:,None]*np.abs(e)**2)))
        m=len(weights)
        self.qi[:m]=np.array(sector);self.bi[:m]=np.array(linear)
        self.constants[:m]=constant
        self.positive=np.arange(m)


class CrossDual(Dual):
    """Enforce local cross-illumination identities for a common binary material."""
    def __init__(self,d,e,a,y,groups=None,diagonal_only=False):
        n,ns=e.shape
        weights=np.eye(n) if groups is None else np.asarray(groups,float)
        self.n=n*ns
        self.a=np.kron(a,np.eye(ns));self.y=y.reshape(-1,1)
        self.h0=self.a.conj().T@self.a;self.b0=self.a.conj().T@self.y
        self.c=float(np.linalg.norm(y)**2)
        qs=[];bs=[];pattern=[]
        for w in weights:
            for s in range(ns):
                for t in range(ns):
                    if diagonal_only and s!=t:continue
                    h=np.zeros((ns,ns));h[s,t]=1.
                    raw=np.kron(w[:,None]*d,h)
                    qs.append(raw)
                    bs.append((w[:,None]*(e@h.T)).reshape(-1,1)/2)
                    pattern.append(float(s==t))
        raw=np.array(qs);bt=np.array(bs)
        self.qi=np.concatenate(((raw+raw.conj().transpose(0,2,1))/2,(-1j*raw+1j*raw.conj().transpose(0,2,1))/2))
        self.bi=np.concatenate((bt,-1j*bt));self.variables=len(self.qi)
        self.constants=np.zeros(self.variables);self.positive=np.array([],int)
        self.start_pattern=np.array(pattern)


class CrossSectorDual(Dual):
    """Unknown common real contrast: source-sector and cross-Hermitian constraints.

    For real chi, P_i^* E_i is Hermitian, regardless of chi. For lo<=chi<=hi,
    the scalar sector constraint holds for every coherent superposition of
    illuminations. Fixed probe vectors restrict the dual search but keep bounds
    valid. All constraints are summed inside spatial groups.
    """
    def __init__(self,g,e,a,y,lo,hi,groups=None):
        if not lo<=0<=hi or lo==hi:raise ValueError('Interval must contain vacuum')
        n,ns=e.shape;weights=np.eye(n) if groups is None else np.asarray(groups,float)
        self.n=n*ns;self.a=np.kron(a,np.eye(ns));self.y=y.reshape(-1,1)
        self.h0=self.a.conj().T@self.a;self.b0=self.a.conj().T@self.y;self.c=float(np.linalg.norm(y)**2)
        unit=np.eye(ns,dtype=complex);probes=list(unit);hermitian=[np.diag(row) for row in unit]
        for s in range(ns):
            for t in range(s):
                for phase in (1.,-1.,1j,-1j):probes.append((unit[s]+phase*unit[t])/np.sqrt(2))
                h=np.zeros((ns,ns),complex);h[s,t]=h[t,s]=1.;hermitian.append(h)
                h=np.zeros((ns,ns),complex);h[s,t]=1j;h[t,s]=-1j;hermitian.append(h)
        qs=[];bs=[];cs=[]
        for w in weights:
            wg=w[:,None]*g;we=w[:,None]*e
            spatial=np.diag(w)-(lo+hi)*(wg+wg.conj().T)/2+lo*hi*g.conj().T@wg
            lin=(lo+hi)*we/2-lo*hi*g.conj().T@we
            for v in probes:
                h=np.outer(v.conj(),v)
                qs.append(np.kron(spatial,h));bs.append((lin@h.T).reshape(-1,1))
                cs.append(lo*hi*float(np.sum(w*np.abs(e@v)**2)))
        npos=len(qs)
        for w in weights:
            for hh in hermitian:
                h=1j*hh
                raw=np.kron(-w[:,None]*g,h)
                qs.append((raw+raw.conj().T)/2)
                bs.append((w[:,None]*(e@h.T)).reshape(-1,1)/2)
                cs.append(0.)
        self.qi=np.array(qs);self.bi=np.array(bs);self.constants=np.array(cs)
        self.variables=len(qs);self.positive=np.arange(npos)
        self.start_vectors=[np.r_[np.full(npos,scale),np.zeros(self.variables-npos)] for scale in (1e-4,1e-3,1e-2,.1,1.,10.)]
