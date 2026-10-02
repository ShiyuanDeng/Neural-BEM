"""Qualified full-matrix initializer diagnostics for all frozen topology scenes.

Extra 0.5GHz off-diagonal samples are explicit additional synthetic data. They
are never represented as inferable from the original24 paired measurements.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
from scipy.special import hankel1

from experiments.atlas.run_jacobian_spectrum import solve, execution, ROOT
from experiments.exploratory_continuation.run import frozen, REFERENCE, seed_state, write
from experiments.exploratory_continuation.indicators import tikhonov_sampling, threshold_circles


def matrix_solve(curves, problem, nodes, legacy_constants=False):
    if legacy_constants:
        return solve(curves, float(problem.angular_frequencies[0]/(2*np.pi*1e9)),
            problem.interior.epsr, nodes, problem.source_points, problem.receiver_points,
            exterior_epsr=problem.exterior.epsr, strength=complex(problem.source_strengths[0]))
    from gpr_bem_kress import Material
    from gpr_bem_kress.coupled_shape_derivative import build_coupled_base
    from ordered_boundary import OrderedBoundary2D
    boundary=OrderedBoundary2D(tuple(c.discretize(nodes,require_even=True) for c in curves))
    return build_coupled_base(boundary,problem.source_points,problem.receiver_points,
        float(problem.angular_frequencies[0]),complex(problem.source_strengths[0]),
        exterior=Material(problem.exterior.epsr),interior=Material(problem.interior.epsr),
        eps0=problem.eps0,mu0=problem.mu0)


def full_indicators(matrix, sources, receivers, points, ke, ki, strength, discrepancy=.01,
                    relative_svd_floor=1e-12):
    """Source-by-receiver data; all coordinates and wavenumbers physical."""
    matrix=np.asarray(matrix,complex)
    sources,receivers=np.asarray(sources),np.asarray(receivers)
    if matrix.shape!=(len(sources),len(receivers)) or not np.isfinite(matrix).all():
        raise ValueError('Need the finite FULL source-by-receiver scattering matrix.')
    if not np.isfinite(strength) or strength==0:
        raise ValueError('Nonzero finite physical source strength is required.')
    # This experiment's sources/receivers are uniform offset concentric rings.
    center=sources.mean(axis=0)
    radii=np.linalg.norm(sources-center,axis=1)
    receiver_radii=np.linalg.norm(receivers-center,axis=1)
    if not np.allclose(radii,radii[0],rtol=1e-10) or not np.allclose(receiver_radii,radii[0],rtol=1e-10):
        raise ValueError('This weighting is only qualified for equal-radius rings.')
    for positions in (sources,receivers):
        angle=np.sort(np.mod(np.arctan2(positions[:,1]-center[1],positions[:,0]-center[0]),2*np.pi))
        if not np.allclose(np.diff(np.r_[angle,angle[0]+2*np.pi]),2*np.pi/len(angle),rtol=1e-10):
            raise ValueError('Uniform angular quadrature is required.')
    flat=points.reshape(-1,2)
    gs=.25j*hankel1(0,ke*np.linalg.norm(sources[:,None,:]-flat[None,:,:],axis=-1))
    gr=.25j*hankel1(0,ke*np.linalg.norm(receivers[:,None,:]-flat[None,:,:],axis=-1))
    weights=2*np.pi*radii[0]/len(sources)
    # The LSM operator maps unit incident Green densities to receiver fields.
    operator=matrix.T/strength*weights
    if not np.isfinite(relative_svd_floor) or not 0 <= relative_svd_floor < 1:
        raise ValueError('Relative numerical SVD floor must be in [0,1).')
    u,s,_=np.linalg.svd(operator,full_matrices=False)
    keep=s>relative_svd_floor*s[0]
    if np.count_nonzero(keep)<2:
        raise ValueError('Fewer than two resolved singular directions.')
    # V is unitary, so expressing source densities in its retained coordinates
    # preserves their L2 norm. The rectangular operator makes the unresolved
    # receiver-space residual explicit in the reused discrepancy solver.
    sample=tikhonov_sampling(u[:,keep]*s[keep],gr,discrepancy)
    sample.update(full_singular_values=s,relative_svd_floor=relative_svd_floor,
                  resolved_rank=int(np.count_nonzero(keep)))
    td=-np.real(np.sum((matrix.conj()@gr)*gs*strength*(ki*ki-ke*ke),axis=0))/np.linalg.norm(matrix)**2
    return sample,td.reshape(points.shape[:-1])


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--legacy-atlas-constants',action='store_true',
        help='Reproduce the initial diagnostic with the atlas rounded vacuum constants.')
    parser.add_argument('--relative-svd-floor',type=float,default=1e-12,
        help='Exclude singular directions below the numerical resolution of the full data.')
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Use a new output directory.')
    args.output.mkdir(parents=True)
    spec=frozen.read(ROOT/'config/topology_scenes_v1.json')
    x,y=np.meshgrid(np.linspace(.3,.7,81),np.linspace(.3,.7,81))
    points=np.stack((x,y),axis=-1)
    rows,images=[],[]
    with execution(device='cpu'):
        for scene in spec['scenes']:
            started=perf_counter()
            data,_=frozen.shared_data(REFERENCE,scene,spec)
            p=data.forward_problem
            frequency=float(p.angular_frequencies[0]/(2*np.pi))
            strength=complex(p.source_strengths[0])
            curves=frozen.truth_curves(scene)
            coarse=matrix_solve(curves,p,256,args.legacy_atlas_constants)
            fine=matrix_solve(curves,p,512,args.legacy_atlas_constants)
            matrix=fine.Y
            refinement=float(np.linalg.norm(coarse.Y-matrix)/np.linalg.norm(matrix))
            diagonal=float(np.linalg.norm(np.diag(matrix)-data.observed_scattered_response[:,0])/np.linalg.norm(data.observed_scattered_response[:,0]))
            if max(refinement,diagonal)>spec['oracle_relative_tolerance']:
                raise ValueError('Full observations fail refinement or original-pair agreement.')
            # Match the exact material constants used by the source observation.
            from gpr_bem_kress import Material
            ke=Material(p.exterior.epsr).wavenumber(p.angular_frequencies[0],p.eps0,p.mu0)
            ki=Material(p.interior.epsr).wavenumber(p.angular_frequencies[0],p.eps0,p.mu0)
            sampling,td=full_indicators(matrix,p.source_points,p.receiver_points,points,ke,ki,strength,
                relative_svd_floor=args.relative_svd_floor)
            coarse_sampling,_=full_indicators(coarse.Y,p.source_points,p.receiver_points,points,ke,ki,strength,
                relative_svd_floor=args.relative_svd_floor)
            valid=sampling['discrepancy_attained'] & coarse_sampling['discrepancy_attained']
            indicator_change=float(np.linalg.norm(sampling['indicator'][valid]-coarse_sampling['indicator'][valid])/
                                   np.linalg.norm(sampling['indicator'][valid]))
            lsm=sampling['indicator'].reshape(x.shape)
            initializers={}
            for name,values in [('lsm',-lsm),('topo_full',td)]:
                seeds,_=threshold_circles(points,values)
                state=seed_state(seeds)
                initializers[name]=dict(seeds=[asdict(s) for s in seeds],state=frozen.driver.serialize_state(state),
                    geometry=frozen.geometry_metrics(state,scene,spec))
            # Stable threshold sensitivity is descriptive; no target selects it.
            sensitivity={}
            for discrepancy in (.005,.02):
                other,_=full_indicators(matrix,p.source_points,p.receiver_points,points,ke,ki,strength,discrepancy,
                    relative_svd_floor=args.relative_svd_floor)
                seeds,_=threshold_circles(points,-other['indicator'].reshape(x.shape))
                sensitivity[str(discrepancy)]=dict(seed_count=len(seeds),attained_fraction=float(np.mean(other['discrepancy_attained'])),seeds=[asdict(s) for s in seeds])
            row=dict(scene=scene['id'],frequency_hz=frequency,added_measurements=matrix.size-len(p.source_points),
                refinement_relative=refinement,original_pair_relative=diagonal,
                legacy_atlas_constants=args.legacy_atlas_constants,
                relative_svd_floor=args.relative_svd_floor,resolved_rank=sampling['resolved_rank'],
                indicator_refinement_relative=indicator_change,
                attained_mask_changes=int(np.count_nonzero(sampling['discrepancy_attained'] != coarse_sampling['discrepancy_attained'])),
                source_sha256=hashlib.sha256((REFERENCE/'scenes'/scene['id']/'observations.json').read_bytes()).hexdigest(),
                lsm_attained_fraction=float(np.mean(sampling['discrepancy_attained'])),
                initializers=initializers,lsm_discrepancy_sensitivity=sensitivity,seconds=perf_counter()-started)
            write(args.output/f"{scene['id']}.json",row)
            np.savez_compressed(args.output/f"{scene['id']}.npz",observed=matrix,sources=p.source_points,
                receivers=p.receiver_points,strength=strength,frequency_hz=frequency,
                exterior_epsr=p.exterior.epsr,interior_epsr=p.interior.epsr,eps0=p.eps0,mu0=p.mu0,
                legacy_atlas_constants=args.legacy_atlas_constants,points=points,td=td,**sampling)
            row['matrix_sha256']=hashlib.sha256((args.output/f"{scene['id']}.npz").read_bytes()).hexdigest()
            write(args.output/f"{scene['id']}.json",row)
            rows.append(row);images.append((lsm,td))
            print(json.dumps({k:row[k] for k in ('scene','refinement_relative','original_pair_relative','lsm_attained_fraction')})
                + ' counts '+str({n:v['geometry']['component_count'] for n,v in initializers.items()}),flush=True)
    summary=dict(scope='Explicit full-matrix initialization extension; original paired observations unchanged',
        carrier_hz=500000000,receivers=24,sources=24,extra_complex_observations_per_scene=552,
        discrepancy='1% right-hand-side residual target, not estimated operator noise',threshold=.6,
        relative_svd_floor=args.relative_svd_floor,
        generation=dict(factorizations=24,primal_and_reciprocal_rhs_batches=48,nodes=[256,512]),
        counts={name:sum(r['initializers'][name]['geometry']['component_count']==r['initializers'][name]['geometry']['truth_component_count'] for r in rows) for name in ('lsm','topo_full')},
        rows=rows)
    write(args.output/'summary.json',summary)
    write(args.output/'manifest.json',dict(source_sha256={str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},spec_sha256=hashlib.sha256((ROOT/'config/topology_scenes_v1.json').read_bytes()).hexdigest()))
    plot(args.output,spec,rows,images)


def plot(output,spec,rows,images):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    angle=np.linspace(0,2*np.pi,160)
    for method,index in [('lsm',0),('topo_full',1)]:
        fig,axes=plt.subplots(3,4,figsize=(13,10),constrained_layout=True)
        for ax,scene,row,image in zip(axes.flat,spec['scenes'],rows,images):
            values=image[index] if index==0 else np.maximum(-image[index],0)
            scale=np.nanmax(values)
            ax.imshow(values/scale,origin='lower',extent=(.3,.7,.3,.7),cmap='magma')
            for curve in frozen.truth_curves(scene):
                p=curve.discretize(512).points
                ax.plot(p[:,0],p[:,1],color='cyan',lw=1)
            for s in row['initializers'][method]['seeds']:
                ax.plot(s['center'][0]+s['radius']*np.cos(angle),s['center'][1]+s['radius']*np.sin(angle),'w-',lw=1)
            ax.set_title(scene['id'],fontsize=9);ax.set_aspect('equal')
        fig.suptitle(f'{method}: 24×24 full-matrix initialization; white seeds / cyan evaluation truth')
        fig.savefig(output/f'{method}.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()
