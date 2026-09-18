"""Bounded LAU-003 screen; evaluation data never constructs/selects the basis."""
import argparse
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np

from experiments.laurent_compression.adapters import (NativeCase, inputs, moved_geometry,
    nodal_reference, parameterization, relative)
from experiments.laurent_compression.evaluation import reference_bundle, qualify_native
from experiments.laurent_compression.metrics import (Ledger, GATES, CONTROL_GATES, acceptance,
    cancellation_allowance, lifted_residual, objective, objective_derivative,
    objective_derivative_passes, paired)
from experiments.laurent_compression.run_screen import (directions_for, equivalent_radius,
    fixture_set, geometry_record, source_hashes, validation_acquisition, write_csv)
from .model import ARMS, bases, derivative, rank_ladder, solve, storage


def hashes():
    return dict(source_hashes(), **{str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path('experiments/laurent_tangent_rom').glob('*.py'))})


class Record(Ledger):
    CEILINGS = dict(assemblies=180, factorizations=1200, rhs_batches=2500, seconds=1800, peak_gib=6.)

    def __init__(self, output, config):
        super().__init__()
        self.out = Path(output)
        self.out.mkdir(parents=True, exist_ok=False)
        self.initial = hashes()
        self.json('config.json', config)
        self.json('manifest.json', dict(source_hashes=self.initial,
            started_utc=datetime.now(timezone.utc).isoformat(), command=sys.argv,
            commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
            dirty=subprocess.check_output(['git','status','--short'],text=True),
            python=platform.python_version(), platform=platform.platform(),
            threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
            load=os.getloadavg(), ceilings=self.CEILINGS))

    def json(self, name, value):
        (self.out/name).write_text(json.dumps(value, indent=2, default=float, allow_nan=False)+'\n')

    def csv(self, name, rows):
        write_csv(self.out/name, rows)

    def finish(self, **summary):
        self.check_resources()
        final = hashes()
        drift = [p for p in set(final)|set(self.initial) if final.get(p)!=self.initial.get(p)]
        self.json('summary.json', dict(status='SOURCE_DRIFT' if drift else 'COMPLETE',
            source_drift=drift, work=self.counts, seconds=perf_counter()-self.started,
            peak_gib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20, **summary))
        self.json('artifact_hashes.json', {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.out.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'})
        if drift:
            raise RuntimeError('Source changed during LAU-003 measurement')


def combination(directions, weights):
    dz = {}
    for direction, weight in zip(directions, weights):
        for j, value in direction.items():
            dz[j] = dz.get(j, 0) + weight*value
    norm = np.sqrt(sum(abs(v)**2 for v in dz.values()))
    target_norm = np.sqrt(sum(abs(v)**2 for v in directions[0].values()))
    return {j:v*target_norm/norm for j,v in dz.items()}


def select(case, bank, ds, full_dy, record, key):
    """Select from the native anchor and training derivatives ONLY."""
    selected, rows = {}, []
    for arm in ARMS:
        candidates = []
        for rank in rank_ladder(bank[arm]['snapshot_rank']):
            v = bank[arm]['v'][:, :rank]
            result = solve(case, v, record)
            field = relative(paired(result['y']), paired(case.y))
            residual = relative(case.a@result['state'], case.b)
            error = max(relative(paired(derivative(result,d)),paired(truth))
                        for d,truth in zip(ds[:4],full_dy[:4]))
            row = dict(case=key, arm=arm, rank=rank, snapshot_rank=bank[arm]['snapshot_rank'],
                field_error=field, native_residual=residual, training_derivative_error=error,
                eligible=bool(field<=1e-8 and residual<=1e-8 and error<=1e-5))
            rows.append(row)
            candidates.append((row,v))
        picked = next((c for c in candidates if c[0]['eligible']),candidates[-1])
        selected[arm] = dict(v=picked[1], rank=picked[0]['rank'], eligible=picked[0]['eligible'])
        np.savez_compressed(record.out/f'basis-{key}-{arm}.npz', v=picked[1],
                            singular_values=bank[arm]['singular_values'])
    return selected, rows


def score(case, ds, reference, observed, selected, record, key, scenario, qualified):
    rows, details = [], []
    for arm, selection in selected.items():
        tic = perf_counter()
        result = solve(case, selection['v'], record)
        dys = [derivative(result,d) for d in ds]
        elapsed = perf_counter()-tic
        y, ref_y = paired(result['y']),paired(reference['fine']['y'])
        field = relative(y,ref_y)
        residual = lifted_residual(result['state'], reference['fine'], case.cutoff)
        loss, r = objective(y,observed)
        _, rr = objective(ref_y,observed)
        cid = f'{key}-{scenario}-{arm}'
        current = []
        for index,(actual,truth) in enumerate(zip(dys,reference['dy'])):
            a,b = paired(actual),paired(truth)
            check = objective_derivative_passes(objective_derivative(r,a),
                objective_derivative(rr,b),cancellation_allowance(rr,b))
            current.append(dict(comparison_id=cid,direction_index=index,heldout=index>=4,
                data_derivative_error=relative(a,b),**check))
        errors = [d['data_derivative_error'] for d in current]
        rows.append(dict(comparison_id=cid,case=key,scenario=scenario,arm=arm,
            rank=selection['rank'],dimension=len(case.a),rank_selection_passed=selection['eligible'],
            data_error=field,full_matrix_data_error=relative(result['y'],reference['fine']['y']),
            lifted_residual=residual,loss=loss,worst_training_derivative_error=max(errors[:4]),
            worst_heldout_derivative_error=max(errors[4:]),
            worst_data_derivative_error=max(errors),projection_solve_six_tangents_seconds=elapsed,
            **storage(len(case.a),selection['rank'],case.b.shape[1],case.c.shape[0]),
            **acceptance(field,residual,max(errors[:4]),max(errors[4:]),
                all(d['passes'] for d in current),qualified=qualified)))
        details.extend(current)
        np.savez_compressed(record.out/f'outputs-{cid}.npz', y=y,reference_y=ref_y,
            dy=np.array([paired(d) for d in dys]),reference_dy=np.array([paired(d) for d in reference['dy']]),
            observed=observed)
    return rows,details


def run(output, stage):
    acq,_ = inputs()
    fixtures = fixture_set()
    a_ref = equivalent_radius(fixtures['star'])
    names = ['ellipse','asymmetric_star'] if stage=='pilot' else list(fixtures)
    kas = [5.] if stage=='pilot' else [2.,5.]
    config = dict(experiment='LAU-003',stage=stage,fixtures=names,ka=kas,
        geometries={k:geometry_record(fixtures[k]) for k in names}, acquisition=acq,
        common_radius=a_ref,arms=ARMS,gates=GATES,control_gates=CONTROL_GATES,
        rank_selection=dict(field=1e-8,residual=1e-8,training_derivative=1e-5,svd=1e-12),
        geometry_offsets=[-.005,.005],offset_weights=[1.,-.4,.7,.2],
        fd_steps=[2e-4,1e-4],fd_weights=[1.,-.4,.7,.2,-.5,.3],
        coefficient_bandwidth=128,refined_bandwidth=160,terms=28,
        scenarios=['anchor','offset_minus','offset_plus','shifted_sources'],
        note='Development feasibility only; full dense assembly retained; no speed or inverse recovery claim.')
    record = Record(output,config)
    rows,details,controls,ranks,fds,windows,timings = [],[],[],[],[],[],[]
    try:
        for name in names:
            geometry = fixtures[name]
            radius = equivalent_radius(geometry)
            named = directions_for(geometry,radius)
            directions = [d for _,d in named]
            dz = combination(directions[:4],config['offset_weights'])
            fd_direction = combination(directions,config['fd_weights'])
            for ka in kas:
                frequency = ka/(a_ref*2*np.pi*np.sqrt(acq['eps0']*acq['mu0']*acq['exterior']['epsr']))
                key = f'{name}-ka{ka:g}'
                cutoff = (16 if ka==2 else 24) if name in ['circle','ellipse'] else (40 if ka==2 else 48)
                anchor = NativeCase(geometry,acq,frequency,cutoff,128,28,ledger=record)
                ds_anchor = [anchor.derivative(d) for d in directions]
                reference = reference_bundle(geometry,acq,frequency,directions,record)
                control,full_dy = qualify_native(anchor,reference,ds_anchor,record)
                bank,basis_seconds = bases(anchor,ds_anchor[:4],record)
                selected,new_ranks = select(anchor,bank,ds_anchor,full_dy,record,key)
                ranks.extend(new_ranks)
                timings.append(dict(case=key,anchor_assembly_seconds=anchor.assembly_seconds,
                                    basis_seconds=basis_seconds))
                truth = moved_geometry(geometry,{2:.015*radius/geometry.scale,4:.010*radius/geometry.scale},1.)
                observed = paired(nodal_reference([parameterization(truth)],frequency,acq,384,record)['y'])
                scenarios = [('anchor',geometry,acq),
                    ('offset_minus',moved_geometry(geometry,dz,-.005),acq),
                    ('offset_plus',moved_geometry(geometry,dz,.005),acq),
                    ('shifted_sources',geometry,validation_acquisition(acq))]
                for scenario,shape,acquisition in scenarios:
                    if scenario=='anchor':
                        case,ds,ref,qual = anchor,ds_anchor,reference,control
                    else:
                        case = NativeCase(shape,acquisition,frequency,cutoff,128,28,ledger=record)
                        ds = [case.derivative(d) for d in directions]
                        ref = reference_bundle(shape,acquisition,frequency,directions,record)
                        qual,_ = qualify_native(case,ref,ds,record)
                    current_observed = observed
                    if scenario=='shifted_sources':
                        current_observed = paired(nodal_reference([parameterization(truth)],frequency,
                                                                 acquisition,384,record)['y'])
                    controls.append(dict(case=key,scenario=scenario,cutoff=cutoff,
                        frequency_hz=frequency,oracle_qualified=ref['qualification']['qualified'],**qual))
                    current,individual = score(case,ds,ref,current_observed,selected,record,key,scenario,qual['qualified'])
                    rows.extend(current)
                    details.extend(individual)
                # Window refinement is an independent axis, never a basis-training sample.
                refined = NativeCase(geometry,acq,frequency,cutoff,160,28,ledger=record)
                refined_ds = [refined.derivative(d) for d in directions]
                refined_qual,refined_dy = qualify_native(refined,reference,refined_ds,record)
                windows.append(dict(case=key,field_error=relative(paired(refined.y),paired(anchor.y)),
                    derivative_error=max(relative(paired(a),paired(b)) for a,b in zip(refined_dy,full_dy)),
                    qualified=refined_qual['qualified']))
                derivative_fd = anchor.derivative(fd_direction)
                for h in config['fd_steps']:
                    sides = [NativeCase(moved_geometry(geometry,fd_direction,sign*h),acq,frequency,
                              cutoff,128,28,ledger=record) for sign in (1,-1)]
                    for arm,selection in selected.items():
                        base = solve(anchor,selection['v'],record)
                        values = [solve(side,selection['v'],record)['y'] for side in sides]
                        err = relative(paired((values[0]-values[1])/(2*h)),paired(derivative(base,derivative_fd)))
                        fds.append(dict(case=key,arm=arm,step=h,relative_error=err,passes=bool(err<1e-4)))
                for filename,data in [('comparisons',rows),('derivatives',details),('controls',controls),
                                      ('rank_selection',ranks),('finite_differences',fds),('windows',windows),('timings',timings)]:
                    record.csv(filename+'.csv',data)
                compact = [r['arm'] for r in rows if r['case']==key and r['scenario']=='anchor'
                           and r['passes_all'] and r['rank_fraction']<=.5]
                print(f'{key}: selected '+str({k:v['rank'] for k,v in selected.items()})+
                      f'; compact anchor passes {compact}',flush=True)
        pilot_gate = (all(r['qualified'] for r in controls) and all(r['passes'] for r in fds)
            and all(r['qualified'] and r['field_error']<1e-8 and r['derivative_error']<1e-6 for r in windows)
            and any(r['case']=='asymmetric_star-ka5' and r['scenario']=='anchor' and r['arm']!='FORWARD'
                    and r['passes_all'] and r['rank_fraction']<=.5 for r in rows))
        record.finish(comparisons=len(rows),passed=sum(r['passes_all'] for r in rows),
            controls=len(controls),controls_qualified=sum(r['qualified'] for r in controls),
            finite_differences=len(fds),finite_difference_passed=sum(r['passes'] for r in fds),
            pilot_gate=pilot_gate,
            compact_passes=[r['comparison_id'] for r in rows if r['passes_all'] and r['rank_fraction']<=.5],
            decision='Continue to campaign' if stage=='pilot' and pilot_gate else 'Assess frozen contract')
    except Exception as exc:
        record.json('failure.json',dict(error_type=type(exc).__name__,error=str(exc),work=record.counts,
                    seconds=perf_counter()-record.started))
        raise


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--stage',choices=['pilot','campaign'],default='pilot')
    args = parser.parse_args()
    run(args.output,args.stage)
