from pathlib import Path
import json
import numpy as np
from scipy.special import hankel1,h1vp,jv,jvp
from scipy.optimize import least_squares

EPS0=8.8541878128e-12
MU0=1.25663706212e-6


def material(frequency,parameters):
    epsinf,delta,tau_ns,sigma=parameters
    omega=2*np.pi*np.asarray(frequency)
    return epsinf+delta/(1-1j*omega*tau_ns*1e-9)+1j*sigma/(EPS0*omega)


class CircleData:
    def __init__(self,frequencies,order=16):
        self.frequencies=np.asarray(frequencies);self.order=order
        self.modes=np.arange(-order,order+1)
        self.sources=np.c_[np.linspace(-.22,.22,8),np.zeros(8)]
        self.receivers=np.c_[np.linspace(-.22,.22,16),np.full(16,.005)]
        self.center=np.array([.01,-.16]);self.incident=[];self.receiver=[]
        self.k=2*np.pi*self.frequencies*np.sqrt(EPS0*MU0*6.)
        for ke in self.k:
            ds=self.sources-self.center;rs=np.linalg.norm(ds,axis=1);ts=np.arctan2(ds[:,1],ds[:,0])
            dr=self.receivers-self.center;rr=np.linalg.norm(dr,axis=1);tr=np.arctan2(dr[:,1],dr[:,0])
            self.incident.append(.25j*hankel1(self.modes[:,None],ke*rs)*np.exp(-1j*self.modes[:,None]*ts))
            self.receiver.append(hankel1(self.modes[None,:],ke*rr[:,None])*np.exp(1j*self.modes[None,:]*tr[:,None]))

    def predict(self,radius,parameters):
        eps=material(self.frequencies,parameters);rows=[]
        for i,(frequency,ke) in enumerate(zip(self.frequencies,self.k)):
            ki=2*np.pi*frequency*np.sqrt(EPS0*MU0*eps[i])
            je=jv(self.modes,ke*radius);ji=jv(self.modes,ki*radius)
            numerator=ki*jvp(self.modes,ki*radius)*je-ke*jvp(self.modes,ke*radius)*ji
            denominator=ke*h1vp(self.modes,ke*radius)*ji-ki*jvp(self.modes,ki*radius)*hankel1(self.modes,ke*radius)
            rows.append((self.receiver[i]*(numerator/denominator)[None,:])@self.incident[i])
        return np.array(rows)


def run():
    out=Path('results/experiments/passive_shape_20260916');out.mkdir(exist_ok=True,parents=True)
    frequencies=np.linspace(.3e9,1.5e9,31);model=CircleData(frequencies)
    hold=CircleData((frequencies[:-1]+frequencies[1:])/2)
    true=np.array([2.5,1.2,.15,.005]);records=[]
    for radius in (.003,.005,.01,.02,.03):
        other=radius*1.25;t=(radius/other)**2
        mapped=np.array([6+t*(true[0]-6),t*true[1],true[2],t*true[3]])
        y=model.predict(radius,true);norm=np.linalg.norm(y)
        def fun(q):
            res=(model.predict(other,q)-y).ravel()/norm
            return np.r_[res.real,res.imag]
        opt=least_squares(fun,mapped,bounds=([1.,0.,.001,0.],[12.,10.,10.,.1]),x_scale='jac',max_nfev=200,ftol=1e-11,gtol=1e-11,xtol=1e-11)
        htruth=hold.predict(radius,true)
        row=dict(radius_mm=radius*1000,alternative_radius_mm=other*1000,
                 constructive_passive_error=float(np.linalg.norm(fun(mapped))),
                 optimized_passive_error=float(np.linalg.norm(fun(opt.x))),
                 heldout_frequency_error=float(np.linalg.norm(hold.predict(other,opt.x)-htruth)/np.linalg.norm(htruth)),
                 true_material=true.tolist(),constructive_material=mapped.tolist(),fitted_material=opt.x.tolist(),
                 nfev=opt.nfev,success=bool(opt.success))
        records.append(row);print({k:row[k] for k in ('radius_mm','alternative_radius_mm','constructive_passive_error','optimized_passive_error','heldout_frequency_error')},flush=True)
        (out/'screen.json').write_text(json.dumps(dict(frequencies=frequencies.tolist(),records=records),indent=2))


if __name__=='__main__':run()
