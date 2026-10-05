"""Independent heat-time circle eigenvalues for ON-003 reference checks only."""
import numpy as np
from scipy.special import ive, roots_legendre


def _scaled_i_and_derivative(modes,x):
    modes=np.asarray(modes); x=np.asarray(x)
    out=np.empty((len(modes),len(x)))
    derivative=np.empty_like(out)
    large=x>=1e6; small=~large
    m=modes[:,None]
    if np.any(small):
        xx=x[None,small]
        out[:,small]=ive(m,xx)
        derivative[:,small]=xx*(.5*(ive(m-1,xx)+ive(m+1,xx))-out[:,small])
    if np.any(large):
        xx=x[None,large]; mu=4*m*m
        term=np.ones((len(modes),int(np.sum(large))))
        series=term.copy(); ds=-.5*term
        # At x>=1e6 and |m|<=129, mu/(8x)<=0.0084.
        for p in range(1,9):
            term=term*(-(mu-(2*p-1)**2)/(8*xx*p))
            series+=term; ds-=(p+.5)*term
        base=1/np.sqrt(2*np.pi*xx)
        out[:,large]=base*series; derivative[:,large]=base*ds
    return out,derivative


def heat_circle(radius,k,tau,modes,order):
    """V,K,T near eigenvalues via heat time, independently of angular Kress.

    V=1/2 integral_0^tau exp(k^2 t) ive(n,a^2/(2t))/t dt.
    K=(a/2) d_a V. T is the matched linear Maue component, not a
    separately differentiated near hypersingular layer without heat forcing.
    The square substitution removes the t^-1/2 endpoint; scaled I_n prevents
    exponential overflow. Large-x asymptotics also differentiate analytically.
    """
    modes=np.asarray(modes)
    if np.max(np.abs(modes))>128 or order not in (256,512):
        raise ValueError("ON-003 circle reference caps are |n|<=128, orders 256/512")
    extended=np.unique(np.r_[modes-1,modes,modes+1])
    g,w=roots_legendre(order); u=(g+1)/2
    x=radius**2/(2*tau*u*u)
    I,xIp=_scaled_i_and_derivative(extended,x)
    weights=(w/2)*np.exp(k*k*tau*u*u)/u
    V=I@weights; K=xIp@weights
    centre=np.searchsorted(extended,modes)
    minus=np.searchsorted(extended,modes-1);plus=np.searchsorted(extended,modes+1)
    return np.array([V[centre],K[centre],-modes*modes*V[centre]+radius*radius*k*k/2*(V[minus]+V[plus])])
