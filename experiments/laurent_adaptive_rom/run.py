"""LAU-004: hierarchical bases, frozen evaluations and explicit refresh decisions."""
import argparse
import hashlib
import json
import resource
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.laurent_compression.adapters import (NativeCase,inputs,moved_geometry,
    nodal_reference,parameterization,relative)
from experiments.laurent_compression.evaluation import reference_bundle,qualify_native
from experiments.laurent_compression.metrics import GATES,CONTROL_GATES,paired
from experiments.laurent_compression.run_screen import (directions_for,equivalent_radius,
    fixture_set,geometry_record,validation_acquisition)
from experiments.laurent_tangent_rom.model import solve,derivative
from experiments.laurent_tangent_rom.run import Record as PreviousRecord,combination,score,hashes as previous_hashes
from .model import ARMS,GUARD_LIMITS,bases,guard,rank_ladder,stability


def hashes():
    return dict(previous_hashes(),**{str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path('experiments/laurent_adaptive_rom').glob('*.py'))})


class Record(PreviousRecord):
    def __init__(self,output,config):
        self.CEILINGS = (dict(assemblies=180,factorizations=2000,rhs_batches=5000,seconds=1800,peak_gib=6.)
            if config['stage']=='pilot' else
            dict(assemblies=280,factorizations=6000,rhs_batches=15000,seconds=1800,peak_gib=6.))
        super().__init__(output,config)
        self.initial = hashes()
        manifest = json.loads((self.out/'manifest.json').read_text())
        manifest['source_hashes'] = self.initial
        self.json('manifest.json',manifest)

    def finish(self,**summary):
        self.check_resources()
        current = hashes()
        drift = [p for p in set(current)|set(self.initial) if current.get(p)!=self.initial.get(p)]
        self.json('summary.json',dict(status='SOURCE_DRIFT' if drift else 'COMPLETE',source_drift=drift,
            work=self.counts,seconds=perf_counter()-self.started,
            peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,**summary))
        self.json('artifact_hashes.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.out.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'})
        if drift:
            raise RuntimeError('LAU-004 measured source drift')


def derivatives(case,directions,record):
    result = []
    for direction in directions:
        record.charge(operator_derivatives=1)
        result.append(case.derivative(direction))
    return result


def select(case,bank,training_derivatives,training_dy,record,key,location):
    selected,rows = {},[]
    for arm,item in bank.items():
        candidates = []
        for rank in rank_ladder(item['protected_rank'],item['snapshot_rank']):
            v = item['v'][:, :rank]
            result = solve(case,v,record)
            field = relative(paired(result['y']),paired(case.y))
            residual = relative(case.a@result['state'],case.b)
            error = max(relative(paired(derivative(result,d)),paired(dy))
                        for d,dy in zip(training_derivatives,training_dy))
            eligible = bool(field<=1e-8 and residual<=1e-8 and error<=1e-5)
            rows.append(dict(case=key,location=location,arm=arm,rank=rank,
                protected_rank=item['protected_rank'],snapshot_rank=item['snapshot_rank'],
                field_error=field,native_residual=residual,training_derivative_error=error,eligible=eligible))
            candidates.append(dict(v=v,rank=rank,eligible=eligible))
        selected[arm] = next((s for s in candidates if s['eligible']),candidates[-1])
        np.savez_compressed(record.out/f'basis-{key}-{location}-{arm}.npz',
            v=selected[arm]['v'],singular_values=item['singular_values'])
    return selected,rows


def check_bound(row,candidate_y,candidate_dy,full_y,full_dy):
    """Audit only: full native outputs never enter guard() or selection here."""
    allowance = 1e-10
    ef = float(np.linalg.norm(paired(candidate_y)-paired(full_y)))
    df = [float(np.linalg.norm(paired(a)-paired(b))) for a,b in zip(candidate_dy,full_dy[:4])]
    checks = [ef<=row['field_absolute_bound']+allowance*np.linalg.norm(paired(full_y))]
    checks += [e<=bound+allowance*np.linalg.norm(paired(truth))
        for e,bound,truth in zip(df,row['derivative_absolute_bounds'],full_dy[:4])]
    return dict(field_absolute_error=ef,derivative_absolute_errors=df,bounds_cover=all(checks))


