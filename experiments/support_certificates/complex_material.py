"""Real QCQP for common, unknown complex materials in a permittivity box."""
import numpy as np
from .core import Dual


def real_quadratic(q,b):
    return np.block([[q.real,-q.imag],[q.imag,q.real]]),np.concatenate((b.real,b.imag))


class ComplexMaterialDual(Dual):
    def __init__(self,g,e,a,y,background,real_bounds,imag_bounds,groups,cross=True):
        n,ns=e.shape;nc=n*ns;weights=np.asarray(groups,float)
        aa=np.kron(a,np.eye(ns));yy=y.reshape(-1,1)
        self.a=np.block([[aa.real,-aa.imag],[aa.imag,aa.real]])
        self.y=np.concatenate((yy.real,yy.imag));self.n=2*nc
        self.h0=self.a.T@self.a;self.b0=self.a.T@self.y;self.c=float(np.linalg.norm(y)**2)
        emin,emax=real_bounds;imin,imax=imag_bounds
        center=((emin+emax)/2+1j*(imin+imax)/2)/background-1
        radius=np.hypot((emax-emin)/2,(imax-imin)/2)/abs(background)
        alpha=abs(center)**2-radius**2
        unit=np.eye(ns,dtype=complex);probes=list(unit)
        for s in range(ns):
            for t in range(s):
                for phase in (1.,-1.,1j,-1j):probes.append((unit[s]+phase*unit[t])/np.sqrt(2))
        qs=[];bs=[];cs=[];disk_indices=[]
        for w in weights:
            wg=w[:,None]*g;we=w[:,None]*e;gwg=g.conj().T@wg;gwe=g.conj().T@we
            ee=float(np.sum(w[:,None]*abs(e)**2))
            sector=np.diag(w)-center*wg-center.conjugate()*wg.conj().T+alpha*gwg
            linear=center*we-alpha*gwe
            for v in probes:
                hh=np.outer(v.conj(),v);q,b=real_quadratic(np.kron(sector,hh),(linear@hh.T).reshape(-1,1))
                disk_indices.append(len(qs));qs.append(q);bs.append(b);cs.append(alpha*float(np.sum(w*abs(e@v)**2)))
            for t,bound,sign in [(1.,emin,-1.),(1.,emax,1.),(-1j,imin,-1.),(-1j,imax,1.)]:
                z=t*background;gamma=z.real-bound
                raw=z*wg.conj().T
                qlocal=sign*(gamma*gwg+(raw+raw.conj().T)/2)
                blocal=-sign*(gamma*gwe+.5*z.conjugate()*we)
                for v in probes:
                    hh=np.outer(v.conj(),v);q,b=real_quadratic(np.kron(qlocal,hh),(blocal@hh.T).reshape(-1,1))
                    qs.append(q);bs.append(b);cs.append(sign*gamma*float(np.sum(w*abs(e@v)**2)))
        positive_count=len(qs)
        if cross:
            for w in weights:
                for s in range(ns):
                    for t in range(s):
                        h=np.zeros((ns,ns));h[s,t]=1.;h[t,s]=-1.
                        raw=np.kron(w[:,None]*g,h);k=(raw+raw.T)/2
                        ell=(w[:,None]*(e@h.T)).reshape(-1,1)
                        qs.append(np.block([[k.real,-k.imag],[-k.imag,-k.real]]))
                        bs.append(-.5*np.concatenate((ell.real,-ell.imag)));cs.append(0.)
                        qs.append(np.block([[k.imag,k.real],[k.real,-k.imag]]))
                        bs.append(-.5*np.concatenate((ell.imag,ell.real)));cs.append(0.)
        self.qi=np.array(qs);self.bi=np.array(bs);self.constants=np.array(cs);self.variables=len(qs)
        self.positive=np.arange(positive_count);self.start_vectors=[]
        for scale in (1e-4,1e-3,.01,.1,1.):
            x=np.zeros(self.variables);x[self.positive]=scale*1e-5;x[disk_indices]=scale
            self.start_vectors.append(x)
