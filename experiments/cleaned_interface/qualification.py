"""Bounded extraction controls, separate from the one production policy.

The SPD-016 two-pair check stops the *same* executable policy after M37 to
match the original D experiment. It is never selected by a reconstruction
scene. The all-36 runner always uses the complete cumulative policy.
"""
from dataclasses import replace
from pathlib import Path
import numpy as np

from . import benchmark as b
from .io import read, write, digest, portable
from .physics import Execution
from .policy import CumulativePolicy
from .runner import fit


class DPrefixQualification(CumulativePolicy):
    def operations(self,problem,physics):
        return tuple(op for op in super().operations(problem,physics) if op.kind!='frontier')


def _curve(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def _relative(a,c):
    a,c=np.asarray(a),np.asarray(c)
    if a.shape!=c.shape:
        return float('inf')
    return float(np.linalg.norm(a-c)/max(np.linalg.norm(c),1e-300))


def compare(candidate,reference):
    """Original SPD-016 quality/work gates; no runtime claim across archived hosts."""
    candidate,reference=Path(candidate),Path(reference)
    a,c=read(candidate/'result.json'),read(reference/'result.json')
    aa,cc=read(candidate/'accepted.json')['states'],read(reference/'accepted.json')['states']
    sa,sc=a['stages'],c['stages']
    key=lambda s:(s['stage'],s['M'],s.get('K_geometry',s.get('K')),s['outcome'],s['stop'],s['accepted_steps'])
    gates=dict(same_stages=[key(s) for s in sa]==[key(s) for s in sc],
        same_outcome_recovery=(a['outcome'],a['recovered'])==(c['outcome'],c['recovered']),
        same_audits=(a['initial_audit_passed'],a['final_audit_passed'])==
                    (c['initial_audit_passed'],c['final_audit_passed']),
        same_localization=a['localization']['parameters_m']==c['localization']['parameters_m'],
        same_work=a['fit_and_localization_units']==c['fit_and_localization_units'],
        same_accepted_indices=[(s['stage'],s['iteration'],s['M'],s['units']) for s in aa]==
                              [(s['stage'],s['iteration'],s['M'],s['units']) for s in cc])
    errors=dict(final_curve_relative=_relative(_curve(a['final_curve']),_curve(c['final_curve'])),
        endpoint_rms_absolute=abs(a['metrics']['rms_mm']-c['metrics']['rms_mm']),
        residual_relative=_relative(a['relative_residual'],c['relative_residual']),
        maximum_accepted_curve_relative=max((_relative(_curve(x['curve']),_curve(y['curve']))
            for x,y in zip(aa,cc)),default=float('inf')) if len(aa)==len(cc) else float('inf'),
        maximum_stage_loss_relative=max((abs(x['final_loss']-y['final_loss'])/max(abs(y['final_loss']),1e-300)
            for x,y in zip(sa,sc)),default=float('inf')) if len(sa)==len(sc) else float('inf'))
    decisions=[]
    for x,y in zip(sa,sc):
        if x['stage']!=y['stage']:
            decisions.append(False)
            continue
        ax,cy=read(candidate/(x['stage']+'.json')),read(reference/(y['stage']+'.json'))
        trial=lambda r:[(v.get('iteration'),v.get('backtrack'),v.get('status')) for v in r['trials']]
        decisions.append(trial(ax)==trial(cy) and
            [v['accepted'] for v in ax['acceptance_checks']]==[v['accepted'] for v in cy['acceptance_checks']] and
            x['work']['stage_units']==y['work']['stage_units'])
    gates.update(same_decisions=bool(decisions) and all(decisions),
        accepted_curves=errors['maximum_accepted_curve_relative']<=1e-7,
        stage_losses=errors['maximum_stage_loss_relative']<=1e-7,
        endpoint_rms=errors['endpoint_rms_absolute']<=1e-5,
        residuals=errors['residual_relative']<=1e-7)
    return dict(quality_pass=all(gates.values()),gates=gates,errors=errors)


def spd_pairs(output,execution):
    """Four full D attempts, each within the existing 13412-unit/1800-second cap."""
    output=Path(output)
    manifest=b.verify(output)
    if execution.device=='cpu':
        raise ValueError('The SPD GPU qualification needs --device auto or cuda with a visible GPU')
    from gpr_bem_kress.cuda_assembly import available
    if not available():
        raise RuntimeError('SPD-016 cost qualification requires an available GPU')
    selected=('far__shifted_star','modal__c13.3__new_asymmetric')
    rows=[]
    for case_id in selected:
        case=next(r for r in manifest['cases'] if r['id']==case_id)
        problem=b.fitting_problem(case,output)
        folders={}
        for mode in ('spd016','reference'):
            folder=output/'spd_pairs'/mode/case_id
            folders[mode]=folder
            if (folder/'result.json').exists():
                continue
            if folder.exists():
                raise FileExistsError('Partial qualification retained: '+str(folder))
            # Auto allows the explicit reference mode's real CUDA + damped CPU.
            settings=replace(execution,device='auto',acceleration=mode)
            result=fit(problem,execution=settings,policy=DPrefixQualification(),output=folder,
                on_event=lambda e:print('SPD',case_id,mode,e['operation']['label'],e['reason'],flush=True))
            metrics=b.score(case,b.curve_from(result['final_curve']))
            residual=result.get('relative_residual')
            result.update(metrics=metrics,recovered=bool(result['final_audit_passed'] and metrics['rms_mm']<=1 and
                metrics['hausdorff_upper_mm']<=2 and residual is not None and np.all(residual<=b.residual_limits(case))),
                manifest_sha256=digest(output/'manifest.json'),environment=b.environment())
            write(folder/'result.json',result)
        result=compare(folders['spd016'],folders['reference'])
        a,c=[read(folders[m]/'result.json') for m in ('spd016','reference')]
        result.update(case=case_id,candidate_seconds=a['total_seconds'],reference_seconds=c['total_seconds'],
                      time_saving=1-a['total_seconds']/c['total_seconds'])
        result['cost_pass']=result['time_saving']>=.20
        tag=f'c{case["contrast"]:g}'
        archive=b.ROOT/'results/validation/speedup/SPD-016-20260930-damped-gpu/runs/baseline/D'/tag/case['case']
        result['reference_vs_archived']=compare(folders['reference'],archive)
        rows.append(result)
        write(output/'spd_pairs/comparison.json',dict(passed=False,complete=False,rows=rows))
        if not result['quality_pass'] or not result['reference_vs_archived']['quality_pass']:
            raise RuntimeError('SPD extraction quality gate failed; stop before the all-36 campaign')
    summary=dict(passed=all(r['quality_pass'] and r['cost_pass'] and r['reference_vs_archived']['quality_pass'] for r in rows),
                 complete=True,rows=rows,environment=b.environment(),
                 limitation='Two sequential D pairs; not full-DF/all-36 speedup evidence')
    write(output/'spd_pairs/comparison.json',summary)
    b.verify(output)
    return summary


def compare_execution(reference_outputs,candidate_outputs,*,matched_host_load=False):
    """Repeated full-path comparison. Caller attests comparable external host load.

    Reference should use current real-CUDA/thread/cache execution with
    acceleration=reference; candidate uses spd016. Physics/policy/data stay fixed.
    """
    if len(reference_outputs)!=len(candidate_outputs) or len(reference_outputs)<b.COMPARISON['runtime']['repeats']:
        raise ValueError('Provide at least three corresponding full-path reference and candidate campaigns')
    roots=[Path(p) for p in (*reference_outputs,*candidate_outputs)]
    if len({p.resolve() for p in roots})!=len(roots):
        raise ValueError('Independent repeats must use distinct campaign directories')
    for path in roots:
        b.verify(path,require_damped=True)
    baseline=read(roots[0]/'manifest.json')
    control=read(roots[0]/'execution.json')
    env_keys=('python','platform','machine','gpu','torch','numpy','blas_threads','threadpools')
    def data_hashes(path):
        aug=path/'augmentation.json'
        return read(aug)['files'] if aug.exists() else {}
    measurements=data_hashes(roots[0])
    # Qualification JSON timings differ across repeated generation; compare
    # observation bytes, never infer identity from a seed alone.
    measurements={k:v for k,v in measurements.items() if k.endswith('/observations.json')}
    for path in roots:
        m=read(path/'manifest.json')
        e=read(path/'execution.json')
        if any(m[k]!=baseline[k] for k in ('sources','inputs','policy','comparison')):
            raise ValueError('Source/input/policy comparison mismatch: '+str(path))
        hashes={k:v for k,v in data_hashes(path).items() if k.endswith('/observations.json')}
        if hashes!=measurements:
            raise ValueError('Augmented observations differ: '+str(path))
        settings,original=e['settings'],control['settings']
        if settings['solver']!=original['solver'] or settings['workers']!=original['workers'] or any(
            settings['execution'][key]!=original['execution'][key]
            for key in ('device','frequency_threads','geometry','resolution')):
            raise ValueError('Unmatched execution configuration: '+str(path))
        if any(e['environment'][key]!=control['environment'][key] for key in env_keys):
            raise ValueError('Unmatched hardware/software/thread environment: '+str(path))
    rows=[]
    for case in baseline['cases']:
        paired=[]
        for ref,candidate in zip(reference_outputs,candidate_outputs):
            a,c=Path(candidate)/'runs'/case['id'],Path(ref)/'runs'/case['id']
            check=compare(a,c)
            ar,cr=read(a/'result.json'),read(c/'result.json')
            paired.append(dict(check,candidate_seconds=ar['total_seconds'],reference_seconds=cr['total_seconds']))
        ratio=float(np.median([r['candidate_seconds'] for r in paired])/
                    np.median([r['reference_seconds'] for r in paired]))
        rows.append(dict(case=case['id'],quality_pass=all(r['quality_pass'] for r in paired),
                         runtime_ratio=ratio,cost_pass=ratio<=b.COMPARISON['runtime']['max_ratio'],repeats=paired))
    summary=dict(complete=len(rows)==36,matched_host_load=matched_host_load,
        passed=bool(matched_host_load and len(rows)==36 and all(r['quality_pass'] and r['cost_pass'] for r in rows)),
        rows=rows,reference_outputs=list(map(str,reference_outputs)),candidate_outputs=list(map(str,candidate_outputs)),
        result_hashes={str(p/'runs'/r['id']/'result.json'):digest(p/'runs'/r['id']/'result.json')
                       for p in roots for r in baseline['cases']})
    for path in map(Path,candidate_outputs):
        write(path/'runtime_comparison.json',summary)
        b.report(path)
    return {k:v for k,v in summary.items() if k not in ('rows','result_hashes')}