def run(output,stage):
    acq,_ = inputs()
    fixtures = fixture_set()
    a_ref = equivalent_radius(fixtures['star'])
    names = ['ellipse','asymmetric_star'] if stage=='pilot' else list(fixtures)
    kas = [5.] if stage=='pilot' else [2.,5.]
    config = dict(experiment='LAU-004',stage=stage,fixtures=names,ka=kas,arms=ARMS,
        acquisition=acq,common_radius=a_ref,geometries={k:geometry_record(fixtures[k]) for k in names},
        gates=GATES,control_gates=CONTROL_GATES,guard_limits=GUARD_LIMITS,
        selection_limits=dict(field=1e-8,residual=1e-8,training_derivative=1e-5),
        rank_ladder=[8,12,16,24,32,40,48,56,64,80,96,112,128,144],singular_threshold=1e-12,
        geometry_steps=[-.001,.001,-.005,.005],offset_weights=[1.,-.4,.7,.2],
        evaluation_motion_step=.005,evaluation_motion_weights=[.8,-.6],
        fd_steps=[1e-4,5e-5],fd_weights=[1.,-.4,.7,.2,-.5,.3],
        coefficient_bandwidth=128,refined_bandwidth=160,terms=28,
        bound_readback_roundoff_allowance=1e-10,
        note='Reference-free finite-system guard; dense SVD and assembly retained; development data only.')
    record = Record(output,config)
    rows,details,controls,ranks,fds,windows,timings,guards,policies = [],[],[],[],[],[],[],[],[]
    def checkpoint():
        for name,data in [('comparisons',rows),('derivatives',details),('controls',controls),
                          ('rank_selection',ranks),('finite_differences',fds),('windows',windows),
                          ('timings',timings),('policies',policies)]:
            record.csv(name+'.csv',data)
        record.json('guards.json',guards)
    try:
        for name in names:
            geometry = fixtures[name]
            radius = equivalent_radius(geometry)
            directions = [d for _,d in directions_for(geometry,radius)]
            dz = combination(directions[:4],config['offset_weights'])
            eval_dz = combination(directions[4:],config['evaluation_motion_weights'])
            fd_dz = combination(directions,config['fd_weights'])
            for ka in kas:
                key = f'{name}-ka{ka:g}'
                frequency = ka/(a_ref*2*np.pi*np.sqrt(acq['eps0']*acq['mu0']*acq['exterior']['epsr']))
                cutoff = (16 if ka==2 else 24) if name in ['circle','ellipse'] else (40 if ka==2 else 48)
                truth = moved_geometry(geometry,{2:.015*radius/geometry.scale,4:.010*radius/geometry.scale},1.)
                observed = paired(nodal_reference([parameterization(truth)],frequency,acq,384,record)['y'])
                scenarios = [('anchor',geometry,acq)]
                scenarios += [(f'train_{"minus" if h<0 else "plus"}_{abs(h):g}',moved_geometry(geometry,dz,h),acq)
                              for h in config['geometry_steps']]
                scenarios += [('evaluation_motion',moved_geometry(geometry,eval_dz,.005),acq),
                              ('shifted_sources',geometry,validation_acquisition(acq))]
                anchor_data = None
                for scenario,shape,acquisition in scenarios:
                    case = NativeCase(shape,acquisition,frequency,cutoff,128,28,ledger=record)
                    ds = derivatives(case,directions,record)
                    reference = reference_bundle(shape,acquisition,frequency,directions,record)
                    qualified,full_dy = qualify_native(case,reference,ds,record)
                    controls.append(dict(case=key,scenario=scenario,cutoff=cutoff,
                        frequency_hz=frequency,oracle_qualified=reference['qualification']['qualified'],**qualified))
                    np.savez_compressed(record.out/f'native-{key}-{scenario}.npz',y=paired(case.y),
                        dy=np.array([paired(d) for d in full_dy[:4]]))
                    spectrum = stability(case.a,ds[:4],record)
                    if scenario=='anchor':
                        bank,setup = bases(case,ds[:4],record)
                        selected,chosen_rows = select(case,bank,ds[:4],full_dy[:4],record,key,'anchor')
                        ranks.extend(chosen_rows)
                        anchor_data = case,ds,reference,full_dy,selected
                    else:
                        setup = 0.
                    current_observed = observed
                    if scenario=='shifted_sources':
                        current_observed = paired(nodal_reference([parameterization(truth)],frequency,
                            acquisition,384,record)['y'])
                    current,individual = score(case,ds,reference,current_observed,selected,record,
                        key,scenario+'__frozen',qualified['qualified'])
                    rows.extend(current)
                    details.extend(individual)
                    frozen_by_arm = {r['arm']:r for r in current}
                    refused = []
                    checks = {}
                    for arm,selection in selected.items():
                        result = solve(case,selection['v'],record)
                        g = guard(case.a,case.b,case.c,result,ds[:4],spectrum,record)
                        g.update(check_bound(g,result['y'],[derivative(result,d) for d in ds[:4]],case.y,full_dy))
                        cid = frozen_by_arm[arm]['comparison_id']
                        g.update(comparison_id=cid,case=key,scenario=scenario,arm=arm,phase='frozen',
                            physical_pass=frozen_by_arm[arm]['passes_all'])
                        guards.append(g)
                        checks[arm] = g
                        if not g['accepted']:
                            refused.append(arm)
                    rebuilt = {}
                    if refused:
                        fresh_bank,fresh_seconds = bases(case,ds[:4],record)
                        setup += fresh_seconds
                        rebuilt,chosen_rows = select(case,{arm:fresh_bank[arm] for arm in refused},
                            ds[:4],full_dy[:4],record,key,scenario+'__rebuild')
                        ranks.extend(chosen_rows)
                        current,individual = score(case,ds,reference,current_observed,rebuilt,record,
                            key,scenario+'__rebuilt',qualified['qualified'])
                        rows.extend(current)
                        details.extend(individual)
                        rebuilt_by_arm = {r['arm']:r for r in current}
                    for arm in ARMS:
                        original = frozen_by_arm[arm]
                        if checks[arm]['accepted']:
                            action,delivered = 'REUSE',original
                        else:
                            result = solve(case,rebuilt[arm]['v'],record)
                            g = guard(case.a,case.b,case.c,result,ds[:4],spectrum,record)
                            g.update(check_bound(g,result['y'],[derivative(result,d) for d in ds[:4]],case.y,full_dy))
                            g.update(comparison_id=rebuilt_by_arm[arm]['comparison_id'],case=key,scenario=scenario,
                                arm=arm,phase='rebuilt',physical_pass=rebuilt_by_arm[arm]['passes_all'])
                            guards.append(g)
                            if g['accepted']:
                                action,delivered = 'REBUILD',rebuilt_by_arm[arm]
                            else:
                                fallback = {arm:dict(v=np.eye(len(case.a)),rank=len(case.a),eligible=True)}
                                current,individual = score(case,ds,reference,current_observed,fallback,record,
                                    key,scenario+'__full',qualified['qualified'])
                                rows.extend(current)
                                details.extend(individual)
                                action,delivered = 'FULL_FALLBACK',current[0]
                        policies.append(dict(case=key,scenario=scenario,arm=arm,action=action,
                            frozen_id=original['comparison_id'],delivered_id=delivered['comparison_id'],
                            frozen_rank=original['rank'],delivered_rank=delivered['rank'],dimension=len(case.a),
                            frozen_pass=original['passes_all'],delivered_pass=delivered['passes_all'],
                            delivered_storage_ratio=delivered['reduced_storage_ratio']))
                    timings.append(dict(case=key,scenario=scenario,assembly_seconds=case.assembly_seconds,
                        setup_seconds=setup,stability_seconds=spectrum['seconds']))
                    checkpoint()
                    print(f'{key} {scenario}: '+str({p['arm']:f"{p['action']} {p['frozen_rank']}->{p['delivered_rank']} pass={p['delivered_pass']}"
                        for p in policies[-3:]}),flush=True)
                anchor,ds_anchor,reference,full_dy,selected = anchor_data
                refined = NativeCase(geometry,acq,frequency,cutoff,160,28,ledger=record)
                refined_qual,refined_dy = qualify_native(refined,reference,derivatives(refined,directions,record),record)
                windows.append(dict(case=key,field_error=relative(paired(refined.y),paired(anchor.y)),
                    derivative_error=max(relative(paired(a),paired(b)) for a,b in zip(refined_dy,full_dy)),
                    qualified=refined_qual['qualified']))
                dfd = derivatives(anchor,[fd_dz],record)[0]
                for h in config['fd_steps']:
                    sides = [NativeCase(moved_geometry(geometry,fd_dz,sign*h),acq,frequency,
                        cutoff,128,28,ledger=record) for sign in (1,-1)]
                    for arm,selection in selected.items():
                        base = solve(anchor,selection['v'],record)
                        vals = [solve(side,selection['v'],record)['y'] for side in sides]
                        err = relative(paired((vals[0]-vals[1])/(2*h)),paired(derivative(base,dfd)))
                        fds.append(dict(case=key,arm=arm,step=h,relative_error=err,passes=bool(err<1e-4)))
                checkpoint()
        false_accepts = [g['comparison_id'] for g in guards if g['accepted'] and not g['physical_pass']]
        reuse = [p for p in policies if p['action']=='REUSE' and p['scenario']!='anchor'
                 and p['arm']!='JOINT_TANGENT' and p['frozen_rank']<=p['dimension']/2 and p['delivered_pass']]
        released = (all(r['qualified'] for r in controls) and all(r['passes'] for r in fds)
            and all(g['bounds_cover'] for g in guards) and not false_accepts and bool(reuse)
            and all(w['qualified'] and w['field_error']<1e-8 and w['derivative_error']<1e-6 for w in windows))
        record.finish(comparisons=len(rows),passed=sum(r['passes_all'] for r in rows),
            controls=len(controls),controls_qualified=sum(r['qualified'] for r in controls),
            finite_differences=len(fds),finite_difference_passed=sum(r['passes'] for r in fds),
            guard_evaluations=len(guards),bounds_covered=sum(g['bounds_cover'] for g in guards),
            guard_false_accepts=false_accepts,guard_conservative_rejections=sum(not g['accepted'] and g['physical_pass'] for g in guards),
            policy_count=len(policies),delivered_passed=sum(p['delivered_pass'] for p in policies),
            policy_actions={action:sum(p['action']==action for p in policies) for action in ['REUSE','REBUILD','FULL_FALLBACK']},
            compact_nonanchor_reuses=[p['delivered_id'] for p in reuse],campaign_released=released,
            decision='RELEASE_CAMPAIGN' if stage=='pilot' and released else 'CLOSEOUT')
    except Exception as exc:
        record.json('failure.json',dict(error_type=type(exc).__name__,error=str(exc),work=record.counts,
                    seconds=perf_counter()-record.started))
        raise


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['pilot','campaign'],default='pilot')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    run(args.output,args.stage)
