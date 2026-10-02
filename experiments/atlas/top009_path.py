"""Finite physical-angle path audit for the failed local TOP-009 explanation."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import CubicSpline
from .top009_projection import SAVED,SPEC,driver,benchmark,component_parameterization
from .run_jacobian_spectrum import solve,jacobian,NormalBasis,write_json,execution,PeriodicParameterization2D


def path_curves(reference,targets):
    producers=[]; velocities=[]
    for p,q in zip(reference,targets):
        t=np.linspace(0,2*np.pi,8192,endpoint=False)
        v,w=p.evaluate(t),q.evaluate(t)
        origin,destination=v.points.mean(axis=0),w.points.mean(axis=0)
        polar=w.points-destination
        angle=np.mod(np.arctan2(polar[:,1],polar[:,0]),2*np.pi);order=np.argsort(angle)
        angle=angle[order]; radius=np.linalg.norm(polar[order],axis=1)
        interp=CubicSpline(np.r_[angle,angle[0]+2*np.pi],np.r_[radius,radius[0]],bc_type='periodic')
        base=v.points-origin
        phi=np.mod(np.arctan2(base[:,1],base[:,0])-angle[0],2*np.pi)+angle[0]
        mapped=destination+interp(phi)[:,None]*np.column_stack((np.cos(phi),np.sin(phi)))
        delta=mapped-v.points
        velocity=CubicSpline(np.r_[t,2*np.pi],np.concatenate((delta,delta[:1])),bc_type='periodic')
        velocities.append(velocity)
    def at(alpha):
        result=[]
        for p,d in zip(reference,velocities):
            def evaluate(t,p=p,d=d):
                b=p.evaluate(t)
                return tuple(getattr(b,key)+alpha*d(t,order) for order,key in enumerate(
                    ('points','first_derivatives','second_derivatives','third_derivatives')))
            result.append(PeriodicParameterization2D(p.component_id,evaluate))
        return tuple(result)
    return at


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):raise FileExistsError('Use a fresh output.')
    args.output.mkdir(parents=True,exist_ok=True)
    saved,spec=json.loads(SAVED.read_text()),json.loads(SPEC.read_text())
    scene=next(s for s in spec['scenes'] if s['id']==saved['scene'])
    state=driver.deserialize_state(saved['final_state'])
    ref=tuple(component_parameterization(c) for c in state.components)
    truth_by_id={c.component_id:c for c in benchmark.truth_curves(scene)}
    matches={r['recovered_component']:r['truth_component'] for r in saved['final_geometry']['matched_components']}
    truth=tuple(truth_by_id[matches[c.component_id]] for c in state.components)
    problem=driver.baseline._problem(np.array(spec['training_frequencies_hz']),acquisition=spec.get('acquisition'))
    options=dict(epsr=problem.interior.epsr,exterior_epsr=problem.exterior.epsr,sources=problem.source_points,
                 receivers=problem.receiver_points,strength=complex(np.asarray(problem.source_strengths).reshape(-1)[0]))
    at=path_curves(ref,truth)
    rows=[]
    with execution(device='cpu'):
        for hz in spec['training_frequencies_hz']:
            f=hz/1e9
            exact=np.diag(solve(truth,f,nodes=512,**options).Y)
            initial=np.diag(solve(ref,f,nodes=512,**options).Y)
            # Two small path steps give independent convergence evidence for
            # the local derivative, while finite alpha explores nonlinear loss.
            for alpha in (0.,.001,.003,.01,.03,.1,.25,.5,.75,1.):
                coarse=np.diag(solve(at(alpha),f,nodes=256,**options).Y)
                field=np.diag(solve(at(alpha),f,nodes=512,**options).Y)
                rows.append(dict(frequency_ghz=f,alpha=alpha,
                                 relative_residual_to_truth=float(np.linalg.norm(field-exact)/np.linalg.norm(exact)),
                                 field_change_from_start=float(np.linalg.norm(field-initial)),
                                 refinement_relative=float(np.linalg.norm(field-coarse)/np.linalg.norm(field))))
            print(f'Path {f} GHz done',flush=True)
    write_json(args.output/'path.json',rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4),constrained_layout=True)
    ax.semilogy([r['alpha'] for r in rows],[max(1e-16,r['relative_residual_to_truth']) for r in rows],'o-')
    ax.set_xlabel('physical-angle interpolation: reconstruction (0) → truth (1)')
    ax.set_ylabel('training relative field residual');ax.grid(alpha=.2)
    fig.savefig(args.output/'nonlinear_path.png',dpi=180)

if __name__=='__main__':main()
