import json, numpy as np, sys, time
sys.path[:0]=['solvers','.']
from pathlib import Path
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.forward import PointSourceAcquisition, solve
import run_radial_fourier_topology_inverse as base
import run_fourier_topology_controller as driver
from sdf_inverse.explicit_fourier import CartesianFourierCurveState

B=Path('results/validation/topology/TOP-025-compiled-20260917-115641')
h=json.load(open(B/'runs/merge/handoff.json'))
state=driver.deserialize_state(h['state'])
comp=state.components[0]
print(type(comp).__name__, comp.maximum_mode)
L=0.05; C=0.5+0.5j
cos=comp.cosine_coefficients[:,0]+1j*comp.cosine_coefficients[:,1]
sin=comp.sine_coefficients[:,0]+1j*comp.sine_coefficients[:,1]
K=len(cos)-1
c=np.zeros(2*K+1,complex); c[K]=cos[0]; c[K+1:]=(cos[1:]-1j*sin[1:])/2; c[:K]=((cos[1:]+1j*sin[1:])/2)[::-1]
phys=FourierCurve(c)
# check against SPD parameterization points
pts=comp.parameterization().discretize(256).points
z=phys.values(256)
print('param match', np.max(np.abs(z-(pts[:,0]+1j*pts[:,1]))))
c2=c/L; c2[K]=(c[K]-C)/L
shape=FourierCurve(c2)
src,rec=base._ring_scan()
o=np.array([.5,.5])
acq=PointSourceAcquisition((src-o)/L,(rec-o)/L,base.SOURCE_STRENGTH)
pred=json.load(open(B/'runs/merge/F/initial_endpoint_predictions.json'))
print(pred.keys())
freqs=pred['frequencies_hz']
cfg=base.cfg
for n in ('256','512'):
    P=np.array(pred['predictions'][n]['real'])+1j*np.array(pred['predictions'][n]['imag'])
    for j,f in enumerate(freqs):
        k=2*np.pi*f*np.sqrt(cfg.MU0*cfg.EPS0*cfg.SAND_EPSR)*L
        t=time.time(); q=solve(shape,k,cfg.PLASTIC_EPSR/cfg.SAND_EPSR,acq,int(n)).prediction; t=time.time()-t
        print(n,f,'rel diff',np.linalg.norm(q-P[:,j])/np.linalg.norm(P[:,j]), f'{t:.2f}s')
