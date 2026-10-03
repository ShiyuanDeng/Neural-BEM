"""RB-001 qualification and continuation of all Stage-A-qualified tails."""
import argparse
from dataclasses import replace
from pathlib import Path
import resource
import subprocess
import sys
import tarfile
from time import perf_counter

import numpy as np

from bem_inverse.continuation import lm_backend as lm
from bem_inverse.geometry import ProjectedUpdate
from bem_inverse.io import curve_from, curve_record, digest, read, write
from bem_inverse.physics import Execution
from bem_inverse.runner import FitResume, fit
from experiments.cleaned_interface.fm001 import full_problem, scored
from experiments.cleaned_interface.fm002 import FactorialPrefix
from . import rb001 as a


def phase_seal(output, folder):
    if folder.exists():
        raise FileExistsError('Preserve previous phase: '+str(folder))
    a.verify_archive()
    folder.mkdir(parents=True)
    paths=sorted(set(a.ROOT.glob('solvers/**/*.py'))|set(a.ROOT.glob('experiments/cleaned_interface/*.py'))|
        set(a.ROOT.glob('experiments/relaxed_bie/*.py'))|set(a.ROOT.glob('pytest/bem_inverse/*.py'))|{a.PLAN})
    with tarfile.open(folder/'sources.tar.gz','w:gz') as archive:
        for path in paths:
            archive.add(path,arcname=str(path.relative_to(a.ROOT)),recursive=False)
    manifest=dict(sources={str(p.relative_to(a.ROOT)):digest(p) for p in paths},
        source_archive_sha256=digest(folder/'sources.tar.gz'),stage_a_manifest_sha256=digest(output/'manifest.json'),
        stage_a_artifacts={str(p.relative_to(output)):digest(p) for p in sorted((output/'stage_a').rglob('*')) if p.is_file()},
        stage_a_summary_sha256=digest(output/'stage_a.json'))
    write(folder/'manifest.json',manifest)
    return manifest


def verify_phase(output):
    folder=output/'qualification'
    manifest=read(folder/'manifest.json')
    for name,expected in manifest['sources'].items():
        if digest(a.ROOT/name)!=expected:
            raise ValueError('Changed qualified source: '+name)
    if digest(folder/'sources.tar.gz')!=manifest['source_archive_sha256']:
        raise ValueError('Changed qualification source archive')
    for name,expected in manifest['stage_a_artifacts'].items():
        if digest(output/name)!=expected:
            raise ValueError('Changed Stage-A artifact: '+name)
    if digest(output/'stage_a.json')!=manifest['stage_a_summary_sha256']:
        raise ValueError('Changed Stage-A summary')
    a.verify_archive()
    return manifest


def checkpoint(output, case, arm, label):
    problem,stage,config,entry,entry_work,original=a.inputs(case,arm,label)
    folder=output/'stage_a'/case/arm/'current'
    replay=read(folder/'stage.json')
    saved=read(folder/'resume_state.json')
    evaluations=read(folder/'evaluations.json')
    data=np.load(folder/'fields.npz')
    base=curve_from(saved['curve'])
    value=lm.Evaluation(base,saved['loss'],saved['relative_l2'],data['base_residual'],data['base_prediction'])
    # Cache only values computed before the interrupted iteration. The failed
    # proposal's fields are diagnostic evidence, never free continuation work.
    failed_index=max(i for i,e in enumerate(evaluations) if e['category']=='candidate')
    observed=np.column_stack([o.scattered.reshape(-1) for o in problem.real])
    cache={}
    for i,e in enumerate(evaluations[:failed_index]):
        if e['nodes']!=stage.refined_nodes:
            continue
        curve=curve_from(e['curve'])
        prediction=data[f'prediction_{i}']
        residual=lm.normalize(prediction-observed,observed,stage.weights,config.residual_floor)
        cache[curve.coefficients.tobytes()]=lm.Evaluation(curve,e['loss'],e['relative_l2'],residual,prediction)
    history=replay['history']
    work=original['history'][-1]['work']
    update=ProjectedUpdate(problem.length_unit_m)
    cp=lm.StageCheckpoint(lm.checkpoint_signature(stage,problem.contrast,config,update),stage,value,
        data['jacobian'],data['gradient'],saved['iteration'],saved['next_damping'],saved['initial_loss'],
        saved['scale'],work,history,[t for t in replay['trials'] if t['iteration']<=saved['iteration']],
        replay['acceptance_checks'][:-1],cache)
    data.close()
    return problem,stage,config,cp,original


