"""Two-dimensional TMz two-half-space Green function for a numerical screen.

e^{-i omega t}, outgoing H1, common mu. Air is z>0, soil z<0.
Horizontal Fourier matching gives beta=sqrt(k^2-xi^2), Im(beta)>=0,
R_soil=(beta_soil-beta_air)/(beta_soil+beta_air). Transmission has
i/(2 pi) integral over R of exp(i xi dx+i beta_air a+i beta_soil h)
divided by beta_air+beta_soil. No antenna pattern or rough ground is modeled.
"""
import numpy as np
from numpy.polynomial.legendre import leggauss
from .core import green,volume_operator


class Layered:
    def __init__(self,kair,ksoil,order=96,cutoff=600.):
        self.ka=complex(kair);self.kg=complex(ksoil)
        t,w=leggauss(order);t=(t+1)/2;w=w/2
        ka=float(kair.real);kg=max(float(ksoil.real),ka+1.)
        # Square maps resolve the air branch point from either side.
        xs=[ka*(1-t*t),ka+(kg-ka)*t*t,kg+kg*t,2*kg+(cutoff-2*kg)*t]
        ws=[w*2*ka*t,w*2*(kg-ka)*t,w*kg,w*(cutoff-2*kg)]
        self.xi=np.concatenate(xs);self.weights=np.concatenate(ws)
        self.ba=np.sqrt(self.ka**2-self.xi**2+0j)
        self.bg=np.sqrt(self.kg**2-self.xi**2+0j)
        self.reflection=(self.bg-self.ba)/(self.bg+self.ba)

    def features(self,points,wave,sign):
        return np.exp(1j*sign*np.asarray(points)[:,0,None]*self.xi+1j*np.abs(np.asarray(points)[:,1,None])*wave)

    def transmitted(self,soil,air):
        factor=1j/(2*np.pi)*self.weights/(self.ba+self.bg)
        return ((self.features(soil,self.bg,1)*factor)@self.features(air,self.ba,-1).T
                +(self.features(soil,self.bg,-1)*factor)@self.features(air,self.ba,1).T)

    def reflected(self,targets,sources):
        factor=1j/(4*np.pi)*self.weights*self.reflection/self.bg
        return ((self.features(targets,self.bg,1)*factor)@self.features(sources,self.bg,-1).T
                +(self.features(targets,self.bg,-1)*factor)@self.features(sources,self.bg,1).T)

    def matrices(self,points,area,sources,receivers):
        g=volume_operator(self.kg,points,area)+self.kg**2*area*self.reflected(points,points)
        e=self.transmitted(points,sources)
        a=self.kg**2*area*self.transmitted(points,receivers).T
        return g,e,a
