"""Matched cold/warm pose inverses, scattering-order convergence, and object reuse."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from time import perf_counter
import numpy as np
import scipy
from scipy.spatial import cKDTree
from experiments.bie002_modal_diagnostic.fixtures import inputs
from .coefficient_operator import LaurentGeometry
from .scattering_library import PoseChart
from .pose_inverse import PoseEvaluator,invert_pose
from .run_inverse import save,relative


FREQUENCIES=[.5e9,1.25e9]


def fixture(count=2):
    acq,_=inputs()
    shapes=[LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0),
            LaurentGeometry.star(radius=.028,amplitude=.12,lobes=3,rotation=0)]
    if count==2:
        anchors=[.44+.49j,.56+.51j]
    elif count==4:
        anchors=[.415+.42j,.585+.42j,.415+.585j,.585+.585j]
    else:
        anchors=[complex(x,y) for y in [.405,.5,.595] for x in [.405,.5,.595]]
    chart=PoseChart([shapes[i%2] for i in range(len(anchors))],anchors)
    base=np.array([[.5,-.4,.3],[-.4,.3,-.25],[.2,.5,-.18],[-.3,-.4,.22]])
    truth=np.vstack([base[i%4] for i in range(len(anchors))]).reshape(-1)
    return acq,chart,truth,np.zeros(chart.size)


def chart_record(chart):
    return dict(anchors=[[z.real,z.imag] for z in chart.anchors],
                templates=[dict(scale=g.scale,coefficients=[[j,complex(v).real,complex(v).imag] for j,v in g.coefficients.items()])
                           for g in chart.geometries])


def boundary(g):
    theta=np.arange(2048)*2*np.pi/2048
    z=g.center+g.scale*sum(v*np.exp(1j*j*theta) for j,v in g.coefficients.items())
    return np.c_[z.real,z.imag]


def metrics(chart,x,truth,acq,observed,clean):
    centers,angles=chart.poses(x);tc,ta=chart.poses(truth)
    components=[]
    for g,tg,center,target,angle,rotation in zip(chart.moved(x),chart.moved(truth),centers,tc,angles,ta):
        a,b=boundary(g),boundary(tg)
        components.append(dict(center_error_mm=float(1000*abs(center-target)),angle_error_degrees=float(abs(angle-rotation)*180/np.pi),
            boundary_rms_mm=float(1000*np.sqrt(np.mean(np.sum((a-b)**2,axis=1)))),
            boundary_hausdorff_mm=float(1000*max(cKDTree(a).query(b)[0].max(),cKDTree(b).query(a)[0].max()))))
    y=PoseEvaluator(chart,acq,FREQUENCIES,backend='nodal_rebuild',nodes=256).forward(x)
    held=dict(acq);angle=.073
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    for key in ['source_points','receiver_points']:
        held[key]=((np.array(acq[key])-.5)@rotation.T+.5).tolist()
    yt=PoseEvaluator(chart,held,[.875e9],backend='nodal_rebuild',nodes=256).forward(truth)
    yh=PoseEvaluator(chart,held,[.875e9],backend='nodal_rebuild',nodes=256).forward(x)
    return dict(components=components,boundary_rms_mm=float(np.sqrt(np.mean([c['boundary_rms_mm']**2 for c in components]))),
        maximum_center_error_mm=max(c['center_error_mm'] for c in components),
        maximum_angle_error_degrees=max(c['angle_error_degrees'] for c in components),
        observed_data_error=relative(y,observed),clean_data_error=relative(y,clean),held_out_error=relative(yh,yt))


def qualification(output):
    acq,chart,x,_=fixture()
    ref=PoseEvaluator(chart,acq,FREQUENCIES,backend='nodal_rebuild',nodes=256)
    y=ref.forward(x);j=ref.jacobian(x);rows=[]
    for order in [4,6,8,10,12,14]:
        e=PoseEvaluator(chart,acq,FREQUENCIES,order=order)
        actual=e.forward(x);jac=e.jacobian(x)
        rows.append(dict(order=order,data_error=relative(actual,y),jacobian_error=relative(jac,j),
            worst_column_error=float(np.max(np.linalg.norm(jac-j,axis=(0,1))/np.linalg.norm(j,axis=(0,1)))),
            work=e.work,online_unknowns=len(e.states[0].matrix),online_boundary_unknowns=0,
            condition_number=max(float(np.linalg.cond(s.matrix)) for s in e.states)))
    save(output/'order_convergence.json',rows)
    print('order convergence',json.dumps(rows),flush=True)


def many_objects(output):
    acq,chart,x,_=fixture(9)
    reference=PoseEvaluator(chart,acq,[1.25e9],backend='nodal_rebuild',nodes=128).forward(x)
    refined=PoseEvaluator(chart,acq,[1.25e9],backend='nodal_rebuild',nodes=192).forward(x)
    rows=[]
    for backend in ['library_native','library_nodal','nodal_rebuild']:
        measured=[];cold=[]
        for repeat in range(3):
            tick=perf_counter();e=PoseEvaluator(chart,acq,[1.25e9],backend=backend,order=14)
            actual=e.forward(x);cold.append(perf_counter()-tick)
            # A genuinely different pose uses the already-compiled templates.
            changed=x.copy();changed[0]+=.01
            tick=perf_counter();e.forward(changed);measured.append(perf_counter()-tick)
        rows.append(dict(backend=backend,cold_forward_seconds=float(np.median(cold)),
            reused_forward_seconds=float(np.median(measured)),data_error=relative(actual,reference),
            oracle_128_192_error=relative(reference,refined),work=e.work,components=9,
            online_unknowns=(9*29 if backend.startswith('library_') else 9*128),
            reference_boundary_unknowns=9*256))
    save(output/'nine_objects.json',rows)
    print('nine objects',json.dumps(rows),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('results/experiments/modal_muller_20260916/scattering_library'))
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=True)
    qualification(output);many_objects(output);summary=[]
    for case_index,case in enumerate(['pair_clean','pair_noise1pct','four_noise1pct']):
        acq,chart,truth,initial=fixture(4 if case.startswith('four') else 2)
        clean=PoseEvaluator(chart,acq,FREQUENCIES,backend='nodal_rebuild',nodes=256).forward(truth)
        fine=PoseEvaluator(chart,acq,FREQUENCIES,backend='nodal_rebuild',nodes=384).forward(truth)
        noise=0. if case.endswith('clean') else .01
        rng=np.random.default_rng(20261101+case_index)
        perturbation=rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
        perturbation*=noise*np.linalg.norm(clean,axis=1)[:,None]/np.linalg.norm(perturbation,axis=1)[:,None]
        observed=clean+perturbation
        save(output/(case+'_inputs.json'),dict(acquisition=acq,chart=chart_record(chart),truth=truth.tolist(),initial=initial.tolist(),
            frequencies=FREQUENCIES,noise_fraction=noise,noise_seed=20261101+case_index,oracle_256_384_error=relative(clean,fine),
            observed_real=observed.real.tolist(),observed_imag=observed.imag.tolist(),clean_real=clean.real.tolist(),clean_imag=clean.imag.tolist()))
        warm={b:PoseEvaluator(chart,acq,FREQUENCIES,backend=b) for b in ['library_native','library_nodal']}
        arms=['native_rebuild','nodal_rebuild','library_native_cold','library_native_warm','library_nodal_cold','library_nodal_warm']
        for repeat in range(args.repeats):
            for arm in arms if repeat%2==0 else list(reversed(arms)):
                if arm.endswith('_warm'):
                    backend=arm.removesuffix('_warm')
                    result=invert_pose(chart,acq,FREQUENCIES,observed,initial,evaluator=warm[backend])
                else:
                    backend=arm.removesuffix('_cold')
                    result=invert_pose(chart,acq,FREQUENCIES,observed,initial,backend=backend)
                tick=perf_counter()
                result['metrics']=metrics(chart,np.array(result['parameters']),truth,acq,observed,clean)
                result['validation_seconds']=perf_counter()-tick
                result.update(case=case,arm=arm,repeat=repeat)
                save(output/f'{case}_{arm}_{repeat}.json',result)
                before=result['work_before']
                row=dict(case=case,arm=arm,repeat=repeat,seconds=result['seconds'],success=result['success'],
                    nfev=result['nfev'],njev=result['njev'],compilation_seconds=result['work']['compilation_seconds'],
                    compilation_included=not arm.endswith('_warm'),compiled_templates=result['work']['compiled_templates'],
                    forward_seconds=result['work']['forward_seconds']-before['forward_seconds'],
                    jacobian_seconds=result['work']['jacobian_seconds']-before['jacobian_seconds'],**result['metrics'])
                summary.append(row);save(output/'summary.json',summary)
                print('pose inverse',json.dumps(row),flush=True)
    paths=list(Path('experiments/modal_muller_research').glob('*.py'))
    paths.extend(Path('solvers/gpr_bem_kress').glob('*.py'))
    save(output/'manifest.json',dict(arguments=vars(args)|{'output':str(output)},
        python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
        thread_environment={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        timing_scope='Cold inverse includes template compilation; warm inverse reuses fixed shape/material/frequency templates. '
                     'All trial forward solves and derivatives included; independent observations and validation excluded.'))


if __name__=='__main__':
    main()