def resume_policy(output, case, arm, label, physics):
    problem,stage,config,cp,original=checkpoint(output,case,arm,label)
    policy=FactorialPrefix(damped_prefix=False,relaxation=arm=='R1')
    folder=a.ARCHIVE/'runs'/case/arm
    old=read(folder/'result.json')
    decisions=read(folder/'decisions.json')['decisions']
    entered=next(i for i,d in enumerate(decisions) if d['operation']['label']==label and
                 d['reason']=='resolved stage entered')
    queue=[]
    for op in policy.operations(problem,physics)[1:-1]:
        if op.kind=='frontier':
            done=next((d for d in decisions[:entered] if d['operation']['label']==op.label and 'measured' in d),None)
            if done is not None:
                queue.extend(policy.tail(problem,physics,done['measured']['frontier']))
                continue
        queue.append(op)
    index=next(i for i,op in enumerate(queue) if op.label==label)
    queue=queue[index:]
    queue[0]=replace(queue[0],stage=stage,optimizer=config)
    states=read(folder/'accepted.json')['states']
    prior_states=[s for s in states if s['stage']!=label or s['iteration']<=cp.iteration]
    initial_audit=read(folder/'initial_audit.json')
    # Historical initial audit remains evidence, but is not charged as fresh work.
    initial_audit=dict(initial_audit,reused_historical=True,original_work=initial_audit['work'],
                       work=dict(work_units=0),seconds=0.)
    resume=FitResume(cp,tuple(queue),tuple(old['stages'][:-1]),tuple(decisions[:entered]),
        tuple(prior_states),old['localization'],initial_audit)
    return problem,policy,resume,original


def qualify(output):
    folder=output/'qualification'
    phase_seal(output,folder)
    started=perf_counter()
    command=[sys.executable,'-m','pytest','pytest/bem_inverse','experiments/cleaned_interface',
             'experiments/shape_continuation','pytest/gpr_bem_kress','pytest/ordered_boundary',
             'experiments/relaxed_bie','-q']
    with (folder/'tests.log').open('w') as log:
        process=subprocess.run(command,cwd=a.ROOT,stdout=log,stderr=subprocess.STDOUT)
    record=dict(passed=False,command=command,test_returncode=process.returncode,
                tests_seconds=perf_counter()-started,replays=[])
    write(folder/'result.json',record)
    if process.returncode:
        raise RuntimeError('Qualification tests failed; preserve the phase and inspect tests.log')
    budget=a.Budget(units=4000,seconds=1800)
    for case,arm,label in a.CASES:
        print('QUALIFY_DEFAULT',case,arm,flush=True)
        problem,stage,config,entry,entry_work,original=a.inputs(case,arm,label)
        physics=a.MeteredPhysics(Execution(),budget)
        actual,fields=a.replay(lm,problem,stage,config,entry,entry_work,physics,folder/'default'/case/arm)
        historical=a.compare(original,actual)
        old=output/'stage_a'/case/arm/'archived'
        values=read(old/'evaluations.json')
        with np.load(old/'fields.npz') as data:
            for i,value in enumerate(values):
                value['prediction']=data[f'prediction_{i}']
        archived_fields=dict(evaluations=values)
        field_gate=a.compare(read(old/'stage.json'),actual,archived_fields,fields)
        problem,stage,config,cp,original=checkpoint(output,case,arm,label)
        ledger=lm.Ledger.restore(cp.work,seconds=1800)
        resumed=lm.fit_stage(cp.current.curve,stage,problem.contrast,ProjectedUpdate(problem.length_unit_m),
                            config,ledger,physics=physics,resume=cp)
        row=dict(case=case,arm=arm,historical=historical,field_gate=field_gate,
            resume=dict(outcome=resumed.outcome,accepted_steps=resumed.accepted_steps,
                maximum_coefficient_error=float(np.max(np.abs(resumed.curve.coefficients-curve_from(original['curve']).coefficients))),
                same_trials=resumed.trials==actual['trials'],same_work=resumed.work['work_units']==original['work']['work_units'],
                same_checks=resumed.acceptance_checks==actual['acceptance_checks']))
        row['passed']=bool(historical['passed'] and field_gate['passed'] and
            row['resume']['outcome']==original['outcome'] and row['resume']['accepted_steps']==original['accepted_steps'] and
            row['resume']['maximum_coefficient_error']<=1e-9 and row['resume']['same_trials'] and
            row['resume']['same_work'] and row['resume']['same_checks'])
        record['replays'].append(row)
        record.update(seconds=perf_counter()-started,budget=budget.snapshot())
        write(folder/'result.json',record)
        print('QUALIFY_DEFAULT_RESULT',case,arm,row['passed'],row['resume'],flush=True)
        if not row['passed']:
            raise RuntimeError('Frozen default/resume replay gate failed')
    verify_phase(output)
    record.update(passed=True,seconds=perf_counter()-started,manifest_sha256=digest(folder/'manifest.json'),
                  tests_sha256=digest(folder/'tests.log'),budget=budget.snapshot())
    write(folder/'result.json',record)


