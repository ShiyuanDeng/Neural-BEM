"""Rebuild matched SPD-016 gates from saved JSON without numerical reruns."""
import json
from pathlib import Path
import numpy as np

BUNDLE = Path(__file__).resolve().parents[1]
ROOT = BUNDLE.parents[3]


def read(p):
    return json.loads(p.read_text())


def no_time(x):
    if isinstance(x,dict):
        return {k:no_time(v) for k,v in x.items() if not ('second' in k or k.endswith('_time'))}
    if isinstance(x,list):
        return [no_time(v) for v in x]
    return x


def rel(a,b):
    a,b=np.asarray(a),np.asarray(b)
    if a.shape!=b.shape:
        return float('inf')
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-300))


def curve(c):
    return np.asarray(c['real'])+1j*np.asarray(c['imag'])


def compare(a_dir,b_dir):
    a,b=read(a_dir/'result.json'),read(b_dir/'result.json')
    sa,sb=a['stages'],b['stages']
    aa,ab=read(a_dir/'accepted.json')['states'],read(b_dir/'accepted.json')['states']
    gates={
        'same_configuration':read(a_dir/'configuration.json')==read(b_dir/'configuration.json'),
        'same_outcome_recovery':(a['outcome'],a['recovered'])==(b['outcome'],b['recovered']),
        'same_audit_passes':(a['initial_audit_passed'],a['final_audit_passed'])==(b['initial_audit_passed'],b['final_audit_passed']),
        'same_localization_start':a['localization']['parameters_m']==b['localization']['parameters_m'],
        'same_stages':[(s['stage'],s['M'],s['K'],s['outcome'],s['stop'],s['accepted_steps']) for s in sa]==[(s['stage'],s['M'],s['K'],s['outcome'],s['stop'],s['accepted_steps']) for s in sb],
        'same_work':no_time(a['fit_work'])==no_time(b['fit_work']) and a['fit_and_localization_units']==b['fit_and_localization_units'],
        'same_accepted_indices':[(s['stage'],s['iteration'],s['M'],s['units']) for s in aa]==[(s['stage'],s['iteration'],s['M'],s['units']) for s in ab],
    }
    errors=dict(final_curve_relative=rel(curve(a['final_curve']),curve(b['final_curve'])),
                rms_mm_absolute=abs(a['metrics']['rms_mm']-b['metrics']['rms_mm']),
                residual_relative=rel(a['relative_residual'],b['relative_residual']))
    errors['maximum_accepted_curve_relative']=max((rel(curve(x['curve']),curve(y['curve'])) for x,y in zip(aa,ab)),default=float('inf')) if len(aa)==len(ab) else float('inf')
    errors['maximum_stage_loss_relative']=max((abs(x['final_loss']-y['final_loss'])/max(abs(y['final_loss']),1e-300) for x,y in zip(sa,sb)),default=float('inf')) if len(sa)==len(sb) else float('inf')
    decisions=[]
    for x,y in zip(sa,sb):
        if x['stage']!=y['stage']:
            continue
        fa,fb=read(a_dir/(x['stage']+'.json')),read(b_dir/(y['stage']+'.json'))
        decision=lambda f:[(v.get('iteration'),v.get('backtrack'),v.get('status')) for v in f['trials']]
        decisions.append(dict(stage=x['stage'],same_trial_decisions=decision(fa)==decision(fb),
                              same_acceptance_checks=[v['accepted'] for v in fa['acceptance_checks']]==[v['accepted'] for v in fb['acceptance_checks']],
                              same_stage_work=no_time(x['work'])==no_time(y['work'])))
    gates['same_decisions']=bool(decisions) and all(all(v for k,v in d.items() if k!='stage') for d in decisions)
    gates.update(accepted_curves=errors['maximum_accepted_curve_relative']<=1e-7,
                 stage_losses=errors['maximum_stage_loss_relative']<=1e-7,
                 endpoint_rms=errors['rms_mm_absolute']<=1e-5,
                 residuals=errors['residual_relative']<=1e-7)
    def times(r):
        return dict(total=r['seconds'],localization=r['localization']['seconds'],grid=r['localization']['grid_seconds'],
                    damped_stages=sum(s['seconds'] for s in r['stages'] if s['stage'].endswith('_damped')),
                    undamped_stages=sum(s['seconds'] for s in r['stages'] if not s['stage'].endswith('_damped')))
    ta,tb=times(a),times(b)
    saving=1-ta['total']/tb['total']
    return dict(quality_pass=all(gates.values()),gates=gates,errors=errors,stage_decisions=decisions,
                candidate_seconds=ta,reference_seconds=tb,total_time_saving=saving,speedup=tb['total']/ta['total'],
                cost_pass=saving>=.2,candidate_units=a['fit_and_localization_units'],reference_units=b['fit_and_localization_units'],
                candidate_metrics=a['metrics'],reference_metrics=b['metrics'])


if __name__=='__main__':
    rows=[]
    for tag,scene in [('c0.5','shifted_star'),('c13.3','new_asymmetric')]:
        a=BUNDLE/'runs/accelerated/D'/tag/scene
        b=BUNDLE/'runs/baseline/D'/tag/scene
        if not (a/'result.json').exists() or not (b/'result.json').exists():
            continue
        r=compare(a,b);r.update(contrast=tag,scene=scene)
        archive=ROOT/'results/validation/modal_atlas/MA-004/runs/D'/tag/scene
        r['fresh_baseline_vs_archive']=compare(b,archive)
        rows.append(r)
        print(json.dumps({k:v for k,v in r.items() if k not in ['stage_decisions','fresh_baseline_vs_archive']}),flush=True)
    (BUNDLE/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
