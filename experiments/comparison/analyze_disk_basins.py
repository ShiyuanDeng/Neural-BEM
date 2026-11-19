"""Trace four-coordinate exact-disk descent and plot radius/material slices at the selected centres."""
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
import numpy as np

from bem_inverse import mie_localize as mie
from bem_inverse.io import curve_from, read, write
from experiments.comparison.compare_clean_schedules import OUT, write_rows
from experiments.comparison.localize_clean_real_disks import DIR, MM, CUT, PARAMS, folded, observation, refine, residual
from experiments.comparison.trace_slider_refusals import ACTIVITY


def loss(obs, p):
    v = residual(obs, [*p[:3], np.log(p[3])])
    return .5*(v@v)


def local_derivatives(obs, p):
    # Equal units in the three spatial directions (one package unit = 50 mm), plus log material.
    x = np.r_[np.array(p[:3])/MM, np.log(p[3])]
    def fun(t):
        v = residual(obs, np.r_[t[:3]*MM,t[3]])
        return .5*(v@v)
    def derivative(fn, t, step):
        offsets = np.eye(len(t))*step
        return np.array([(fn(t+d)-fn(t-d))/(2*step) for d in offsets]).T
    def gradient(t):
        return derivative(fun,t,1e-5)
    h = derivative(gradient,x,8e-5)
    return dict(grad_inf=float(np.max(abs(gradient(x)))), eigenvalues=np.linalg.eigvalsh((h+h.T)/2))


