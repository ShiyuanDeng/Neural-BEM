"""Score a BRG endpoint by importing the frozen comparison protocol."""
from pathlib import Path
import sys,time,json,os
from types import SimpleNamespace
import numpy as np
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'solvers'),str(ROOT),str(Path.home()/'Gau-Gal/src')]
from bem_inverse.io import write,read,curve_record,portable
from bem_inverse.continuation.geometry import FourierCurve
from experiments.comparison import scoring as Q
from experiments.gaugal_comparison import tg002_data as D
BASE=ROOT/'results/brg/tg002_no_curvature/2026-11-18'
DOC=ROOT/'docs/iterations/brg_adaptation/05_run_brg_without_curvature_limit'
ROW=os.environ.get('BRG_TG002_ROW','control')
RUN_LABEL='brg/provisional_tg002_no_curvature_known'
if ROW=='shipped':
    BASE=ROOT/'results/brg/tg002_shapes/2026-11-17'
    DOC=ROOT/'docs/iterations/brg_adaptation/04_run_brg_on_tg002_shapes'
    RUN_LABEL='brg/provisional_tg002_known'


def score_case(case):
    started=time.monotonic();out=BASE/case;eta=float(case.split('__c')[1]);s=read(out/'summary.json') if (out/'summary.json').exists() else {'frequencies':[],'status':'failed'}
    rows=s['frequencies'];rows=[rows] if isinstance(rows,dict) else rows
    curve=None; image=np.zeros((201,201))
    if rows:
        final=loadmat(out/f"frequency_{rows[-1]['index']:03d}.mat",simplify_cells=True)['record']
        z=np.asarray(final['xs'])+1j*np.asarray(final['ys']);assert np.isfinite(z).all()
        coefficients=np.fft.fftshift(np.fft.fft(z)/len(z))
        if len(z)%2==0:
            coefficients=np.r_[coefficients,coefficients[0]/2];coefficients[0]/=2
        curve=FourierCurve(coefficients*(.065/.05))
        assert np.max(abs(curve.values(len(z) if len(z)%2 else 2*len(z))[::1 if len(z)%2 else 2]*.05/.065-z))<1e-10
        image=(eta-1)*D.fill_fraction(.05*curve.values(max(4096,2*curve.band+2)),*D.pixel_grid(201))
    fit=dict(representation='curve',final_curve=None if curve is None else portable(curve_record(curve)),contrast=eta,
             data_status='provisional BRG forward; frozen BEM-side data pending')
    result=Q.score(SimpleNamespace(key=RUN_LABEL,noise=None),case,fit,dict(image=image),ROOT)
    residuals=read(out/'final_residuals.json') if (out/'final_residuals.json').exists() else []
    data=read(out/'data_summary.json') if (out/'data_summary.json').exists() else []
    attempts=[read(p) for p in sorted(out.glob('attempt_*.json'))]
    result.update(status=s['status'],data_status=fit['data_status'],completed_frequencies=len(rows),
        final_k=rows[-1]['k'] if rows else None,last_continuation_residual=rows[-1]['residual'] if rows else None,
        final_curve_residuals=[r['relative_residual'] for r in residuals],
        max_final_curve_residual=max((r['relative_residual'] for r in residuals),default=None),
        residual_over_limit=max((r['relative_residual']/.003 for r in residuals),default=None),
        curvature='shipped' if ROW=='shipped' else 'default; eps_curv unset',
        data_seconds=sum(r['wall_seconds'] for r in data) if ROW=='shipped' else 0.0,
        reused_data_generation_seconds=sum(r['wall_seconds'] for r in data),inverse_seconds=sum(r['wall_seconds'] for r in rows),
        residual_check_seconds=sum(r['wall_seconds'] for r in residuals),matlab_process_seconds=sum(a.get('wall_seconds',0) for a in attempts),
        scoring_seconds=time.monotonic()-started,iterations=sum(r['iterations'] for r in rows),
        geometry_resampling_max_error=max((r.get('geometry_check',{}).get('max_point_error',0) for r in data),default=0))
    write(out/'fit.json',fit);write(out/'metrics.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _,truth,_=Q.truth_for(case);fig,ax=plt.subplots(figsize=(5,5))
    for p in Q.polygons(truth): ax.plot(*np.asarray(p.exterior.coords).T*1000,'k-',label='True TG-002 shape')
    if curve is not None:
        z=.05*curve.values(4096)*1000;ax.plot(z.real,z.imag,'r--',label='BRG endpoint')
    t=np.arange(300)*2*np.pi/300;ax.plot(65*np.cos(t),65*np.sin(t),':',color='.6',label='Start')
    ax.set(aspect='equal',xlabel='x relative to scene centre (mm)',ylabel='y (mm)',title=case+' — provisional')
    ax.legend(fontsize=7);fig.tight_layout();(DOC/'figures').mkdir(exist_ok=True)
    fig.savefig(DOC/'figures'/f'{case}.png',dpi=120);plt.close(fig)
    result['scoring_seconds']=time.monotonic()-started;write(out/'metrics.json',result)
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);a=p.parse_args();r=score_case(a.case)
    print(json.dumps({k:r[k] for k in ['case','status','area_error','max_final_curve_residual','data_seconds','inverse_seconds','residual_check_seconds','scoring_seconds']}))
