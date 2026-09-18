"""Explicitly experimental transfer of the JWY2021 mask to the Muller system.

No scalar theorem is asserted for this coupled system. We compare identity-only,
the old full logarithmic protection, and extraction of the local principal
logarithmic coefficient in the T block. The latter has finite geometry bandwidth
and an exact Fourier symbol, unlike protecting every logarithmic amplitude.
"""
import numpy as np

from .scalar import literature_mask


def speed_squared_coefficients(z, dz=None):
    result = {}
    for j, v in z.items():
        for k, w in z.items():
            result[j-k] = result.get(j-k, 0)+j*k*v*np.conj(w)
    if dz is None:
        return result
    result = {}
    for first, second in ((dz,z),(z,dz)):
        for j,v in first.items():
            for k,w in second.items():
                result[j-k] = result.get(j-k,0)+j*k*v*np.conj(w)
    return result


def principal_log(case, dz=None):
    """Lower-left principal log kernel: (ko²-ki²) J(t)² L(t-s)/(8*pi).

    Signs follow A=[[I-DeltaK,DeltaV],[-DeltaT,I+DeltaKp]]. Here L is the
    canonical log(4 sin²/2), with zero constant mode. Its diagonal limit agrees
    with gpr_bem_kress.operators._diagonal_split_limits after flux row scaling.
    """
    modes = np.arange(-case.cutoff,case.cutoff+1)
    delta = modes[:,None]-modes[None,:]
    coeff = speed_squared_coefficients(case.geometry.coefficients,dz)
    toeplitz = np.zeros(delta.shape,complex)
    for d,v in coeff.items():
        toeplitz[delta==d] = v
    symbol = -1/np.maximum(np.abs(modes),1).astype(float)
    symbol[modes==0] = 0.
    part = ((case.ko**2-case.ki**2)*case.geometry.scale**2/4)*toeplitz*symbol[None,:]
    result = np.zeros_like(case.a)
    result[len(modes):,:len(modes)] = part
    return result


class SplitCase:
    def __init__(self,case,label):
        self.base,self.label=case,label
        self.leading=principal_log(case) if label=='PRINCIPAL_LOG' else None

    def __getattr__(self,name):
        return getattr(self.base,name)

    def parts(self,label=None):
        if self.label=='PRINCIPAL_LOG':
            return self.identity+self.leading,self.a-self.identity-self.leading
        return self.base.parts(self.label)

    def derivative(self,dz):
        result=self.base.derivative(dz)
        if self.label=='PRINCIPAL_LOG':
            result['principal_log']=principal_log(self,dz)
        return result

    def derivative_parts(self,derivative,label=None):
        if self.label=='PRINCIPAL_LOG':
            leading=derivative['principal_log']
            return leading,derivative['total']-leading
        return self.base.derivative_parts(derivative,self.label)


def mask_for(case,mu,mask_n=None):
    return np.tile(literature_mask(case.cutoff,mu,mask_n=mask_n),(2,2))


def storage(case,mask):
    # Count allocated/retained structural slots, never threshold values to claim
    # sparse storage. PRINCIPAL_LOG needs geometry coefficients plus symbol;
    # expanded-union slots are provided as a conservative comparison as well.
    size=2*case.cutoff+1
    support=np.eye(2*size,dtype=bool)
    if case.label=='VERIFIED_SINGULAR_SPLIT':
        return dict(retained=int(mask.sum()), candidate=int(mask.size),
                    stored_slots=int(mask.size+mask.sum()+2*size),
                    expanded_union_slots=int(mask.size), protected_kind='dense_log')
    if case.label=='PRINCIPAL_LOG':
        z=case.geometry.coefficients
        offsets={j-k for j in z for k in z if j and k}
        modes=np.arange(-case.cutoff,case.cutoff+1)
        support[size:,:size]=np.isin(modes[:,None]-modes[None,:],list(offsets)) & (modes[None,:]!=0)
        protected_slots=2*size+len(offsets)+size
    else:
        protected_slots=2*size
    return dict(retained=int(mask.sum()),candidate=int(mask.size),
                stored_slots=int(mask.sum()+protected_slots),
                expanded_union_slots=int((mask|support).sum()),protected_kind=case.label)
