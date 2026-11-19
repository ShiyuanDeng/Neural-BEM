"""CPU-only exact-circle loss maps; no inverse fit is started or changed."""
from csi_runtime import ROOT, provenance  # pins BLAS to one thread
import json
import sys
from pathlib import Path
import numpy as np
from scipy.special import jv, jvp, hankel1, h1vp
from scipy.optimize import minimize, minimize_scalar
from scipy.ndimage import minimum_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import csi_cylinder_info as C
from bem_inverse.io import curve_from

BASE = ROOT/'results/bem/baseline_data/csi_adapter/2026-11-18'
OUT = ROOT/'results/bem/baseline_data/measured_schedule/2026-11-19/analysis'
DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/11_test_measured_cylinder_schedule'

class CircleLoss:
    """Cache the exact series waves at one centre, contract loss in modal space."""
    def __init__(self, obs, centre):
        self.k = obs.wavenumber
        self.n = np.arange(-int(self.k*70*C.MM+40), int(self.k*70*C.MM+40)+1)[:,None]
        acq=obs.acquisition
        c=complex(*centre)*C.MM
        zs=acq.sources[:,0]+1j*acq.sources[:,1]-c
        zr=acq.receivers[:,0]+1j*acq.receivers[:,1]-c
        incoming=.25j*hankel1(self.n,self.k*abs(zs)[None])*np.exp(-1j*self.n*np.angle(zs)[None])
        outgoing=hankel1(self.n,self.k*abs(zr)[None])*np.exp(1j*self.n*np.angle(zr)[None])
        basis=(incoming[:,:,None]*outgoing[:,None,:])[:,acq.mask]/np.linalg.norm(obs.scattered)
        self.scale=np.linalg.norm(basis,axis=1)
        basis=basis/self.scale[:,None]
        self.gram=basis.conj()@basis.T
        self.cross=basis.conj()@(obs.scattered/np.linalg.norm(obs.scattered))
    def __call__(self,r,eps):
        eps=np.atleast_1d(eps)
        a=r*C.MM; ki=self.k*np.sqrt(eps)[None,:];n=self.n
        t=-((self.k*jvp(n,self.k*a)*jv(n,ki*a)-ki*jv(n,self.k*a)*jvp(n,ki*a))/
            (self.k*h1vp(n,self.k*a)*jv(n,ki*a)-ki*hankel1(n,self.k*a)*jvp(n,ki*a)))
        t[abs(n[:,0])>int(self.k*a+40),:]=0
        z=t*self.scale[:,None]
        return .5*(np.einsum('ne,nm,me->e',z.conj(),self.gram,z).real-2*np.einsum('ne,n->e',z.conj(),self.cross).real+1)