def main():
    with (DIR/'joint_scores.csv').open() as stream:
        results = [r for r in csv.DictReader(stream) if r['case'].endswith('__c13.3') and not r['case'].startswith('circle')]
    profiles, basins, curvature = [], [], []
    rgrid = np.unique(np.r_[np.arange(3.,121.,.6), 145.])
    qgrid = np.geomspace(.02,100.,241)
    rm, qm = np.meshgrid(rgrid,qgrid)
    targets = read(DIR/'joint_minima.json')
    fig, axes = plt.subplots(3,3, figsize=(12.6,10.2), sharex=True, sharey=True, layout='constrained')
    fields = []
    k0 = observation(results[0]['case']).wavenumber
    radial = mie.radial_coefficients(k0,qm.reshape(-1,1),rm.ravel()/MM,np.arange(CUT+1))
    for s,ax in zip(results,axes.flat):
        case = s['case']
        o = observation(case)
        c = read(OUT/'warmup'/(case+'.json'))
        q = c['start_contrast']
        stage = c['stages'][0]
        coeff = curve_from(stage['curve']).coefficients
        warm = [coeff[4].real*MM,coeff[4].imag*MM,abs(coeff[5])*MM,stage['contrast']]
        best = [float(s[k]) for k in PARAMS]
        truth = [float(s[k]) for k in ('true_x_mm','true_y_mm','true_radius_mm','true_contrast')]
        seeds = dict(selected=best, weak=[0,0,65,q], mirrored=[0,0,65,2-q], warmup_exit=warm)
        # Resolve the basin of the selected grid solution on the same wider domain as the actual starts.
        best_local = refine(o,best,wide=True)
        for source,p in seeds.items():
            if p[-1] <= 0:
                basins.append(dict(case=case, source=source, admissible=False, start=p))
                continue
            end = refine(o,p,wide=True)
            params = [end[k] for k in PARAMS]
            location_difference = np.linalg.norm(np.array(params[:2])-[best_local[k] for k in PARAMS[:2]])
            same = (location_difference<.25 and abs(params[2]-best_local['radius_mm'])<.25 and
                    abs(np.log(params[3]/best_local['contrast']))<.01)
            basins.append(dict(case=case,source=source,admissible=True,start=p,start_loss=loss(o,p),
                               same_as_selected=same, result=end, ending_near_limit=bool(
                                   params[2]<1.01 or params[2]>199.99 or params[3]<1.1e-10 or params[3]>999.9)))
        d=local_derivatives(o,warm)
        verified=loss(o,warm)
        assert abs(verified-stage['final_loss'])<1e-7
        curvature.append(dict(case=case,source='warmup_exit',parameters=warm,loss=verified,**d))
        # Truth is used only to compare the diagnostic choice to an equal-area disk, after selection.
        background_loss = loss(o,[*best[:3],1.])
        assert abs(background_loss-.5)<1e-12
        truth_cost = loss(o,truth)
        truth_local = refine(o,truth)
        same_disk_loss = mie.landscape([o],best[3],[complex(*best[:2])/MM],[best[2]/MM],cutoff=CUT)[0,0]
        assert abs(same_disk_loss-float(s['loss'])) < 1e-10
        other = [v for v in targets if v['case']==case and
                 (abs(v['radius_mm']-best[2])>2 or abs(np.log(v['contrast']/best[3]))>.1 or
                  abs(complex(v['x_mm']-best[0],v['y_mm']-best[1]))>2)]
        competitor = min(other,key=lambda v:v['loss']) if other else None
        profiles.append(dict(case=case,loss_at_equal_area_true_material=truth_cost,truth_seed_check=truth_local,
                             background_loss=background_loss, weak_start_loss=stage['initial_loss'],
                             warmup_exit_loss=stage['final_loss'],
                             nearest_competing_loss=None if competitor is None else competitor['loss'],
                             competitor=competitor, reprojection_loss=same_disk_loss))
        assert o.wavenumber == k0
        prod=folded(o,np.array([complex(*best[:2])/MM]))[0]
        field=.5*np.sum(abs(radial@prod.T-o.scattered)**2,axis=1).reshape(rm.shape)/np.linalg.norm(o.scattered)**2
        fields.append(field.astype(np.float32))
        im=ax.pcolormesh(rgrid,qgrid,field,norm=LogNorm(1e-5,2),cmap='BrBG_r',shading='auto',rasterized=True)
        ax.contour(rgrid,qgrid,field,levels=[.001,.01,.1,.25,.5,1.],linewidths=.45,colors='#524e4a',alpha=.65)
        for name,marker,col in [('weak','s','#1f2840'),('mirrored','+','#244d9c'),('warmup_exit','v','#e94e18'),
                                ('selected','o','#161616'),('truth','*','#161616')]:
            p = truth if name=='truth' else seeds[name]
            if p[3]>0:
                ax.plot(p[2],max(.024,p[3]),marker=marker,mec=col,mew=1.2,mfc='white' if name in ('truth','selected') else col,
                        ls='',ms=9 if name=='truth' else 6)
        ax.set(title=case.split('__')[0].replace('_',' '),yscale='log',xlim=(3,120),ylim=(.02,100))
        ax.tick_params(labelsize=8)
    for ax in axes[-1]: ax.set_xlabel('Radius (mm)')
    for ax in axes[:,0]: ax.set_ylabel('Stored contrast')
    handles=[Line2D([],[],ls='',marker=m,mec=c,mfc=fill,ms=8,label=l) for m,c,fill,l in [
        ('s','#1f2840','#1f2840','Weak start'),('+','#244d9c','#244d9c','Mirror (when positive)'),
        ('v','#e94e18','#e94e18','Warm-up exit'),('o','black','white','Selected disk'),('*','black','white','Equal-area truth')]]
    fig.legend(handles=handles,loc='outside lower center',ncol=5,frameon=False)
    fig.colorbar(im,ax=axes,label='B5 loss at selected centre',shrink=.7)
    fig.savefig(ACTIVITY/'figures/nine_disk_basins.png',dpi=160)
    plt.close(fig)
    np.savez_compressed(DIR/'disk_slices.npz',loss=fields,radius_mm=rgrid,contrast=qgrid,
                        cases=[r['case'] for r in results],
                        centers_mm=[[float(r['x_mm']),float(r['y_mm'])] for r in results])
    write(DIR/'basin_descents.json',basins)
    write(DIR/'disk_checks.json',profiles)
    write(DIR/'warmup_curvature.json',curvature)
    rows=[]
    for b in basins:
        e = b.get('result',{})
        rows.append(dict(case=b['case'],source=b['source'],admissible=b['admissible'],
                         start_loss=b.get('start_loss'),same_basin=b.get('same_as_selected'),
                         end_x_mm=e.get('x_mm'),end_y_mm=e.get('y_mm'),end_radius_mm=e.get('radius_mm'),
                         end_contrast=e.get('contrast'),end_loss=e.get('loss'),status=e.get('status'),
                         nfev=e.get('nfev'),near_limit=b.get('ending_near_limit')))
    write_rows(DIR/'basin_descents.csv',rows)
    plot_replays()


def plot_replays():
    fig, axes = plt.subplots(2,4, figsize=(11,5.1), layout='constrained')
    for col, shape in enumerate(['star','c_shape','aphex_twin','hook']):
        for arm, color, label in [('reference','#15775c','Default bounds'),('log_x4','#b64d28','4× log step'),
                                  ('shape_x4','#644e86','4× shape step')]:
            receipt = read(DIR/'warmup_replays'/f'{shape}__c13.3_{arm}.json')
            h = receipt['history']
            for row, field in enumerate(['loss','contrast']):
                ax = axes[row,col]
                ax.plot([t['iteration'] for t in h],[t[field] for t in h],color=color,label=label,lw=1.45)
                ax.plot(h[-1]['iteration'],h[-1][field],marker='o',ms=3,color=color)
        axes[0,col].set_title(shape.replace('_',' ')+(' (mirrored)' if shape=='hook' else ''))
        axes[1,col].set(xlabel='Accepted step',yscale='log')
        axes[0,col].set_yscale('log' if shape=='aphex_twin' else 'linear')
    axes[0,0].set_ylabel('B5 loss')
    axes[1,0].set_ylabel('Stored contrast')
    fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=3,frameon=False)
    fig.savefig(ACTIVITY/'figures/band_one_bounds.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':
    main()
