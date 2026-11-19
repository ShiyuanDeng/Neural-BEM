"""Exact-disk TG-002 circle schedule maps, CPU only, no optimizer fits."""
import os
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[name]='1'
os.environ['SC_FORWARD_BACKEND']='cpu'
os.environ.setdefault('MPLCONFIGDIR','/tmp/tg_circle_mpl')
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT)]
import json
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from scipy.special import jv,jvp,hankel1,h1vp
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from shapely.geometry import Polygon
from bem_inverse import FourierCurve
from bem_inverse.io import read,curve_from,digest
from bem_inverse.physics import Execution
from experiments.benchmark import campaign,scenes
from experiments.comparison import bem
from experiments.comparison.check_stage_stops import BASE
from experiments.comparison.runs import RESULTS

OUT=RESULTS/'bem/stage_scheduling/2026-11-19/circle_loss_maps'
DOC=ROOT/'docs/iterations/investigate_bem_stage_scheduling/02_compare_clean_failures_and_passes'
MM=.001/scenes.LENGTH

class Disk:
    def __init__(self,obs,centre,max_radius=80):
        self.obs=obs;self.k=obs.wavenumber
        self.n=np.arange(-int(self.k*max_radius*MM+40),int(self.k*max_radius*MM+40)+1)[:,None]
        a=obs.acquisition
        assert a.paired and a.mask is None
        zs=a.sources[:,0]+1j*a.sources[:,1]-centre
        zr=a.receivers[:,0]+1j*a.receivers[:,1]-centre
        self.basis=(.25j*a.strength*hankel1(self.n,self.k*abs(zs)[None])*np.exp(-1j*self.n*np.angle(zs)[None])*
                    hankel1(self.n,self.k*abs(zr)[None])*np.exp(1j*self.n*np.angle(zr)[None]))
    def predict(self,r,eps):
        a=r*MM;ki=self.k*np.sqrt(np.atleast_1d(eps))[None,:];n=self.n
        t=-(self.k*jvp(n,self.k*a)*jv(n,ki*a)-ki*jv(n,self.k*a)*jvp(n,ki*a))/(self.k*h1vp(n,self.k*a)*jv(n,ki*a)-ki*hankel1(n,self.k*a)*jvp(n,ki*a))
        t[abs(n[:,0])>int(self.k*a+40),:]=0
        return t.T@self.basis
    def loss(self,r,eps):
        residual=self.predict(r,eps)-self.obs.scattered
        return .5*np.sum(abs(residual)**2,axis=1)/np.linalg.norm(self.obs.scattered)**2

def curve_point(record):
    curve=curve_from(record);z=curve.values(16384);poly=Polygon(np.c_[z.real,z.imag]);repaired=not poly.is_valid
    if repaired:poly=poly.buffer(0)
    return dict(radius_mm=float(np.sqrt(poly.area/np.pi)/MM),centre_units=[poly.centroid.x,poly.centroid.y],area_repaired=repaired)

def stage_points(fit):
    return [dict(**curve_point(s['curve']),permittivity=s['contrast'],stage=s['stage'],saved_loss=s['final_loss'],accepted_steps=s['accepted_steps']) for s in fit['stages']]

def validate(real,truth):
    physics,forward=campaign._physics('modal_muller',Execution('cpu',1))
    circles=[(65.,1.6409664029853395,0j),(50.,13.3,truth),(70.,1.6,truth)]
    checks=[]
    for r,e,c in circles:
        curve=FourierCurve.circle(r*MM,c);nodes=physics.resolution_profile(curve.band)['production'];errors=[]
        for obs in real:
            exact=Disk(obs,c).predict(r,e)[0]
            prediction=np.asarray(forward(curve,obs,e,nodes).prediction).reshape(-1)
            errors.append(float(np.linalg.norm(exact-prediction)/np.linalg.norm(prediction)))
        checks.append(dict(radius_mm=r,permittivity=e,centre_units=[c.real,c.imag],max_relative_forward_error=max(errors),per_frequency_relative_error=errors))
        print('check',r,e,max(errors),flush=True)
    if hasattr(physics,'close'):physics.close()
    assert max(c['max_relative_forward_error'] for c in checks)<1e-8,checks
    return checks

