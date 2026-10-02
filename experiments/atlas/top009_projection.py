"""Project the saved TOP-009 error, retaining linearization and graph diagnostics.

A large near-null projection is a local diagnostic, not a uniqueness claim.
No truth-selected rotation or phase alignment is applied.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.interpolate import CubicSpline
from .run_jacobian_spectrum import NormalBasis, solve, jacobian, spectral, write_json, ROOT, relative, execution
import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from sdf_inverse.topology_controller import component_parameterization

SAVED = ROOT/'results/validation/topology/TOP-009-20260912-bandwidth-capacity/stage4_uncapped_ladder.json'
SPEC = ROOT/'results/validation/topology/TOP-008-20260912-feasible-fd/scene_spec.json'


def cross(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def normal_difference(producer, target, basis, samples=2048):
    curve = producer.discretize(samples)
    q = target.discretize(8192).points
    end = np.roll(q,-1,axis=0)
    edge = end-q
    hs, missing, multi_near = [], 0, 0
    index_history = []
    # Normal lines intersect twice even for concentric circles; choose the
    # nearest signed intersection and record whether the resulting map folds.
    for p,n in zip(curve.points,curve.normals):
        denom = cross(n,edge)
        safe = np.where(abs(denom)>1e-16,denom,np.nan)
        h,t = cross(q-p,edge)/safe,cross(q-p,n)/safe
        mask = np.isfinite(h)&(t>=0)&(t<1)
        if np.any(mask):
            eligible = np.flatnonzero(mask)
            chosen = eligible[np.argmin(abs(h[eligible]))]
            hs.append(h[chosen]); index_history.append(chosen+t[chosen])
            multi_near += int(np.count_nonzero(mask & (abs(h)<.02))>1)
        else:
            # Save a finite diagnostic, but mark that no normal graph exists.
            missing += 1
            delta = q-p
            fraction = np.clip(np.sum((p-q)*edge,axis=1)/np.sum(edge**2,axis=1),0,1)
            nearest = q+fraction[:,None]*edge
            chosen = int(np.argmin(np.linalg.norm(nearest-p,axis=1)))
            hs.append(np.dot(nearest[chosen]-p,n)); index_history.append(chosen+fraction[chosen])
    h = np.array(hs)
    a = basis.values(curve.parameters)
    w = curve.arc_length_weights/basis.length
    gram = a.T @ (w[:,None]*a)
    coeff = np.linalg.solve(gram,a.T @ (w*h))
    residual = h-a@coeff
    phase = np.unwrap(2*np.pi*np.r_[index_history,index_history[0]]/len(q))
    report = dict(normal_rms_m=float(np.sqrt(np.sum(w*h*h))),
                  normal_maximum_m=float(np.max(abs(h))),
                  outside_band_rms_m=float(np.sqrt(np.sum(w*residual**2))),
                  coefficient_norm_m=float(np.linalg.norm(coeff)),
                  missing_normal_intersections=missing,
                  multiple_intersections_within_20mm=multi_near,
                  backwards_correspondence_steps=int(np.count_nonzero(np.diff(phase)<-1e-5)),
                  correspondence_winding=float((phase[-1]-phase[0])/(2*np.pi)))
    return coeff,report


def polar_difference(producer, target, basis, samples=2048):
    """Smooth correspondence by physical polar angle, using each curve's centre.

    Its normal component is the tangent to the full vector displacement path;
    this does not assume that the other curve is a normal graph.
    """
    curve = producer.discretize(samples)
    target_curve = target.discretize(8192)
    origin, destination = curve.points.mean(axis=0), target_curve.points.mean(axis=0)
    p, q = curve.points-origin, target_curve.points-destination
    angle = np.mod(np.arctan2(q[:,1],q[:,0]),2*np.pi)
    winding_steps = np.diff(np.unwrap(np.r_[angle,angle[0]]))
    if np.any(winding_steps <= 0):
        raise ValueError('Polar correspondence requires a strictly star-shaped target.')
    order = np.argsort(angle)
    theta, radius = angle[order], np.linalg.norm(q[order],axis=1)
    spline = CubicSpline(np.r_[theta,theta[0]+2*np.pi], np.r_[radius,radius[0]],bc_type='periodic')
    phi = np.mod(np.arctan2(p[:,1],p[:,0])-theta[0],2*np.pi)+theta[0]
    mapped = destination+spline(phi)[:,None]*np.column_stack((np.cos(phi),np.sin(phi)))
    velocity = mapped-curve.points
    h = np.sum(velocity*curve.normals,axis=1)
    tangent = np.sum(velocity*curve.tangents,axis=1)
    a, w = basis.values(curve.parameters), curve.arc_length_weights/basis.length
    coeff = np.linalg.solve(a.T @ (w[:,None]*a),a.T @ (w*h))
    return coeff,dict(normal_rms_m=float(np.sqrt(np.sum(w*h*h))),
                      normal_maximum_m=float(np.max(abs(h))),
                      outside_band_rms_m=float(np.sqrt(np.sum(w*(h-a@coeff)**2))),
                      coefficient_norm_m=float(np.linalg.norm(coeff)),
                      tangential_rms_m=float(np.sqrt(np.sum(w*tangent*tangent))),
                      correspondence='monotone physical polar angle; each curve uses its own Fourier centre')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--nodes',type=int,default=256)
    p.add_argument('--refined-nodes',type=int,default=512)
    p.add_argument('--correspondence', choices=['normal','polar'], default='normal')
    args=p.parse_args(argv)
    if args.output.exists() and any(args.output.iterdir()):
        raise FileExistsError('Use a new output directory.')
    args.output.mkdir(parents=True,exist_ok=True)
    saved,spec=json.loads(SAVED.read_text()),json.loads(SPEC.read_text())
    scene=next(s for s in spec['scenes'] if s['id']==saved['scene'])
    state=driver.deserialize_state(saved['final_state'])
    producers=tuple(component_parameterization(c) for c in state.components)
    truth_by_id={c.component_id:c for c in benchmark.truth_curves(scene)}
    matches={r['recovered_component']:r['truth_component'] for r in saved['final_geometry']['matched_components']}
    truths=tuple(truth_by_id[matches[c.component_id]] for c in state.components)
    problem=driver.baseline._problem(np.array(spec['training_frequencies_hz']), acquisition=spec.get('acquisition'))
    sources,receivers=problem.source_points,problem.receiver_points
    strength=complex(np.asarray(problem.source_strengths).reshape(-1)[0])
    options=dict(epsr=problem.interior.epsr,exterior_epsr=problem.exterior.epsr,
                 sources=sources,receivers=receivers,strength=strength)
    metadata=dict(saved_state=str(SAVED.relative_to(ROOT)),spec=str(SPEC.relative_to(ROOT)),
                  hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (SAVED,SPEC)},
                  training_frequencies_hz=spec['training_frequencies_hz'],holdout_frequencies_hz=spec['holdout_frequencies_hz'],
                  sources=sources.tolist(), receivers=receivers.tolist(),exterior_epsr=problem.exterior.epsr,
                  interior_epsr=problem.interior.epsr, nodes=args.nodes,refined_nodes=args.refined_nodes,
                  projection=args.correspondence,
                  metric='sum of per-component mean-square normal motion, equal component weights',
                  null_threshold=1e-3,warning='Local derivative projection; nonlinear remainder and graph failures limit interpretation.')
    write_json(args.output/'manifest.json',metadata)
    all_rows, geometry_rows = [],[]
    with execution(device='cpu'):
        for location,reference,other in [('reconstruction',producers,truths),('truth',truths,producers)]:
            bases=tuple(NormalBasis(p,40) for p in reference)
            difference = normal_difference if args.correspondence == 'normal' else polar_difference
            projections=[difference(p,q,b) for p,q,b in zip(reference,other,bases)]
            coefficients=np.concatenate([v[0] for v in projections])
            geometry_rows.extend([dict(location=location,component=p.component_id,**v[1]) for p,v in zip(reference,projections)])
            stack={m:[] for m in (9,40)}; stack_coarse={m:[] for m in (9,40)}
            stack_actual=[]
            for f_hz in spec['training_frequencies_hz']+spec['holdout_frequencies_hz']:
                frequency=f_hz/1e9
                coarse=solve(reference,frequency,nodes=args.nodes,**options)
                fine=solve(reference,frequency,nodes=args.refined_nodes,**options)
                target=solve(other,frequency,nodes=args.refined_nodes,**options)
                jc,jf=jacobian(coarse,bases),jacobian(fine,bases)
                ids=np.arange(len(sources)); c,f=jc[ids,ids],jf[ids,ids]
                actual=np.diag(target.Y-fine.Y)
                stack_actual.append(actual)
                for m in (9,40):
                    cols=np.concatenate([np.arange(i*81,i*81+2*m+1) for i in range(len(reference))])
                    j,jc_m,coeff=f[:,cols],c[:,cols],coefficients[cols]
                    stack[m].append(j); stack_coarse[m].append(jc_m)
                    s,vh,metrics=spectral(j,jc_m)
                    coordinates=vh@coeff
                    fraction=float(np.linalg.norm(coordinates[s<=1e-3*s[0]])/np.linalg.norm(coeff))
                    linear=j@coeff
                    all_rows.append(dict(location=location,frequency_ghz=frequency,band=m,
                                         role='training' if f_hz in spec['training_frequencies_hz'] else 'holdout',
                                         near_null_norm_fraction=fraction,near_null_energy_fraction=fraction**2,
                                         linearized_change_norm=float(np.linalg.norm(linear)),
                                         actual_change_norm=float(np.linalg.norm(actual)),
                                         nonlinear_remainder_relative=relative(linear,actual),**metrics))
                    np.savez_compressed(args.output/f'{location}_f{frequency:g}_M{m}.npz',jacobian=j,
                                        coarse_jacobian=jc_m,coefficients=coeff,singular_values=s,right_vectors=vh,
                                        actual_field_difference=actual,linearized_difference=linear)
                print(f'TOP009 {location} {frequency:g} GHz done',flush=True)
            for m in (9,40):
                j,c=np.concatenate(stack[m]),np.concatenate(stack_coarse[m])
                cols=np.concatenate([np.arange(i*81,i*81+2*m+1) for i in range(len(reference))])
                coeff=coefficients[cols]; s,vh,metrics=spectral(j,c)
                fraction=float(np.linalg.norm((vh@coeff)[s<=1e-3*s[0]])/np.linalg.norm(coeff))
                all_rows.append(dict(location=location,frequency_ghz='stacked',band=m,role='training+holdout diagnostic',
                                     near_null_norm_fraction=fraction,near_null_energy_fraction=fraction**2,
                                     nonlinear_remainder_relative=relative(j@coeff,np.concatenate(stack_actual)),**metrics))
            write_json(args.output/'projection.json',all_rows)
            write_json(args.output/'normal_graph.json',geometry_rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    for ax,loc in zip(axes,['reconstruction','truth']):
        for m in (9,40):
            rs=[r for r in all_rows if r['location']==loc and r['band']==m]
            ax.plot([str(r['frequency_ghz']) for r in rs],[r['near_null_energy_fraction'] for r in rs],'o-',label=f'M={m}')
        ax.set_ylim(0,1);ax.set_title('Jacobian at '+loc);ax.set_ylabel('error energy below 0.001 σ₁');ax.set_xlabel('GHz / stacked diagnostic');ax.legend()
    fig.savefig(args.output/'top009_projection.png',dpi=180)

if __name__=='__main__':
    main()