def continue_tails(output):
    verify_phase(output)
    qualification=read(output/'qualification/result.json')
    if not qualification['passed'] or qualification['manifest_sha256']!=digest(output/'qualification/manifest.json'):
        raise ValueError('Current implementation requires complete qualification')
    stage_a=read(output/'stage_a.json')
    remaining=10800-stage_a['budget']['seconds']-qualification['seconds']
    budget=a.Budget(units=4*13412+2000,seconds=remaining)
    started=perf_counter()
    rows=[]
    for case,arm,label in a.CASES:
        gate=next(r for r in stage_a['rows'] if r['case']==case and r['arm']==arm)
        if not gate['continuation_gate']:
            rows.append(dict(case=case,arm=arm,continued=False,reason='Stage-A gate failed'))
            continue
        verify_phase(output)
        folder=output/'runs'/case/arm
        if folder.exists():
            raise FileExistsError('Preserve prior/incomplete continuation: '+str(folder))
        low=a.MeteredPhysics(Execution(),budget)
        high=a.MeteredPhysics(Execution(frequency_threads=1,resolution=1024),budget)
        problem,policy,resume,original=resume_policy(output,case,arm,label,low)
        descriptor=next(r for r in a.b.descriptors() if r['id']==case)
        _,limits=full_problem(descriptor,a.CATALOGS)
        print('CONTINUE',case,arm,'historical',resume.stage.work['work_units'],resume.stage.work['seconds'],flush=True)
        gpu_before=subprocess.check_output(['nvidia-smi'],text=True)
        import torch
        torch.cuda.reset_peak_memory_stats()
        arm_started=perf_counter()
        result=fit(problem,physics=low,policy=policy,resume=resume,output=folder,
            resolution_response=lm.ResolutionResponse(1024,2048,high),
            on_event=lambda event: print(case,arm,event['operation']['label'],event['reason'],flush=True))
        result=scored(descriptor,result,limits)
        result.update(arm=arm,continued=True,fresh_seconds=perf_counter()-arm_started,
            qualification_manifest_sha256=digest(output/'qualification/manifest.json'),
            stage_a_result_sha256=digest(output/'stage_a'/case/arm/'result.json'),
            execution_receipts=dict(original=low.receipt(),finer=high.receipt()),
            memory=dict(cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                process_maximum_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            gpu_before=gpu_before,gpu_after=subprocess.check_output(['nvidia-smi'],text=True))
        write(folder/'result.json',result)
        rows.append(dict(case=case,arm=arm,continued=True,outcome=result['outcome'],detail=result['detail'],
            recovered=result['recovered'],paired_recovered=result['paired_recovered'],metrics=result['metrics'],
            maximum_residual=result['maximum_residual'],promoted=result['resolution_promoted'],
            fresh_seconds=result['fresh_seconds'],fresh_fit_units=result['fresh_fit_units'],
            fit_units=result['fit_and_localization_units'],fit_seconds=result['fit_and_localization_seconds'],
            initial_rms_mm=read(a.ARCHIVE/'runs'/case/arm/'result.json')['metrics']['rms_mm']))
        write(output/'continuation.json',dict(rows=rows,completed=len(rows),scheduled=4,
            seconds=perf_counter()-started,budget=budget.snapshot(),
            numerical_seconds=stage_a['budget']['seconds']+qualification['seconds']+perf_counter()-started))
        print('CONTINUATION_RESULT',case,arm,result['outcome'],result['recovered'],result['metrics'],flush=True)
    verify_phase(output)
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('qualify','continue'))
    parser.add_argument('--output',type=Path,default=a.OUTPUT)
    args=parser.parse_args()
    (qualify if args.command=='qualify' else continue_tails)(args.output)


if __name__=='__main__':
    main()