def main():
    OUT.mkdir(parents=True,exist_ok=True);(DOC/'figures').mkdir(exist_ok=True)
    cases=['circle__c4','circle__c13.3'];loaded={}
    for case in cases:
        row=campaign.row(case);real,_=bem.observations(BASE,row,RESULTS)
        truth=curve_from(read(ROOT/row['truth']));centre=truth.coefficients[truth.band]
        original=read(BASE.folder()/case/'fit.json')
        warm_path=OUT.parent/'clean_tg002/warmup'/f'{case}.json'
        warm=read(warm_path) if warm_path.exists() else None
        loaded[case]=(row,real,truth,centre,original,warm)
    _,real,truth,centre,original,_=loaded[cases[-1]]
    checks=validate(real,centre)
    sets=[dict(label='warmup_025_real',frequencies_hz=[.25e9])]
    seen=set()
    for event in original['decisions']:
        if event['reason']=='resolved stage entered':
            op=event['operation'];fs=op['stage']['frequencies_hz'];key=tuple(fs)
            if key not in seen:sets.append(dict(label=op['label'],frequencies_hz=fs));seen.add(key)
    radii=np.unique(np.r_[np.linspace(2,80,157),50,65])
    eps=np.unique(np.concatenate([np.geomspace(1.02,40,181),[4,13.3],[loaded[c][4]['contrast_start']['start_contrast'] for c in cases]]))
    all_records={};fig,axes=plt.subplots(2,len(sets),figsize=(22,8),sharex=True,sharey=True,layout='constrained')
    for row_i,(case,(row,real,truth,centre,original,warm)) in enumerate(loaded.items()):
        models=[Disk(o,centre) for o in real]
        indices=[[i for i,o in enumerate(real) if o.frequency_hz in s['frequencies_hz']] for s in sets]
        archive=OUT/f'{case}.npz'
        if '--reuse-grid' in sys.argv and archive.exists():
            a=np.load(archive);radii=a['radius_mm'];eps=a['permittivity'];grids=a['loss']
        else:
            def frequency_grid(model):return np.array([model.loss(r,eps) for r in radii])
            with ThreadPoolExecutor(max_workers=4) as pool:per=np.array(list(pool.map(frequency_grid,models)))
            grids=np.array([per[idx].mean(axis=0) for idx in indices])
            np.savez_compressed(archive,radius_mm=radii,permittivity=eps,loss=grids.astype(np.float32))
        paths={'default':stage_points(original)}
        if warm:paths['warm-up']=stage_points(warm)
        start=dict(**curve_point(read(ROOT/row['initial'])),permittivity=original['contrast_start']['start_contrast'])
        points={'start':start,'truth':dict(radius_mm=50.,permittivity=row['contrast'],centre_units=[centre.real,centre.imag]),'default first exit':paths['default'][0],'default final':paths['default'][-1]}
        if warm:points['warm-up exit']=paths['warm-up'][0]
        for p in points.values():
            actual=[Disk(o,complex(*p['centre_units'])).loss(p['radius_mm'],p['permittivity'])[0] for o in real]
            fixed=[m.loss(p['radius_mm'],p['permittivity'])[0] for m in models]
            p['exact_circle_loss_at_actual_centre']=[float(np.mean(np.array(actual)[idx])) for idx in indices]
            p['exact_circle_loss_at_map_centre']=[float(np.mean(np.array(fixed)[idx])) for idx in indices]
        valley=[]
        for e in [1.05,1.2,1.5,1.64,2,4,8,13.3,20,30,40]:
            losses=np.array([models[0].loss(r,e)[0] for r in radii]);i=losses.argmin()
            fit=minimize_scalar(lambda r:models[0].loss(r,e)[0],bounds=(radii[max(0,i-1)],radii[min(len(radii)-1,i+1)]),method='bounded')
            valley.append(dict(permittivity=e,radius_mm=fit.x,loss=fit.fun))
        radius_samples=[]
        for r in [40.,50.,59.3641751281,65.,75.]:
            sample_eps=np.geomspace(1.02,40,1201)
            sample_loss=models[0].loss(r,sample_eps);i=sample_loss.argmin()
            opt=minimize_scalar(lambda e:models[0].loss(r,e)[0],bounds=(sample_eps[max(0,i-1)],sample_eps[min(len(sample_eps)-1,i+1)]),method='bounded')
            losses=[m.loss(r,opt.x)[0] for m in models]
            radius_samples.append(dict(radius_mm=r,permittivity=opt.x,loss_by_frequency_set=[float(np.mean(np.array(losses)[idx])) for idx in indices]))
        all_records[case]=dict(valley_radius_samples=radius_samples,input_sha256=digest(ROOT/row['data']),truth_sha256=digest(ROOT/row['truth']),map_centre_units=[centre.real,centre.imag],sets=sets,points=points,paths=paths,valley_025GHz=valley,warmup_available=warm is not None)
        for ax,s,g in zip(axes[row_i],sets,grids):
            image=ax.pcolormesh(radii,eps,g.T,shading='auto',cmap='magma',norm=LogNorm(1e-6,2),rasterized=True)
            ax.contour(radii,eps,g.T,levels=[1e-4,.001,.01,.05,.1,.25,.5],colors='grey',linewidths=.45)
            for (label,pts),color in zip(paths.items(),['#00aaff','#00cc88']):
                ax.plot([start['radius_mm']]+[p['radius_mm'] for p in pts],[start['permittivity']]+[p['permittivity'] for p in pts],'.-',color=color,lw=1.2,ms=4,label=label)
            ax.plot(65,start['permittivity'],'s',color='deepskyblue',ms=6,label='start')
            ax.plot(50,row['contrast'],'*',color='lime',ms=10,label='truth')
            fs=np.array(s['frequencies_hz'])/1e9
            title='0.25 GHz' if len(fs)==1 and fs[0]==.25 else ('all 19: 0.25–2.5 GHz' if len(fs)==19 else ', '.join(f'{f:g}' for f in fs)+' GHz')
            if row_i==0:ax.set_title(title,fontsize=9)
            ax.set(yscale='log',xlim=(2,80),ylim=(1.02,40))
            if row_i==1:ax.set_xlabel('Equivalent radius (mm)')
        axes[row_i,0].set_ylabel(f'{case}\nStored contrast (permittivity)')
        axes[row_i,-1].legend(fontsize=7)
        print('finished',case,'warmup',warm is not None,flush=True)
    fig.colorbar(image,ax=axes,label='Half mean squared relative residual',shrink=.85)
    fig.suptitle('TG-002 exact-circle losses at the truth centre; stage paths project changing centres and noncircular shapes',fontsize=12)
    fig.savefig(DOC/'figures/tg002_circle_loss_maps.png',dpi=150);plt.close(fig)
    record=dict(forward_checks=checks,scaling='Each active frequency divided by its data norm, equal weights; half mean squared relative residual.',cpu_threads=4,cases=all_records,limits='Maps fix the truth centre; paths project area-equivalent radius and stored contrast. Marker losses do not equal actual noncircular fit losses.')
    (OUT/'summary.json').write_text(json.dumps(record,indent=2)+'\n')

if __name__=='__main__':main()
