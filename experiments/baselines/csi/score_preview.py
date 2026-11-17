"""Fresnel preview using frozen protocol-1 support and region scoring imports."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/csi-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.io import loadmat
from shapely.geometry import Point

from experiments.comparison import scoring as G


def main():
    parser=argparse.ArgumentParser(__doc__); parser.add_argument('run',type=Path)
    args=parser.parse_args(); run=args.run
    data=loadmat(run/'final_contrast.mat',simplify_cells=True)
    launch=json.loads((run/'launch.json').read_text())
    repo=Path(__file__).resolve().parents[3]
    figures=repo/launch['activity']/'figures'
    true=Point(-.03,0).buffer(.015,quad_segs=4096)
    truth=dict(radius_mm=15,centroid_mm=[-30,0],relative_permittivity=3,
               relative_permittivity_uncertainty=.3,susceptibility=2,
               source='Belkebir and Saillard (2001), section 4.2, Figure 6(a), Figure 7, Table 1',
               url='https://doi.org/10.1088/0266-5611/17/6/301',
               frame='declared before inversion: rightward x/upward y of the paper drawing; no post-fit alignment',
               numerical_frame_alignment_verified=False,
               warning='The database drawing does not label numerical axes. Drawing-frame area_error and centroid_mm are not verified physical recovery errors.')
    n=G.PROTOCOL['grid_cells']; h=G.PROTOCOL['grid_half_width_m']
    x=np.linspace(-h,h,n); y=x[::-1]; xx,yy=np.meshgrid(x,y)
    shape=tuple(int(z) for z in data['csi_pars']['Ninv'][:2])
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    records=[]
    for index,name in enumerate(['MF-CC-CSI','MF-MR-CSI','CSI'],1):
        contrasts=data[f'chi{index}']; raw=np.asarray(contrasts[-1]).real.reshape(shape,order='F')
        real_spread=max(float(np.max(np.abs(np.asarray(c).real-np.asarray(contrasts[-1]).real))) for c in contrasts)
        interpolator=RegularGridInterpolator((data['grid_x_primary_m'],data['grid_y_primary_m']),raw,
                                             method='linear',bounds_error=False,fill_value=0.)
        image=interpolator(np.column_stack([xx.ravel(),yy.ravel()])).reshape(n,n)
        entries=[]; chosen=None
        for fraction in [.5,.3,.7]:
            rings,peak=G.support_rings(image,fraction)
            found,repaired=G.region(rings)
            inside=np.sign(peak)*image>=fraction*abs(peak) if peak else np.zeros_like(image,dtype=bool)
            mean=float(image[inside].mean()) if inside.any() else None
            entry=dict(fraction=fraction,image_peak=peak,**G.region_scores(found,true),
                       centroid_xy_mm=None if found.is_empty else [found.centroid.x*1000,found.centroid.y*1000],
                       mean_susceptibility=mean,mean_relative_permittivity=None if mean is None else 1+mean,
                       mean_susceptibility_relative_error=None if mean is None else mean/2-1,
                       mean_relative_permittivity_relative_error=None if mean is None else (1+mean)/3-1,
                       ring_repaired=repaired)
            entry['centroid_radius_mm']=None if found.is_empty else float(np.hypot(found.centroid.x,found.centroid.y)*1000)
            entry['area_relative_difference']=entry['area_mm2']/entry['true_area_mm2']-1
            entry['unregistered_drawing_frame_metrics']={key:entry.pop(key) for key in
                ('area_error','missing_area','excess_area','centroid_mm')}
            entries.append(entry)
            if fraction==.5: chosen=rings
        records.append(dict(method=name,real_spread_across_frequencies=real_spread,scores=entries))
        ax=axes[index-1]
        panel=ax.imshow(image,extent=[-h*1000,h*1000,-h*1000,h*1000],origin='upper',cmap='jet')
        for ring in chosen: ax.plot(ring.real*1000,ring.imag*1000,color='white',lw=.8)
        t=np.linspace(0,2*np.pi,512); ax.plot(-30+15*np.cos(t),15*np.sin(t),'k--',lw=1)
        ax.set(title=name,xlabel='Numerical x / mm',ylabel='Numerical y / mm',xlim=(-70,70),ylim=(-70,70))
        fig.colorbar(panel,ax=ax,shrink=.8)
    fig.suptitle('dielTM_dec8f: raw real contrast; white = protocol-1 support\nDashed = unregistered paper-drawing reference; no post-fit alignment')
    fig.savefig(figures/'diel_tm_support_preview.png',dpi=140)
    output=dict(protocol=G.PROTOCOL,truth=truth,methods=records,
                adapter='raw unmasked Re(chi), physical x/y, linear resampling to frozen 201x201 +/-100 mm grid; zero outside native domain',
                api_limit='Full score() is TG-002-specific; imports support_rings, region and region_scores without edits.')
    (run/'score_preview.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(records,indent=2))


if __name__=='__main__': main()
