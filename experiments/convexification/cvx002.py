"""CVX-002 augmented-boundary feasibility campaign on frozen TG-002 targets."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback

import numpy as np
from scipy.special import hankel1, h1vp, jv, jvp
from scipy.spatial import cKDTree
from skimage.measure import find_contours
from skimage.restoration import unwrap_phase
from matplotlib.path import Path as Polygon

from bem_inverse.continuation.forward import PointSourceAcquisition, solve
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.io import curve_from, curve_record, read, write, digest
from gpr_bem_kress import build_exterior_receiver_operator
from gpr_bem_kress.geometry import adapt_periodic_curve
from experiments.benchmark import campaign as B
from .joint_tail import Grid, BoundaryData, JointTail, algebra_qualification


CASES=('circle__c0.5','circle__c4','circle__c13.3','c_shape__c13.3')
ROOT=Path(__file__).resolve().parents[2]
DEADLINE=float('inf')


def budget(deadline=float('inf')):
    if perf_counter()>=min(DEADLINE,deadline):
        raise TimeoutError('Registered wall budget exhausted')


def incident(points,k,source,strength):
    delta=np.asarray(points)-source
    radius=np.linalg.norm(delta,axis=1)
    value=.25j*strength*hankel1(0,k*radius)
    gradient=(-.25j*strength*k*hankel1(1,k*radius))[:,None]*delta/radius[:,None]
    return value,gradient


def exterior_normal(state,points,normals):
    adapter=adapt_periodic_curve(state.curve)
    delta=points[:,None,:]-adapter.points[None,:,:]
    radius=np.linalg.norm(delta,axis=-1)
    e=delta/radius[:,:,None]
    en=np.einsum('pnd,nd->pn',e,adapter.normals)
    ev=np.einsum('pnd,pd->pn',e,normals)
    nv=normals@adapter.normals.T
    k=state.wavenumber
    first=-.25j*k*hankel1(1,k*radius)
    second=.25j*(2*k*hankel1(1,k*radius)/radius-k*k*hankel1(0,k*radius))
    ds=first*ev*adapter.arc_length_weights
    dd=(-second*ev*en-first/radius*nv)*adapter.arc_length_weights
    n=state.curve.num_nodes
    return (dd@state.traces[:n]-ds@state.traces[n:]).T[0]


def disk_field(points,k,contrast,source,strength,radius=1.3,cutoff=36):
    """Exact total field of prescribed centered disk, including its interior."""
    orders=np.arange(-cutoff,cutoff+1)
    ki=k*np.sqrt(contrast)
    sr=np.linalg.norm(source);sa=np.arctan2(source[1],source[0])
    a=.25j*strength*hankel1(orders,k*sr)*np.exp(-1j*orders*sa)
    ji,jip=jv(orders,ki*radius),jvp(orders,ki*radius)
    je,jep=jv(orders,k*radius),jvp(orders,k*radius)
    he,hep=hankel1(orders,k*radius),h1vp(orders,k*radius)
    den=k*ji*hep-ki*jip*he
    scattered=(ki*jip*je-k*jep*ji)/den
    transmitted=(2j/(np.pi*radius))/den
    rr=np.linalg.norm(points,axis=1);angle=np.arctan2(points[:,1],points[:,0])
    phase=np.exp(1j*angle[:,None]*orders)
    inside=rr<radius
    result=np.empty(len(points),complex)
    result[inside]=np.sum(a*transmitted*jv(orders,ki*rr[inside,None])*phase[inside],axis=1)
    outside=~inside
    result[outside]=incident(points[outside],k,source,strength)[0]+np.sum(
        a*scattered*hankel1(orders,k*rr[outside,None])*phase[outside],axis=1)
    if not np.isfinite(result).all():raise FloatingPointError('Nonfinite exact disk field')
    return result


def relative(a,b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))


def prepare(case,grid,folder):
    """Only this generator loads truth. Fit inputs contain boundary data only."""
    started=perf_counter();problem=B.problem(case)
    truth=curve_from(read(ROOT/B.row(case)['truth']))
    outline=truth.values(16384)
    if max(abs(outline.real).max(),abs(outline.imag).max())>=grid.half:
        raise ValueError('Truth support is not enclosed by the auxiliary box')
    source=problem.real[0].acquisition.sources[0]
    strength=problem.real[0].acquisition.strength
    boundary=grid.points[grid.boundary]
    faces=grid.points[grid.normal_ids]
    values=[];normals=[];gradients=[];initial=[];ratios=[];checks=[]
    for o in problem.real[:3]:
        budget()
        k=o.wavenumber
        acq=PointSourceAcquisition(source[None,:],boundary,strength,False)
        states=[solve(truth,k,problem.contrast,acq,n,execution_backend='cpu') for n in (512,1024)]
        inc,ig=incident(boundary,k,source,strength)
        ng=incident(faces,k,source,strength)[1]
        u=[s.prediction[0]+inc for s in states]
        un=[exterior_normal(s,faces,grid.normals)+np.sum(ng*grid.normals,axis=1) for s in states]
        check=dict(frequency_hz=o.frequency_hz,field_refinement=relative(u[0],u[1]),
                   normal_refinement=relative(un[0],un[1]))
        # Derivative reference uses existing value operator, not the new derivative code.
        if not values:
            errors=[]
            for h in (1e-4,5e-5):
                plus,minus=faces+h*grid.normals,faces-h*grid.normals
                vp=build_exterior_receiver_operator(states[-1].curve,plus,k).apply_state(states[-1].traces)[0]
                vm=build_exterior_receiver_operator(states[-1].curve,minus,k).apply_state(states[-1].traces)[0]
                fd=(vp-vm)/(2*h)
                errors.append(relative(fd,exterior_normal(states[-1],faces,grid.normals)))
            check['normal_fd_errors']=errors
        incfull,gradfull=incident(grid.points,k,source,strength)
        initial_u=disk_field(grid.points,k,problem.contrast,source,strength)
        refined=disk_field(grid.points,k,problem.contrast,source,strength,cutoff=46)
        check['mie_cutoff_refinement']=relative(initial_u,refined)
        start_state=solve(problem.initial,k,problem.contrast,acq,512,execution_backend='cpu')
        check['initial_mie_vs_nodal']=relative(initial_u[grid.boundary],start_state.prediction[0]+inc)
        check['passed']=check['field_refinement']<1e-7 and check['normal_refinement']<1e-6 and check['mie_cutoff_refinement']<1e-8 and check['initial_mie_vs_nodal']<1e-7 and max(check.get('normal_fd_errors',[0]))<1e-5
        checks.append(check)
        write(folder/'data_qualification.json',dict(checks=checks,passed=all(c['passed'] for c in checks)))
        if not check['passed']:raise RuntimeError(f'Boundary/initial physics qualification failed: {check}')
        fullvalues=np.zeros(grid.n**2,complex);fullvalues[grid.boundary]=u[-1]
        ratio=fullvalues[grid.cycle]/incfull[grid.cycle]
        ratios.append(ratio)
        values.append(fullvalues)
        normals.append((un[-1]/u[-1][np.searchsorted(grid.boundary,grid.normal_ids)]-
                        np.sum(ng*grid.normals,axis=1)/incident(faces,k,source,strength)[0])/k**2)
        gradients.append(gradfull/incfull[:,None])
        initial.append(initial_u/incfull)
        print('DATA',case,o.frequency_hz/1e9,check,flush=True)
    k=np.array([o.wavenumber for o in problem.real[:3]])
    ratios=np.asarray(ratios)
    winding=np.sum(np.angle(np.roll(ratios,-1,axis=1)/ratios),axis=1)/(2*np.pi)
    boundary_increment=float(abs(np.angle(np.roll(ratios,-1,axis=1)/ratios)).max())
    phase_record=dict(boundary_winding=winding,min_boundary_abs_u_over_u0=float(abs(ratios).min()),
                      max_boundary_wrapped_phase_increment=boundary_increment)
    write(folder/'log_qualification.json',phase_record)
    if max(abs(winding))>1e-6 or abs(ratios).min()<1e-8:
        raise ValueError(f'Boundary log unqualified: winding={winding}, minimum={abs(ratios).min()}')
    phase=np.unwrap(np.angle(ratios),axis=1)
    anchors=np.unwrap(phase[:,0])
    phase+=2*np.pi*np.round((anchors-phase[:,0])/(2*np.pi))[:,None]
    logvalues=np.zeros((3,grid.n**2),complex)
    logvalues[:,grid.cycle]=(np.log(abs(ratios))+1j*phase)/k[:,None]**2
    initial=np.asarray(initial)
    initial_grid=initial.reshape(3,grid.n,grid.n)
    edges_x=np.angle(initial_grid[:,:,1:]/initial_grid[:,:,:-1])
    edges_y=np.angle(initial_grid[:,1:,:]/initial_grid[:,:-1,:])
    residues=(edges_x[:,:-1,:]+edges_y[:,:,1:]-edges_x[:,1:,:]-edges_y[:,:,:-1])/(2*np.pi)
    phase_record.update(initial_plaquette_nonzero_count=int(np.count_nonzero(abs(residues)>.5)),
                        max_initial_wrapped_phase_increment=float(max(abs(edges_x).max(),abs(edges_y).max())),
                        min_initial_abs_u_over_u0=float(abs(initial).min()),
                        boundary_cycle_closure=float(max(abs(np.sum(np.angle(np.roll(ratios,-1,axis=1)/ratios),axis=1)))))
    write(folder/'log_qualification.json',phase_record)
    if phase_record['initial_plaquette_nonzero_count']:
        raise ValueError(f'Initial log field has phase vortices: {phase_record}')
    initphase=np.array([unwrap_phase(np.angle(r.reshape(grid.n,grid.n)),rng=1926).ravel() for r in initial])
    first=np.unwrap(np.angle(initial[:,grid.cycle[0]]))
    initphase+=2*np.pi*np.round((first-initphase[:,grid.cycle[0]])/(2*np.pi))[:,None]
    initfields=(np.log(abs(initial))+1j*initphase)/k[:,None]**2
    if abs(initial).min()<1e-8:raise ValueError('Initial log field is unqualified near a sampled zero')
    start_c=1+(problem.contrast-1)*(np.linalg.norm(grid.points[grid.interior],axis=1)<1.3)
    data=BoundaryData(k,logvalues,np.asarray(normals),np.asarray(gradients))
    np.savez_compressed(folder/'fit_inputs.npz',k=k,boundary_log=logvalues,boundary_normal=data.normal,
                        incident_gradient=data.incident_gradient,initial_fields=initfields,initial_coefficient=start_c)
    qualification=dict(passed=True,checks=checks,boundary_winding=winding,
                       min_boundary_abs_u_over_u0=float(abs(ratios).min()),
                       min_initial_abs_u_over_u0=float(abs(initial).min()),
                       seconds=perf_counter()-started,source=source,
                       acquisition='Augmented full fixed-source Cauchy data; not original paired acquisition')
    write(folder/'data_qualification.json',qualification)
    return data,initfields,start_c,qualification


def coefficient_image(grid,c):
    image=np.ones(grid.n**2);image[grid.interior]=c
    return image.reshape(grid.n,grid.n)


def resample(z,count=None):
    if abs(z[0]-z[-1])>1e-10:z=np.r_[z,z[0]]
    s=np.r_[0,np.cumsum(abs(np.diff(z)))]
    count=count or max(128,int(np.ceil(s[-1]/.002)))
    t=np.linspace(0,s[-1],count,endpoint=False)
    return np.interp(t,s,z.real)+1j*np.interp(t,s,z.imag)


def score(case,grid,c,folder,label):
    """Post-fit truth scoring; this function is never called by JointTail."""
    truth=curve_from(read(ROOT/B.row(case)['truth']))
    chi=B.row(case)['contrast']
    boundary=truth.values(16384)
    mask=Polygon(np.column_stack((boundary.real,boundary.imag))).contains_points(grid.points).reshape(grid.n,grid.n)
    estimate=coefficient_image(grid,c)
    occupancy=(estimate-1)/(chi-1)
    predicted=occupancy>.5
    contours=[]
    for contour in find_contours(occupancy,.5):
        z=np.interp(contour[:,1],np.arange(grid.n),grid.axis)+1j*np.interp(contour[:,0],np.arange(grid.n),grid.axis)
        contours.append(z)
    measurements=dict(coefficient_rmse=float(np.sqrt(np.mean((estimate-(1+(chi-1)*mask))**2))),
                      coefficient_relative_error=float(np.linalg.norm(estimate-(1+(chi-1)*mask))/np.linalg.norm(1+(chi-1)*mask)),
                      occupancy_iou=float(np.count_nonzero(predicted&mask)/max(1,np.count_nonzero(predicted|mask))),
                      area_relative_error=float(np.count_nonzero(predicted)/np.count_nonzero(mask)-1),
                      out_of_material_range_fraction=float(np.mean((occupancy<0)|(occupancy>1))),
                      contour_count=len(contours),grid_spacing_mm=grid.h*50,
                      sampled_symmetric_rms_mm=None,sampled_hausdorff_mm=None)
    if contours:
        points=np.concatenate([resample(z) for z in contours])
        txy=np.column_stack((boundary.real,boundary.imag));pxy=np.column_stack((points.real,points.imag))
        d1=cKDTree(txy).query(pxy)[0];d2=cKDTree(pxy).query(txy)[0]
        measurements.update(sampled_symmetric_rms_mm=float(50*np.sqrt((np.mean(d1*d1)+np.mean(d2*d2))/2)),
                            sampled_hausdorff_mm=float(50*max(d1.max(),d2.max())))
    np.savez_compressed(folder/f'{label}_scoring.npz',coefficient=estimate,occupancy=occupancy,
                        truth_mask=mask,truth_boundary=boundary,**{f'contour_{j}':z for j,z in enumerate(contours)})
    curve=None
    if contours:
        closed=[z for z in contours if abs(z[0]-z[-1])<1e-8]
        if closed:
            z=max(closed,key=lambda p:abs(np.sum(p[:-1].real*p[1:].imag-p[1:].real*p[:-1].imag)))
            if np.sum(z[:-1].real*z[1:].imag-z[1:].real*z[:-1].imag)<0:z=z[::-1]
            samples=resample(z,2048)
            curve=FourierCurve.from_samples(samples,16)
            try:
                curve.validate()
                measurements['readout_smoothing_rms_mm']=float(50*np.sqrt(np.mean(abs(curve.values(2048)-samples)**2)))
                measurements['readout_discarded_components']=len(contours)-1
                write(folder/f'{label}_curve.json',curve_record(curve))
            except Exception as exc:
                measurements['curve_failure']=str(exc);curve=None
        else:measurements['curve_failure']='No closed threshold contour'
    return measurements,curve


def paired_check(case,curve,folder,deadline=float('inf')):
    problem=B.problem(case);rows=[];started=perf_counter()
    for o in problem.real:
        budget(deadline)
        predictions=[solve(curve,o.wavenumber,problem.contrast,o.acquisition,n,execution_backend='cpu').prediction for n in (256,512)]
        refinement=relative(predictions[0],predictions[1]);nodes=[256,512]
        if refinement>1e-5:
            predictions.append(solve(curve,o.wavenumber,problem.contrast,o.acquisition,1024,execution_backend='cpu').prediction)
            refinement=relative(predictions[-2],predictions[-1]);nodes=[512,1024]
        rows.append(dict(frequency_hz=o.frequency_hz,residual=relative(predictions[-1],o.scattered),
                         refinement=refinement,nodes=nodes,qualified=refinement<=1e-5))
        write(folder/'paired_validation.json',dict(rows=rows,complete=False))
    result=dict(rows=rows,complete=True,qualified=all(r['qualified'] for r in rows),
                maximum_relative_residual=max(r['residual'] for r in rows),
                rms_relative_residual=float(np.sqrt(np.mean([r['residual']**2 for r in rows]))),
                frequencies_below_003=sum(r['residual']<=.003 for r in rows),seconds=perf_counter()-started,
                certified_tg002_recovery=False)
    write(folder/'paired_validation.json',result);return result


def fit_arm(case,grid,data,initfields,start_c,span,folder):
    folder.mkdir()
    model=JointTail(grid,data,span)
    def callback(fields,c,history,stop):
        np.savez_compressed(folder/'latest.npz',fields=fields,coefficient=c,axis=grid.axis)
        write(folder/'progress.json',dict(history=history,stop=stop,diagnostics=model.diagnostics(fields,c)))
        if history:print('FIT',case,grid.n,span,history[-1]['iteration'],history[-1]['objective'],stop,flush=True)
        budget(deadline)
    started=perf_counter()
    deadline=started+300
    try:
        fields,c,history,stop=model.fit(initfields,start_c,callback,wall_seconds=min(300,DEADLINE-started))
        budget(deadline)
        result=dict(case=case,grid=grid.n,weight_log_span=span,stop=stop,history=history,
                    diagnostics=model.diagnostics(fields,c),fit_seconds=perf_counter()-started,
                    accepted_updates=sum(r.get('fraction',0)>0 for r in history),acquisition='augmented_full_cauchy')
        write(folder/'result.json',result)
        initial_metrics,_=score(case,grid,start_c,folder,'initial')
        final_metrics,curve=score(case,grid,c,folder,'final')
        result.update(initial=initial_metrics,final=final_metrics)
        if curve is not None:
            result['paired']=paired_check(case,curve,folder,deadline)
        else:result['paired']=dict(qualified=False,failure='Invalid contour readout')
        result['total_seconds']=perf_counter()-started
        result['refinement_eligible']=bool(curve is not None and result['paired']['qualified']
              and final_metrics['sampled_symmetric_rms_mm']<=.75*initial_metrics['sampled_symmetric_rms_mm']
              and final_metrics['occupancy_iou']>=initial_metrics['occupancy_iou']+.10)
        write(folder/'result.json',result)
        return result
    except Exception:
        failure=traceback.format_exc();(folder/'failure.txt').write_text(failure)
        write(folder/'failure.json',dict(case=case,span=span,seconds=perf_counter()-started,failure=failure))
        raise


def main():
    global DEADLINE
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--grid',type=int,default=41)
    parser.add_argument('--cases',nargs='+',default=list(CASES))
    parser.add_argument('--spans',nargs='+',type=float,default=[0,4])
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    started=perf_counter();DEADLINE=started+1800;results=[]
    def interrupted(signum,frame):
        raise TimeoutError(f'External watchdog signal {signum}')
    signal.signal(signal.SIGTERM,interrupted)
    sources=sorted([*Path(__file__).parent.glob('*.py'),ROOT/'docs/iterations/convexification/CVX-002_plan.md',
                    *ROOT.glob('solvers/bem_inverse/continuation/*.py'),*ROOT.glob('solvers/gpr_bem_kress/*.py'),
                    ROOT/'experiments/benchmark/campaign.py',ROOT/'experiments/benchmark/scenes.py'])
    hashes={str(p.relative_to(ROOT)):digest(p) for p in sources}
    with tarfile.open(args.output/'sources.tar.gz','w:gz') as tar:
        for p in sources:tar.add(p,arcname=str(p.relative_to(ROOT)))
    write(args.output/'manifest.json',dict(experiment='CVX-002',command=[sys.executable,*sys.argv],
          settings=vars(args),source_hashes=hashes,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          python=sys.version,platform=platform.platform(),augmented_acquisition=True))
    try:
        B.verify(require_inputs=True)
        algebra=algebra_qualification();write(args.output/'algebra_qualification.json',algebra)
        if not algebra['passed']:raise RuntimeError(f'Algebra qualification failed: {algebra}')
        grid=Grid(args.grid)
        for case in args.cases:
            budget()
            folder=args.output/case;folder.mkdir()
            try:
                data,initial,c0,qualification=prepare(case,grid,folder)
            except Exception:
                failure=traceback.format_exc();(folder/'failure.txt').write_text(failure)
                for span in args.spans:results.append(dict(case=case,grid=grid.n,weight_log_span=span,status='DATA_QUALIFICATION_FAILED',failure=failure))
                write(args.output/'summary.json',dict(complete=False,results=results,seconds=perf_counter()-started))
                print('CASE FAILED',case,failure,flush=True)
                continue
            for span in args.spans:
                budget()
                try:
                    result=fit_arm(case,grid,data,initial,c0,span,folder/f'span{span:g}')
                except Exception:
                    result=dict(case=case,grid=grid.n,weight_log_span=span,status='ARM_FAILED',failure=traceback.format_exc())
                    print('ARM FAILED',case,span,result['failure'],flush=True)
                results.append(result)
                write(args.output/'summary.json',dict(complete=False,results=results,seconds=perf_counter()-started))
    except Exception:
        (args.output/'failure.txt').write_text(traceback.format_exc())
        raise
    finally:
        write(args.output/'summary.json',dict(complete=len(results)==len(args.cases)*len(args.spans),results=results,
              seconds=perf_counter()-started,source_hashes_unchanged=all(digest(ROOT/p)==h for p,h in hashes.items())))


if __name__=='__main__':main()
