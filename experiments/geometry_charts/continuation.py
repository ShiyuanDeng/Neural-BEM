"""TA-001: exactly four conditional TG-002 fits with the experimental chart."""
import argparse
from dataclasses import asdict
import gc
from pathlib import Path
from time import perf_counter
import traceback

import numpy as np
import torch

from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.errors import UpdateRefused
from bem_inverse.io import curve_from, digest, portable, read, write
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import fit
from experiments.benchmark import audit as final_check
from experiments.benchmark import campaign
from experiments.cleaned_interface import benchmark as scoring
from .adapter import GeometryAdapter
from .replay import OUTPUT, ROWS, environment, inputs

FOLDER=OUTPUT/'continuation'
EXECUTION=Execution(device='cuda',frequency_threads=1,preparation_device='cpu')


def resources():
    info=environment()
    info['gpu']=dict(name=torch.cuda.get_device_name(),
        max_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
        max_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
        allocator_limit_gib=5.) if torch.cuda.is_initialized() else 'not initialized'
    return info


def check_adapter():
    """Only the requested zero-step, actual B6 FD and failed-closure behavior."""
    checks=[]
    for case,label in ROWS:
        row=read(OUTPUT/'rebuild'/f'{case}.json')
        curve=curve_from(row['accepted'])
        settings,trial=GeometryAdapter().update(.05)
        saved,configuration,stage,config=inputs(case,label)
        space=settings.prepare(curve,stage.update_modes,curve.band)
        zero,_=trial(np.zeros(len(space.orders)),prepared=space)
        direction=np.random.default_rng(42001).normal(size=len(space.orders))
        direction/=np.linalg.norm(direction)
        errors=[]
        for step in (1e-7,5e-8):
            plus,_=trial(step*direction,prepared=space)
            minus,_=trial(-step*direction,prepared=space)
            fd=(plus.coefficients-minus.coefficients)/(2*step)
            exact=space.derivatives@direction
            errors.append(dict(step_m=step,relative_error=float(np.linalg.norm(fd-exact)/np.linalg.norm(exact))))
        same=np.array_equal(zero.coefficients,curve.coefficients)
        passed=same and max(e['relative_error'] for e in errors)<1e-5
        checked=dict(case=case,zero_step_exact=same,derivative_checks=errors,passed=passed)
        if case=='aphex_twin__c4':
            try:
                trial(np.asarray(row['bounded_step_m']),prepared=space)
                checked['closure_exception']='unexpected success'
                checked['passed']=False
            except UpdateRefused as exc:
                checked['closure_exception']=dict(type=type(exc).__name__,reason=exc.reason,detail=exc.detail)
                checked['passed']=checked['passed'] and exc.reason=='chart_closure'
        checks.append(checked)
        print('ADAPTER',checked,flush=True)
    record=dict(checks=checks,passed=all(c['passed'] for c in checks),environment=environment(),
                sources={p.name:digest(p) for p in Path(__file__).parent.glob('*.py')})
    write(FOLDER/'adapter_checks.json',record)
    if not record['passed']:
        raise ValueError('Chart adapter checks failed; do not run fits')


def run(case):
    check=read(FOLDER/'adapter_checks.json')
    if not check['passed']:
        raise ValueError('Adapter checks must pass before fitting')
    # The source map is preserved; report.py can change without altering the fit.
    for name in ('adapter.py','replay.py'):
        if check['sources'][name]!=digest(Path(__file__).parent/name):
            raise ValueError('Numerical driver changed after adapter checks: '+name)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for planned continuation')
    total=torch.cuda.get_device_properties(0).total_memory
    torch.cuda.set_per_process_memory_fraction(5*2**30/total)
    campaign.verify(require_inputs=True)
    settings=portable(dict(solver='modal_muller',geometry_update='ta001_positive_speed_tangent_angle',
                  localization='none',execution=asdict(EXECUTION),policy=asdict(CumulativePolicy()),
                  final_check_seconds=final_check.SECONDS,adapter='experiments.geometry_charts.adapter.GeometryAdapter'))
    campaign.open_run(FOLDER/'chart',[c for c,_ in ROWS],settings,experiment='TA-001 conditional chart continuation')
    case_row=campaign.row(case)
    folder=FOLDER/'chart/runs'/case
    if folder.exists():
        raise FileExistsError('Preserve existing run; the four-fit plan allows no rerun: '+str(folder))
    folder.mkdir(parents=True)
    start=perf_counter()
    write(folder/'run_environment.json',dict(start=resources(),settings=settings))
    try:
        problem=campaign.problem(case)
        physics,forward=campaign._physics('modal_muller',EXECUTION)
        def event(record):
            print(case,record['operation']['label'],record['reason'],record.get('outcome',''),
                  record.get('final_loss',''),flush=True)
            write(folder/'resources.json',resources())
        result=fit(problem,solver='modal_muller',execution=EXECUTION,physics=physics,forward_solve=forward,
                   policy=CumulativePolicy(),geometry_adapter=GeometryAdapter(),
                   localization_adapter=campaign.keep_start,output=folder,on_event=event)
        del physics,forward
        gc.collect()
        torch.cuda.empty_cache()
        physics,forward=campaign._physics('modal_muller',EXECUTION)
        update,trial=GeometryAdapter().update(problem.length_unit_m)
        with geometry_runtime(EXECUTION.geometry):
            checked=final_check.audit(curve_from(result['final_curve']),
                final_check.audited_modes(result['final_stage']),problem,physics,forward,
                update,trial,final_check.SECONDS)
        write(folder/'final_audit.json',checked)
        result.update(final_audit_passed=checked['passed'],relative_residual=checked.get('relative_residual'),
                      audit_units=checked['work']['work_units'],audit_seconds=checked['seconds'],
                      total_units=result['fit_and_localization_units']+checked['work']['work_units'],
                      total_seconds=result['total_seconds']+checked['seconds'],
                      audited_output_seconds=perf_counter()-start)
        # Truth is first read only after fit and independent final check return.
        metrics=scoring.score(case_row,curve_from(result['final_curve']))
        limits=scoring.residual_limits(case_row)
        residual=result['relative_residual']
        result.update(case=case_row,settings=settings,metrics=metrics,residual_limits=limits,
            recovered=bool(checked['passed'] and metrics['rms_mm']<=1 and
                           metrics['hausdorff_upper_mm']<=2 and residual is not None and np.all(residual<=limits)),
            maximum_residual=None if residual is None else float(max(residual)))
    except Exception:
        result=dict(case=case_row,settings=settings,outcome='WORKER_EXCEPTION',recovered=False,
                    traceback=traceback.format_exc())
    result['resources']=resources()
    write(folder/'result.json',result)
    campaign.summarize(FOLDER/'chart')
    print('RESULT',case,result['outcome'],result['recovered'],result.get('metrics'),flush=True)
    print('RESOURCES',result['resources'],flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('step',choices=('check','run'))
    parser.add_argument('--case',choices=[c for c,_ in ROWS])
    args=parser.parse_args()
    if args.step=='check':
        check_adapter()
    else:
        if not args.case:
            parser.error('run requires one --case; commit/push each before the next')
        run(args.case)


if __name__=='__main__':
    main()
