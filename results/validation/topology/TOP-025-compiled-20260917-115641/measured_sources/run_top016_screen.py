"""TOP-016 Phase-0 completion and binding Phase-1 information screen.

Consumes saved Phase-0 evidence; never reruns completed input/resolution checks.
No optimizer, topology controller, truth-selected directions or fitted evaluation data.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import run_top016_preflight as p


def scaled_change(prediction, base, observations):
    norms=np.linalg.norm(observations,axis=0)
    return (prediction-base)/norms[None,:]


def rms_data(change):
    return float(np.sqrt(np.mean(np.sum(abs(change)**2,axis=0))))


def spectrum(matrix):
    u,s,v=np.linalg.svd(matrix,full_matrices=False)
    return dict(singular_values=s,right_vectors=v,left_vectors=u),v


def normal_rms(base, perturbed, count=2048):
    numerator=denominator=0.
    for a,b in zip(base.components,perturbed.components):
        curve=p.component_parameterization(a).discretize(count)
        other=p.component_parameterization(b).discretize(count)
        delta=np.sum((other.points-curve.points)*curve.normals,axis=1)
        numerator+=float(np.sum(curve.arc_length_weights*delta**2))
        denominator+=float(np.sum(curve.arc_length_weights))
    return np.sqrt(numerator/denominator)


def retrace(state,basis,direction,scale):
    return state.incremented(basis.T@(direction*scale)).polar_angle_gauge_fixed()[0]


def physical_direction(state,basis,direction):
    # The retained Cartesian subspace is linear; this computes the linear
    # physical normal displacement, with arclength weights on the base state.
    trial=state.incremented(basis.T@(direction*1e-5))
    per_unit=normal_rms(state,trial)/1e-5
    if per_unit<=1e-10:
        return None,per_unit
    return direction*(.001/per_unit),per_unit


def gate(rows):
    usable=[r for r in rows if r.get('usable')]
    if len(usable)<4:
        return dict(passed=False,reason='fewer than four usable directions',usable=len(usable))
    checks=[]
    for resolution in ('production','refined'):
        for amplitude in (.5,1.):
            gains=[float(np.median([v[resolution]['gain'] for v in r['probes']
                                   if v['amplitude_mm']==amplitude])) for r in usable]
            checks.append(dict(resolution=resolution,amplitude_mm=amplitude,
                median_gain=float(np.median(gains)),fraction_at_least_1_5=float(np.mean(np.array(gains)>=1.5)),
                passed=bool(np.median(gains)>=1.5 and np.mean(np.array(gains)>=1.5)>=.5)))
    gains=[r['median_gain'] for r in usable]
    passed=all(c['passed'] for c in checks) and np.median(gains)>=1.5 and np.mean(np.array(gains)>=1.5)>=.5
    return dict(passed=bool(passed),usable=len(usable),median_gain=float(np.median(gains)),
                fraction_at_least_1_5=float(np.mean(np.array(gains)>=1.5)),robustness_checks=checks)


def oracle(scene,frequencies,nodes,solve,ledger):
    ledger.reserve(len(frequencies));ledger.calls['oracle_validation']+=1
    with ledger.category_scope('oracle_validation'):
        return p.physical.predict_multicomponent_kress_paired_boundary_response(
            p.OrderedBoundary2D(tuple(c.discretize(nodes) for c in p.benchmark.truth_curves(scene))),
            p.driver.baseline._problem(np.asarray(frequencies)),solve_config=solve).scattered_response


def measure_scene(name,state,observed,nodes,solve,control,ledger,save):
    low,high=nodes;basis=state.gauge_tangent_basis();dimension=len(basis)
    report=dict(scene=name,coordinate_convention='original Cartesian coefficient vector; orthonormal gauge basis rows',
        gauge_basis=basis,dimension=dimension,fd_steps=[1e-4,5e-5],jacobians={},spectra={},directions=[])
    prediction_cache={}
    def predict(s,n,category):
        key=(s.parameter_vector().tobytes(),n)
        if key not in prediction_cache:
            prediction_cache[key]=p.prediction(s,p.TRAIN,n,solve,ledger,category)
        else:
            ledger.calls['cache_hits']+=1
        return prediction_cache[key]
    bases={n:predict(state,n,'screen_base') for n in nodes}
    repeated=p.prediction(state,p.TRAIN,low,solve,ledger,'repeatability')
    repeat=rms_data(scaled_change(repeated,bases[low],observed))
    report['base_repeatability_rms_relative']=repeat
    data=p.training_data(p.TRAIN,observed)
    residual=lambda a:p.normalized_complex_residual(a,observed,data.frequency_weights)[0]
    indexS=np.r_[np.arange(0,24*4,4),np.arange(24*4,2*24*4,4)]
    for n in nodes:
        for h in report['fd_steps']:
            # Every side may require four frequency solves. Check the entire
            # Jacobian's known maximum before starting any column.
            ledger.reserve(dimension*2*len(p.TRAIN))
            columns=[];status=[];base_res=residual(bases[n])
            for i,direction in enumerate(basis):
                sides={}
                for sign in (-1,1):
                    try:
                        candidate=state.incremented(direction*(sign*h)).polar_angle_gauge_fixed()[0]
                    except ValueError:
                        continue
                    if p.feasible(candidate,nodes,solve,control.minimum_component_radius_m):
                        sides[sign]=residual(predict(candidate,n,'derivative'))
                if len(sides)==2:
                    col=(sides[1]-sides[-1])/(2*h);kind='central'
                elif 1 in sides:
                    col=(sides[1]-base_res)/h;kind='forward'
                elif -1 in sides:
                    col=(base_res-sides[-1])/h;kind='backward'
                else:
                    report['unresolved_column']=dict(nodes=n,step=h,column=i)
                    save(report)
                    raise p.Obstruction(f'{name}: unresolved finite-difference column; no zero substitution')
                columns.append(col);status.append(kind)
            matrix=np.column_stack(columns)
            key=f'{n}:{h:g}'
            s_matrix=matrix[indexS]*2 # undo 1/sqrt(4) for single-frequency objective
            report['jacobians'][key]=dict(F=matrix,S=s_matrix,stencils=status)
            report['spectra'][key]=dict(S=spectrum(s_matrix)[0],F=spectrum(matrix)[0])
            save(report)
            print('jacobian',name,n,h,'complete',ledger.total,flush=True)
    report['derivative_scale_checks']=[]
    for n in nodes:
        a=report['jacobians'][f'{n}:0.0001']['F'];b=report['jacobians'][f'{n}:5e-05']['F']
        per_column=np.linalg.norm(a-b,axis=0)/np.maximum(np.linalg.norm(b,axis=0),np.finfo(float).tiny)
        passed=bool(np.max(per_column)<=.25)
        report['derivative_scale_checks'].append(dict(nodes=n,relative_column_discrepancy=per_column,passed=passed))
        if not passed:
            save(report);raise p.Obstruction(f'{name}: two-scale derivatives fail inherited 0.25 stability gate')
    # Freeze the weak directions in descending-spectrum order: N-8,...,N-1.
    reference=report['spectra'][f'{low}:0.0001']['S']
    selected=[]
    for rank in reversed(range(dimension)):
        direction=np.asarray(reference['right_vectors'][rank])
        physical,per_unit=physical_direction(state,basis,direction)
        if physical is None:
            report.setdefault('parameterization_only_ranks',[]).append(rank)
        else:
            selected.append((rank,physical,per_unit))
            if len(selected)==8:break
    selected.reverse()
    report['selected_ranks']=[r[0] for r in selected]
    numerical_floor=max(repeat,64*np.finfo(float).eps)
    for rank,direction,per_unit in selected:
        row=dict(rank=rank,direction_for_1mm=direction,normal_rms_m_per_unit_coefficient=per_unit,
                 probes=[],usable=True)
        # All signs/amplitudes and both resolutions: maximum 32 frequency solves.
        ledger.reserve(2*2*2*len(p.TRAIN))
        for amplitude in (.5,1.):
            for sign in (-1,1):
                probe=dict(amplitude_mm=amplitude,sign=sign)
                try:
                    candidate=retrace(state,basis,direction,sign*amplitude)
                    valid=p.feasible(candidate,nodes,solve,control.minimum_component_radius_m)
                except ValueError:
                    valid=False
                probe['feasible']=bool(valid)
                if not valid:
                    row['usable']=False;row['probes'].append(probe);continue
                probe['actual_rms_normal_displacement_mm']=float(normal_rms(state,candidate)*1e3)
                changes={n:scaled_change(predict(candidate,n,'physical_probe'),bases[n],observed) for n in nodes}
                uncertainty=changes[low]-changes[high]
                floorS=max(numerical_floor,float(np.linalg.norm(uncertainty[:,0])))
                floorF=max(numerical_floor,rms_data(uncertainty))
                probe['numerical_uncertainty']=dict(S=floorS,F=floorF)
                for label,n in (('production',low),('refined',high)):
                    ds=float(np.linalg.norm(changes[n][:,0]));df=rms_data(changes[n])
                    usable=ds>=5*floorS and df>=5*floorF
                    # A floor-limited direction is recorded, never an infinite gain.
                    probe[label]=dict(D_S=ds,D_F=df,gain=float(df/ds) if ds>floorS else None,
                                      above_five_times_uncertainty=bool(usable))
                    if ds<=floorS:
                        probe[label]['gain_lower_bound']=df/floorS
                    row['usable'] &= usable
                row['probes'].append(probe)
        if row['usable']:
            row['median_gain']=float(np.median([v['production']['gain'] for v in row['probes']]))
        report['directions'].append(row);save(report)
        print('direction',name,rank,'usable',row['usable'],'gain',row.get('median_gain'),flush=True)
    report['gate']=gate(report['directions']);save(report)
    return report


def run(phase0,output,ledger,record):
    previous=p.benchmark.read(phase0/'preflight.json')
    if previous['status']!='INPUT_AND_RESOLUTION_PASS':
        raise p.Obstruction('phase0 did not pass')
    nodes=previous['selected_nodes'];spec=p.benchmark.read(p.DATA/'scene_spec.json')
    scenes={s['id']:s for s in spec['scenes'] if s['id'] in p.SCENES}
    states={n:p.driver.deserialize_state(p.benchmark.read(phase0/'inputs'/n/'state.json')) for n in p.SCENES}
    solve=p.driver.baseline.iteration01_solve_config()
    control=p.TopologyControllerConfig(**spec['controller'],refined_feasibility_guard=True,feasible_fd_jacobian=True)
    record.update(selected_nodes=nodes,oracle_checks={},evaluation_checks={},scenes={})
    observations={}
    for name in p.SCENES:
        source=p.benchmark.read(phase0/'inputs'/name/'observations.json')
        old=np.array(source['observed_real'])+1j*np.array(source['observed_imag'])
        # Original values are concatenated directly, not regenerated/refitted.
        ledger.reserve(6)
        a=oracle(scenes[name],p.TRAIN[1:],256,solve,ledger)
        b=oracle(scenes[name],p.TRAIN[1:],512,solve,ledger)
        errors=p.relative(a,b)
        record['oracle_checks'][name]=dict(relative_discrepancy=errors,passed=bool(np.max(errors)<=spec['oracle_relative_tolerance']))
        if not record['oracle_checks'][name]['passed']:
            raise p.Obstruction(f'{name}: added training oracle convergence failed')
        observed=np.column_stack((old[:,0],a));observations[name]=observed
        p.write(output/f'{name}_training_observations.json',dict(frequencies_hz=p.TRAIN,
            observed_real=observed.real,observed_imag=observed.imag,
            acquisition_and_material_source=str((phase0/'inputs'/name/'observations.json').relative_to(p.ROOT)),
            source_sha256=p.digest(phase0/'inputs'/name/'observations.json'),old_training_bytes_equal=old[:,0].tobytes()==observed[:,0].tobytes()))
        # Evaluate saved candidate-geometry convergence; scores against truth or
        # held-out data are not used in direction or resolution selection.
        a=p.prediction(states[name],p.EVALUATION,nodes[0],solve,ledger,'evaluation_resolution')
        b=p.prediction(states[name],p.EVALUATION,nodes[1],solve,ledger,'evaluation_resolution')
        errors=p.relative(a,b)
        record['evaluation_checks'][name]=dict(relative_discrepancy=errors,passed=bool(np.max(errors)<=spec['oracle_relative_tolerance']))
        if not record['evaluation_checks'][name]['passed']:
            raise p.Obstruction(f'{name}: evaluation-frequency resolution failed at frozen pair')
        p.write(output/'sensitivity.json',record)
    for name in p.SCENES[:2]:
        def save(scene_record):
            record['scenes'][name]=scene_record
            record['work']=ledger.snapshot()
            p.write(output/'sensitivity.json',record)
        result=measure_scene(name,states[name],observations[name],nodes,solve,control,ledger,save)
        if not result['gate']['passed']:
            raise p.Obstruction(f'{name}: binding information screen failed')
    record['status']='SCREEN_PASS'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase0',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    phase0=args.phase0.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(k)!='1':raise ValueError('single-thread workers required')
    previous=p.benchmark.read(phase0/'preflight.json');spent=previous['work']
    manifest=p.benchmark.read(phase0/'manifest.json')
    for name,expected in manifest['source_sha256'].items():
        if name=='run_top016_preflight.py':continue
        if p.digest(p.ROOT/name)!=expected:raise ValueError(f'phase0 numerical source changed: {name}')
    if p.digest(p.ROOT/'run_top016_preflight.py')!=manifest['source_sha256']['run_top016_preflight.py']:
        raise ValueError('preflight implementation changed after phase0')
    p.write(output/'manifest.json',dict(phase0=str(phase0.relative_to(p.ROOT)),
        phase0_manifest_sha256=p.digest(phase0/'manifest.json'),driver_sha256=p.digest(__file__),
        preflight_driver_sha256=p.digest(p.ROOT/'run_top016_preflight.py'),command=sys.argv,
        prior_attempted_solves=spent['total_attempted'],prior_active_wall_seconds=spent['active_wall_seconds'],
        concurrency=1,threads=1))
    ledger=p.Ledger(cap=5000-spent['total_attempted'],seconds=1200-spent['active_wall_seconds'])
    record=dict(status='IN_PROGRESS')
    try:
        with ledger.instrument():run(phase0,output,ledger,record)
    except p.Obstruction as exc:
        record.update(status='OBSTRUCTION',reason=str(exc),exception_type=type(exc).__name__)
    except Exception as exc:
        record.update(status='IMPLEMENTATION_ERROR',reason=str(exc),exception_type=type(exc).__name__)
        raise
    finally:
        record['work']=ledger.snapshot()
        record['phase01_total_attempted']=spent['total_attempted']+ledger.total
        record['phase01_total_active_wall_seconds']=spent['active_wall_seconds']+record['work']['active_wall_seconds']
        p.write(output/'sensitivity.json',record)
        print(json.dumps(dict(status=record['status'],reason=record.get('reason'),
            solves=record['phase01_total_attempted'],seconds=record['phase01_total_active_wall_seconds'])),flush=True)

if __name__=='__main__':main()