def paths():
    from shapely.geometry import Polygon
    sources={'saved':BASE/'first_fit/dielTM_dec8f/cuda/attempt_01/fit.json'}
    schedule=OUT.parent
    sources.update({'stopped warm-up':schedule/'warmup/dielTM_dec8f/cuda/attempt_01/local/fit_result.json',
                    'warm-up':schedule/'warmup/dielTM_dec8f/cuda/attempt_02/fit.json',
                    'first cap':schedule/'first_cap/dielTM_dec8f/cuda/attempt_01/fit.json'})
    result={}
    for label,p in sources.items():
        if not p.exists():
            if label!='stopped warm-up':continue
            files=list(p.parent.glob('*.json'));stages=[]
            for f in files:
                j=json.loads(f.read_text())
                if isinstance(j,dict) and 'accepted_steps' in j and 'curve' in j:stages.append(j)
            stages.sort(key=lambda s: (0 if s['stage'].startswith('warmup') else 1,s['stage']))
        else:stages=json.loads(p.read_text())['stages']
        points=[]
        for s in stages:
            z=curve_from(s['curve']).values(16384)*C.D.LENGTH_M*1000
            poly=Polygon(np.c_[z.real,z.imag]); repaired=not poly.is_valid
            if repaired:poly=poly.buffer(0)
            points.append(dict(stage=s['stage'],radius_mm=float(np.sqrt(poly.area/np.pi)),
                               permittivity=s['contrast'],centre_mm=[poly.centroid.x,poly.centroid.y],
                               area_repaired=repaired))
        result[label]=points
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True);(DOC/'figures').mkdir(exist_ok=True)
    info=json.loads((BASE/'cylinder_info/cylinder_info.json').read_text())
    real,_,source=C.D.observations(C.D.MEASURED)
    best=info['least_squares']['from_bem_fit']['end'];centre=[best['x_mm'],best['y_mm']]
    models=[CircleLoss(o,centre) for o in real]
    checks={}
    for label,p in [('nominal',info['nominal']['params']),('bem_equivalent_circle',info['bem_fit']['params']),('best_circle',best)]:
        values=list(p.values()); direct=C.loss(C.per_frequency(real,values))
        cached=float(np.mean([CircleLoss(o,values[:2])(values[2],values[3])[0] for o in real]))
        assert abs(cached-direct)<1e-10,(label,cached,direct)
        checks[label]=dict(exact_circle_loss=direct,cached_loss=cached)
    checks['saved_non_circular_bem_loss']=info['bem_fit']['loss']
    radii=np.unique(np.r_[np.linspace(2,70,181),best['radius_mm'],15,19.0453338612])
    eps=np.unique(np.r_[np.geomspace(1.05,40,161),2,3,31,best['permittivity'],2.1937311771])
    counts=[1,2,3,4,8]
    if '--reuse-grid' in sys.argv:
        saved=np.load(OUT/'circle_loss_grid.npz')
        radii=saved['radius_mm'];eps=saved['permittivity'];grids=saved['loss']
    else:
        per=np.empty((8,len(radii),len(eps)))
        for f,model in enumerate(models):
            for i,r in enumerate(radii):per[f,i]=model(r,eps)
            print(f'finished {f+1} GHz',flush=True)
        grids=np.array([per[:n].mean(axis=0) for n in counts])
        np.savez_compressed(OUT/'circle_loss_grid.npz',radius_mm=radii,permittivity=eps,frequency_counts=counts,loss=grids)
    valley=[]
    for e in [2.,31.]:
        vals=np.array([models[0](r,e)[0] for r in radii]);i=int(vals.argmin())
        fit=minimize_scalar(lambda r:models[0](r,e)[0],bounds=(radii[max(0,i-1)],radii[min(len(radii)-1,i+1)]),method='bounded')
        valley.append(dict(permittivity=e,contrast_minus_one=e-1,radius_mm=fit.x,loss=fit.fun))
    minima=[]
    for n,g in zip(counts,grids):
        idx=np.unravel_index(g.argmin(),g.shape)
        local=np.argwhere((g==minimum_filter(g,size=3)) & (g<.12))
        refined=minimize(lambda p:float(np.mean([m(*p)[0] for m in models[:n]])),[radii[idx[0]],eps[idx[1]]],method='L-BFGS-B',bounds=[(2,70),(1.05,40)])
        profile=g.min(axis=1);near=radii[profile<g.min()+.005]
        minima.append(dict(refined_main_minimum=dict(radius_mm=float(refined.x[0]),permittivity=float(refined.x[1]),loss=float(refined.fun)),radius_range_within_0005=[float(near.min()),float(near.max())],frequencies_ghz=list(range(1,n+1)),grid_best=dict(radius_mm=radii[idx[0]],permittivity=eps[idx[1]],loss=g[idx]),
                           local_minima_below_012=[dict(radius_mm=radii[i],permittivity=eps[j],loss=g[i,j]) for i,j in local if 0<i<len(radii)-1 and 0<j<len(eps)-1]))
    endpoint=[info['bem_fit']['params']['radius_mm'],info['bem_fit']['params']['permittivity']]
    def full(p):return float(np.mean([m(*p)[0] for m in models]))
    h=[.01,.001];grad=[(full(np.array(endpoint)+np.eye(2)[i]*h[i])-full(np.array(endpoint)-np.eye(2)[i]*h[i]))/(2*h[i]) for i in range(2)]
    descent=minimize(full,endpoint,method='L-BFGS-B',bounds=[(2,70),(1.05,40)])
    record=dict(provenance=provenance(),input=source,centre_mm=centre,checks=checks,
                material_note='The stored contrast is relative permittivity: interior wavenumber is exterior times sqrt(contrast). No +1 conversion.',
                valley_1GHz=valley,minima=minima,endpoint_at_map_centre=dict(radius_mm=endpoint[0],permittivity=endpoint[1],loss=full(endpoint),gradient_per_mm_and_permittivity=grad,
                local_descent_end=descent.x.tolist(),local_descent_loss=descent.fun),paths=paths(),
                limits='All maps fix centre at the best exact-circle centre. Stage markers use area-equivalent radius; their centres and noncircular shapes vary. Thus marker height is not the saved stage loss.')
    (OUT/'circle_loss_summary.json').write_text(json.dumps(record,indent=2)+'\n')
    fig,axes=plt.subplots(1,5,figsize=(19,4.6),sharex=True,sharey=True,layout='constrained')
    colors=['#0072b2','#00bbbb','#00a020','#cc00aa']
    for ax,n,g in zip(axes,counts,grids):
        im=ax.pcolormesh(radii,eps,g.T,norm=LogNorm(.035,2),cmap='magma',shading='auto',rasterized=True)
        ax.contour(radii,eps,g.T,levels=[.04,.06,.08,.1,.15,.25,.5],colors='grey',linewidths=.5)
        for (label,pts),color in zip(record['paths'].items(),colors):
            ax.plot([65]+[p['radius_mm'] for p in pts],[1.0931033143341842]+[p['permittivity'] for p in pts],'.-',color=color,lw=1,label=label)
        for r,e,marker,color,label in [(65,1.0931033143341842,'s','black','start'),(15,3,'+','deepskyblue','nominal'),(best['radius_mm'],best['permittivity'],'*','lime','best circle')]:
            ax.plot(r,e,marker,color=color,ms=9,label=label)
        ax.set(title='1 GHz' if n==1 else f'1–{n} GHz',xlabel='Equivalent radius (mm)',yscale='log',xlim=(2,70),ylim=(1.05,40))
    axes[0].set_ylabel('Relative permittivity');axes[-1].legend(fontsize=7,loc='upper right')
    fig.colorbar(im,ax=axes,label='Half mean squared relative residual',shrink=.8)
    fig.suptitle('Measured cylinder: exact-circle loss at fixed best-circle centre\nPaths show stage exit area and material; centres and noncircular shapes vary',fontsize=11)
    fig.savefig(DOC/'figures/circle_loss_map.png',dpi=160);plt.close(fig)
    print(json.dumps({k:record[k] for k in ['checks','valley_1GHz','minima','endpoint_at_map_centre']},indent=2))

if __name__=='__main__':main()
