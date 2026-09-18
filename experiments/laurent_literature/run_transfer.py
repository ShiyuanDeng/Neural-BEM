"""Qualify the numerical transfer separately from the scalar reproduction."""
import argparse
import hashlib
import numpy as np

from experiments.laurent_compression.adapters import (NativeCase, inputs,
    moved_geometry, nodal_reference, parameterization, relative, solve_masked,
    masked_data_derivative)
from experiments.laurent_compression.evaluation import reference_bundle, qualify_native, assess
from experiments.laurent_compression.run_screen import fixture_set, equivalent_radius, directions_for, geometry_record
from experiments.laurent_compression.metrics import paired, GATES, CONTROL_GATES
from .evidence import Evidence
from .transmission import SplitCase, mask_for, principal_log, storage

LABELS=['IDENTITY_ONLY','VERIFIED_SINGULAR_SPLIT','PRINCIPAL_LOG']
MUS=[1.1,1.2,1.4]


def derivative_list(base,view,directions):
    if view.label!='PRINCIPAL_LOG':
        return base
    return [dict(d,principal_log=principal_log(view,dz)) for d,dz in zip(base,directions)]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=['pilot','campaign'],default='pilot')
    args=p.parse_args()
    fixtures=fixture_set()
    a_ref=equivalent_radius(fixtures['star'])
    if args.stage=='pilot':
        fixtures={k:fixtures[k] for k in ['ellipse','asymmetric_star']}
    acq,_=inputs()
    record=Evidence(args.output,dict(stage=args.stage,fixtures=list(fixtures),ka=[2.,5.],
        geometries={name:geometry_record(g) for name,g in fixtures.items()}, acquisition=acq,
        common_frequency_reference_radius=a_ref,gates=GATES,control_gates=CONTROL_GATES,
        mu=MUS,splits=LABELS,cutoffs='qualified original, doubled, 128 (campaign only)',
        restricted_larger_mask_factors=[2,4,8,16] if args.stage=='campaign' else [],
        derivative_directions='LAU-001-R1 four training and two heldout; mask uses none',
        coefficient_bandwidth=128,terms=28,fd_steps=[2e-4,1e-4],
        baseline='LAU-001-R1; scalar JWY2021 reproduction',
        claim='Numerical transmission extension; no scalar-theorem transfer or assembly speed claim'))
    rows,controls,derivative_rows,fd_rows=[],[],[],[]
    for name,geometry in fixtures.items():
        radius=equivalent_radius(geometry)
        named=directions_for(geometry,radius)
        directions=[d for _,d in named]
        for ka in [2.,5.]:
            frequency=ka/(a_ref*2*np.pi*np.sqrt(acq['eps0']*acq['mu0']*acq['exterior']['epsr']))
            key=f'{name}@ka{ka:g}'
            reference=reference_bundle(geometry,acq,frequency,directions,record)
            truth=moved_geometry(geometry,{2:.015*radius/geometry.scale,
                                          4:.010*radius/geometry.scale},1.)
            observed=paired(nodal_reference([parameterization(truth)],frequency,acq,384,record)['y'])
            k0=(16 if ka==2 else 24) if name in ['circle','ellipse'] else (40 if ka==2 else 48)
            cutoffs=[k0,2*k0] if args.stage=='pilot' else [k0,2*k0,128]
            for cutoff in cutoffs:
                case=NativeCase(geometry,acq,frequency,cutoff,128,28,ledger=record)
                base_derivatives=[case.derivative(dz) for dz in directions]
                control,full_dy=qualify_native(case,reference,base_derivatives,record)
                controls.append(dict(case=key,cutoff=cutoff,frequency_hz=frequency,
                    oracle_qualified=reference['qualification']['qualified'],
                    oracle_receiver_error=reference['qualification']['oracle_receiver_error'],
                    oracle_derivative_worst=reference['qualification']['oracle_derivative_worst'],**control))
                if not control['qualified']:
                    record.csv('controls.csv',controls)
                    continue
                for label in LABELS:
                    view=SplitCase(case,label)
                    ds=derivative_list(base_derivatives,view,directions)
                    settings=[(mu,cutoff+1,'literal') for mu in MUS]
                    if cutoff==k0 and args.stage=='campaign':
                        settings += [(1.1,factor*(cutoff+1),'restricted_larger_mask') for factor in [2,4,8,16]]
                    for mu,mask_n,variant in settings:
                        mask=mask_for(view,mu,mask_n)
                        solved=solve_masked(*view.parts(),mask,case.b,case.c,record)
                        metrics,details=assess(view,solved,mask,label,ds,reference,observed,
                            full_dy,qualified=True,directions=directions)
                        cid=f'{key}:K{cutoff}:{label}:mu{mu}:n{mask_n}'
                        digest=hashlib.sha256(mask.tobytes()).hexdigest()
                        np.savez_compressed(record.out/f'mask-{digest}.npz',mask=mask)
                        rows.append(dict(comparison_id=cid,case=key,cutoff=cutoff,split=label,
                            mu=mu,mask_n=mask_n,variant=variant,mask_sha256=digest,
                            original_dense_slots=4*(2*k0+1)**2,
                            **storage(view,mask),**metrics))
                        derivative_rows.extend(dict(comparison_id=cid,**detail) for detail in details)
                if cutoff==k0:
                    # Independent centered differences of each frozen compressed
                    # model in a generic combination of all six directions.
                    for h in [2e-4,1e-4]:
                        # One selected direction per fixture is insufficient for
                        # all modes: use a fixed generic combination, including
                        # the heldout modes, and test each individual analytic
                        # tangent separately in the physical-oracle comparisons.
                        dz={}
                        weights=np.array([1.,-.4,.7,.2,-.5,.3])
                        for weight,d in zip(weights,directions):
                            for j,v in d.items(): dz[j]=dz.get(j,0)+weight*v
                        sides=[NativeCase(moved_geometry(geometry,dz,sign*h),acq,frequency,
                            cutoff,128,28,ledger=record) for sign in [1,-1]]
                        dcase=case.derivative(dz)
                        for label in LABELS:
                            view=SplitCase(case,label)
                            d=dict(dcase,principal_log=principal_log(case,dz))
                            mask=mask_for(view,1.2)
                            base=solve_masked(*view.parts(),mask,case.b,case.c,record)
                            dy=masked_data_derivative(base,view,d,mask,label)
                            vals=[]
                            for side in sides:
                                v=SplitCase(side,label)
                                vals.append(solve_masked(*v.parts(),mask,side.b,side.c,record)['y'])
                            error=relative(paired((vals[0]-vals[1])/(2*h)),paired(dy))
                            fd_rows.append(dict(case=key,split=label,step=h,relative_error=error,
                                                passes=bool(error<1e-4)))
                record.csv('transfer.csv',rows)
                record.csv('controls.csv',controls)
                record.csv('derivatives.csv',derivative_rows)
                record.csv('finite_differences.csv',fd_rows)
                print(f'completed {key} K={cutoff}',flush=True)
    record.finish(comparisons=len(rows),passed=sum(r['passes_all'] for r in rows),
        controls_qualified=sum(r['qualified'] for r in controls),controls=len(controls),
        finite_difference_passed=sum(r['passes'] for r in fd_rows),finite_differences=len(fd_rows),
        compact_passes=[dict(comparison_id=r['comparison_id'],
                            retained_to_original=r['stored_slots']/r['original_dense_slots'])
                       for r in rows if r['passes_all'] and r['stored_slots']<r['original_dense_slots']])


if __name__=='__main__':
    main()
