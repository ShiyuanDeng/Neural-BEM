"""Score saved preparation snapshots and summarize measured resource use."""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
os.environ.setdefault('MPLCONFIGDIR','/tmp/csi-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.special import hankel1
from shapely.geometry import Point, Polygon
from experiments.baselines.csi.registered_metrics import score_field

REPO=Path(__file__).resolve().parents[3]
ACT=REPO/'docs/iterations/csi_adaptation/03_prepare_simulated_tg002_cases'


def resource_summary(run,summary,launch):
    rows=list(csv.DictReader((run/'resources.csv').open()))
    elapsed=np.array([float(r['elapsed_seconds']) for r in rows])
    cpu=np.array([float(r['cpu_seconds']) for r in rows])
    start=dt.datetime.fromisoformat(launch['started_utc']).timestamp()
    end=summary['native_end_posix']-start
    begin=end-summary['time_seconds']
    native_cpu=float(np.interp(end,elapsed,cpu)-np.interp(begin,elapsed,cpu))
    answer=dict(native_cpu_seconds=native_cpu,native_wall_seconds=summary['time_seconds'],
        native_equivalent_cores=native_cpu/summary['time_seconds'],
        total_cpu_seconds=float(cpu[-1]),total_wall_seconds=launch['wall_seconds'],
        peak_process_rss_GiB=max(float(r['rss_bytes']) for r in rows)/1024**3,
        minimum_available_GiB=min(float(r['available_bytes']) for r in rows)/1024**3,
        minimum_free_GiB=min(float(r['free_bytes']) for r in rows)/1024**3,
        native_window_elapsed_seconds=[begin,end],configured_threads=summary['threads'])
    if 'family_rss_bytes' in rows[0]:
        answer['peak_family_rss_GiB']=max(float(r['family_rss_bytes']) for r in rows)/1024**3
        use=[float(r['host_busy_cores']) for r,t in zip(rows,elapsed) if begin<=t<=end]
        answer['native_mean_host_busy_cores']=float(np.mean(use))
    overlap=run/'overlap.jsonl'
    if overlap.exists():
        checks=[json.loads(s) for s in overlap.read_text().splitlines()]
        answer['observed_matlab_job_counts']=sorted(set(c['matlab_count'] for c in checks))
    return answer


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['snapshots','probe']);args=parser.parse_args()
    run=REPO/f'results/csi/preparation/2026-11-17_{args.mode}'
    summary=json.loads((run/'matlab_summary.json').read_text())
    launch=json.loads((run/'launch.json').read_text());assert launch['returncode']==0
    data=loadmat(run/'final_contrast.mat',simplify_cells=True)
    shape=tuple(np.asarray(summary['Ninv'])[:2]);counts=np.atleast_1d(data['counts']).astype(int)
    snapshots=data['snapshots']
    if len(counts)==1:snapshots=[snapshots]
    if args.mode=='snapshots':truth=Point(0,.03).buffer(.015,quad_segs=4096)
    else:
        geo=loadmat(REPO/'results/csi/preparation/2026-11-17_geometry/geometry.mat',simplify_cells=True)
        boundary=geo['boundary'];truth=Polygon(np.column_stack([boundary.real,boundary.imag]))
    results=[];images=[]
    for count,values in zip(counts,snapshots):
        assert np.isfinite(values).all()
        scores,image=score_field(values,shape,data['grid_x_primary_m'],data['grid_y_primary_m'],truth)
        results.append(dict(iterations=int(count),scores=scores));images.append(image)
    final=results[-1]['scores'][0]
    for result in results:
        score=result['scores'][0]
        differences={key:abs(score[key]/final[key]-1) for key in ('area_mm2','mean_relative_permittivity','mean_susceptibility')}
        result['relative_difference_from_final']=differences
        # The benchmark contrast is epsilon_r, i.e. squared wavenumber ratio.
        result['within_one_percent']=differences['area_mm2']<=.01 and differences['mean_relative_permittivity']<=.01
    record=dict(mode=args.mode,protocol_version=1,raw_unmasked=True,truth_based_alignment=False,
        mean_contrast_definition='relative permittivity = 1 + susceptibility',snapshots=results,
        minimum_checked_iterations_within_one_percent=min(r['iterations'] for r in results if r['within_one_percent']),
        resources=resource_summary(run,summary,launch))
    if args.mode=='probe':
        full=loadmat(run/'full_history.mat',simplify_cells=True)
        calibrations=[];incident_errors=[]
        for fi,(frequency,omega) in enumerate(zip(np.atleast_1d(data['fre']),data['csi_pars']['omega'])):
            table=full['rawdat'][full['rawdat'][:,2]==frequency]
            t=table[:,0].reshape((49,36),order='F')*np.pi/180
            r=table[:,1].reshape((49,36),order='F')*np.pi/180
            incident=(table[:,5]+1j*table[:,6]).reshape((49,36),order='F')
            distance=np.hypot(.76*np.cos(r)-.72*np.cos(t),.76*np.sin(r)-.72*np.sin(t))
            k=2*np.pi*frequency*1e9/299792458.
            reference=1j*omega**2/4*hankel1(0,-k*distance[24])
            scale=incident[24]/reference
            for si,value in enumerate(scale):
                calibrations.append(dict(frequency_GHz=float(frequency),source_index=si+1,
                    real=float(value.real),imag=float(value.imag),expected=1/omega**2,
                    relative_error=float(abs(value*omega**2-1))))
            distances=np.hypot(data['grid_x_primary_m'][0]-.72*np.cos(t[0]),data['grid_y_primary_m'][0]-.72*np.sin(t[0]))
            expected_inc=1j/4*hankel1(0,-k*distances)
            actual_inc=full['Einc'][fi][0]
            incident_errors.append(float(np.max(np.abs(actual_inc-expected_inc))/np.max(np.abs(expected_inc))))
        with (run/'calibration.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(calibrations[0]));writer.writeheader();writer.writerows(calibrations)
        record['maximum_calibration_relative_error']=max(r['relative_error'] for r in calibrations)
        record['maximum_native_incident_relative_error']=max(incident_errors)
        assert record['maximum_calibration_relative_error']<1e-12
        assert record['maximum_native_incident_relative_error']<1e-12
    if args.mode=='snapshots':
        old=loadmat(REPO/'results/csi/fresnel/2026-11-17_diel_tm/final_contrast.mat',simplify_cells=True)
        # The last frequency's real susceptibility is shared by all frequencies.
        previous=old['chi1'][-1] if 'chi1' in old else old['chi'][0][-1]
        record['previous_final_max_absolute_difference']=float(np.max(np.abs(np.asarray(data['chi1'][-1])-np.asarray(previous))))
    (run/'scores.json').write_text(json.dumps(record,indent=2)+'\n')
    rows=[]
    for line in (run/'matlab.log').read_text().splitlines():
        if re.match(r'^\s+\d+\s+[-\d.]+e[+-]\d+',line):
            values=[float(x) for x in line.split()]
            rows.append(dict(iteration=int(values[0]),FS=values[1],FD=values[2],FC=values[3],reported_cost=values[4]))
    with (run/'cost_history.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    figures=ACT/'figures';figures.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,len(images),figsize=(3.1*len(images),3.3),squeeze=False)
    vmax=max(float(np.max(im)) for im in images)
    for ax,image,count in zip(axes[0],images,counts):
        im=ax.imshow(image,extent=[-100,100,-100,100],origin='upper',vmin=0,vmax=vmax,cmap='turbo')
        ax.contour(np.linspace(-100,100,image.shape[1]),np.linspace(100,-100,image.shape[0]),image,levels=[.5*np.max(image)],colors='white',linewidths=.6)
        bx,by=truth.exterior.xy;ax.plot(np.array(bx)*1000,np.array(by)*1000,'k--',lw=.8)
        limits=((-65,65),(-45,75)) if args.mode=='snapshots' else ((-105,105),(-105,105))
        ax.set(xlabel='numerical x (mm)',title=f'{count} iterations',xlim=limits[0],ylim=limits[1]);ax.set_aspect('equal')
    axes[0,0].set_ylabel('numerical y (mm)');fig.colorbar(im,ax=list(axes[0]),label='Re susceptibility',shrink=.7)
    fig.savefig(figures/f'{args.mode}_contrasts.png',dpi=140,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(5,3));ax.semilogy([r['iteration'] for r in rows],[r['reported_cost'] for r in rows]);ax.set(xlabel='iteration',ylabel='native reported cost');fig.tight_layout();fig.savefig(figures/f'{args.mode}_cost.png',dpi=140);plt.close(fig)
    print(json.dumps(dict(selected_iterations=record['minimum_checked_iterations_within_one_percent'],resources=record['resources']),indent=2))


if __name__=='__main__':main()
