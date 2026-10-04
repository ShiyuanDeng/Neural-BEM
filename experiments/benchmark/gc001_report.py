"""Read-only receipt validation and summaries for the approved GC-001 replay."""
import argparse
from collections import Counter
import statistics
from pathlib import Path
import subprocess

import numpy as np

from bem_inverse.io import read, write, digest
from .gc001 import ARMS, DIAGNOSTIC_IDS, DEFAULT_OUTPUT
from . import campaign


def median(x):
    return float(statistics.median(x))


def summary(x):
    return dict(median=median(x), maximum=float(max(x)), minimum=float(min(x)), count=len(x))


def historical_context():
    rows = {}
    failures = {'aphex_twin__c0.5','aphex_twin__c4','aphex_twin__c13.3','hook__c13.3'}
    for experiment, arm in [('PC-001','M1'),('PC-001','N1'),('PC-002','NS')]:
        paths = sorted((campaign.ROOT/'results/validation/cleaned_interfaces'/experiment/arm/'runs').glob('*/fit_result.json'))
        data = [(p.parent.name,read(p)) for p in paths]
        def aggregate(items):
            prep = sum(d['geometry_work']['preparation_seconds'] for _,d in items)
            trial = sum(d['geometry_work']['trial_seconds'] for _,d in items)
            total = sum(d['total_seconds'] for _,d in items)
            fraction = (prep+trial)/total
            return dict(cases=len(items), preparation_seconds=prep,trial_seconds=trial,total_seconds=total,
                        nested_certificate_seconds=sum(d['geometry_work'].get('certificate_seconds',0) for _,d in items),
                        geometry_fraction=fraction,
                        median_case_fraction=median([(d['geometry_work']['preparation_seconds']+
                            d['geometry_work']['trial_seconds'])/d['total_seconds'] for _,d in items]),
                        speedup_if_geometry_twice_faster=1/(1-fraction/2),
                        speedup_if_geometry_free=1/(1-fraction))
        rows[f'{experiment}/{arm}'] = dict(all=aggregate(data),
            recovered=aggregate([r for r in data if r[0] not in failures]),
            failed=aggregate([r for r in data if r[0] in failures]),
            source_hashes={str(p.relative_to(campaign.ROOT)):digest(p) for p in paths})
    return rows


def build(output):
    output = Path(output)
    manifest = read(output/'manifest.json')
    completed = read(output/'completion.json')
    assert completed['completed'] and completed['physics_calls']==0
    assert manifest['physics_calls']==0 and len(manifest['states'])==31
    assert manifest['unique_states']==len({r['exact_key'] for r in manifest['states']})
    campaign.verify(require_inputs=True)
    assert digest(campaign.INPUTS/'manifest.json')==manifest['tg002_manifest_sha256']
    for path, expected in manifest['source_hashes'].items():
        # Check the measured commit, so later report-only edits do not rewrite provenance.
        saved = subprocess.check_output(['git','show',manifest['source_commit']+':'+path],cwd=campaign.ROOT)
        import hashlib
        assert hashlib.sha256(saved).hexdigest()==expected, path
    for state in manifest['states']:
        assert digest(campaign.ROOT/state['source'])==state['sha256'], state['id']
    assert read(output/'adapter_qualification.json')['passed']
    precision, preparations, timings = [], [], []
    for state in manifest['states']:
        folder = output/'precision'/state['id']
        preparations.append(read(folder/'preparation.json'))
        moves = [read(p) for p in sorted(folder.glob('*m-d*.json'))]
        assert len(moves)==9, state['id']
        precision.extend(dict(state=state['id'],**r) for r in moves)
        counts = read(folder/'counts.json')
        assert all(v['trial_constructions']==9 for v in counts.values())
        for arm in ('B','C'):
            assert counts[arm].get('prepare_fallbacks',0)==0
            assert counts[arm].get('device_certificate_fallbacks',0)==0
        if state['timing_panel']:
            rows=read(output/'timing'/(state['id']+'.json'))
            assert len(rows)==12 and Counter(r['arm'] for r in rows)=={a:3 for a in ARMS}
            assert {(r['arm'],r['repeat']) for r in rows}=={(a,i) for a in ARMS for i in range(3)}
            timings.extend(rows)
    assert len(precision)==279 and len(timings)==132
    timing={}
    state_ids=[r['id'] for r in manifest['states'] if r['timing_panel']]
    per_state={}
    for arm in ARMS:
        per_state[arm]={}
        for state in state_ids:
            rows=[r for r in timings if r['arm']==arm and r['state']==state]
            per_state[arm][state]=dict(preparation=median([r['preparation_seconds'] for r in rows]),
                first_trial=median([r['first_trial']['seconds'] for r in rows]),
                subsequent_trial=median([r['subsequent_trial']['seconds'] for r in rows]))
        timing[arm]={key:summary([r[key] for r in per_state[arm].values()])
                     for key in ('preparation','first_trial','subsequent_trial')}
        timing[arm]['measured_range']={key:summary([r[raw] if raw=='preparation_seconds' else r[raw]['seconds']
                       for r in timings if r['arm']==arm])
                   for key,raw in [('preparation','preparation_seconds'),('first_trial','first_trial'),
                                   ('subsequent_trial','subsequent_trial')]}
    ratios={}
    for a,b in [('S','F'),('S','B'),('F','B'),('B','C')]:
        ratios[f'{a}/{b}']={key:summary([per_state[a][s][key]/per_state[b][s][key] for s in state_ids])
                            for key in ('preparation','first_trial','subsequent_trial')}
    qualified=[r for r in precision if r['reference_qualified']]
    agreement={}
    for arm in ARMS:
        counts=Counter('accepted' if r['trials'][arm]['accepted'] else r['trials'][arm]['reason'] for r in precision)
        agreement[arm]=dict(counts)
    disagreement={}
    for a,b in [('S','F'),('F','B'),('B','C')]:
        difference=[dict(state=r['state'],move=r['move']['id'],a=r['trials'][a],b=r['trials'][b])
                    for r in precision if r['trials'][a]['accepted']!=r['trials'][b]['accepted'] or
                    (not r['trials'][a]['accepted'] and r['trials'][a].get('reason')!=r['trials'][b].get('reason'))]
        disagreement[f'{a}/{b}']=difference
    errors={arm:dict(refinement_relative=summary([r['refinement'][arm]['relative'] for r in precision]),
            reference_maximum_m=summary([r['reference_errors'][arm]['maximum_m'] for r in qualified]),
            reference_relative=summary([r['reference_errors'][arm]['relative'] for r in qualified]))
            for arm in ('S','F')}
    errors['by_step']={str(size):{arm:dict(
            reference_maximum_m=summary([r['reference_errors'][arm]['maximum_m'] for r in qualified if r['move']['size_m']==size]),
            refinement_relative=summary([r['refinement'][arm]['relative'] for r in precision if r['move']['size_m']==size]))
            for arm in ('S','F')} for size in (1e-7,.001,.006)}
    errors['S_F']=dict(maximum_m=summary([r['S_F']['maximum_m'] for r in precision]),
        normal_maximum_m=summary([r['S_F']['normal_maximum_m'] for r in precision]),
        tangential_maximum_m=summary([r['S_F']['tangential_maximum_m'] for r in precision]),
        columns={a:summary([p['columns'][a]['maximum'] for p in preparations]) for a in ('S','B','C')})
    errors['reference']=dict(qualified=len(qualified),unqualified=len(precision)-len(qualified),
        refinement_relative=summary([r['reference']['relative'] for r in precision]))
    ablations=[read(output/'preparation_ablations'/(s+'.json')) for s in DIAGNOSTIC_IDS]
    derivatives=[read(output/'derivatives'/(s+'.json')) for s in DIAGNOSTIC_IDS]
    assert all(len(r['steps'])==3 for r in derivatives)
    interpolation=[read(p) for p in sorted((output/'interpolation').glob('*.json'))]
    assert len(interpolation)==6
    ranked=sorted(precision,key=lambda r:(-r['S_F']['relative'],r['state'],r['move']['id']))[:6]
    assert [(r['selection']['state'],r['selection']['move']) for r in interpolation]==[(r['state'],r['move']['id']) for r in ranked]
    assert all(r['closure_maximum']<1e-12 for r in interpolation)
    profiles=[dict(state=s,arms=read(output/'profiling'/(s+'.json'))) for s in DIAGNOSTIC_IDS]
    for state in profiles:
        for arm in state['arms']:
            assert arm['preparation_other']>=-1e-6 and arm['trial_other']>=-1e-6
            assert all(v>=0 for v in arm['preparation_components'].values())
            assert all(v>=-1e-9 for v in arm['trial_components'].values())
    report=dict(experiment='GC-001',validated=True,completed=completed,source_commit=manifest['source_commit'],
        coverage=dict(states=31,unique_states=manifest['unique_states'],trials=279,timing_states=11,timing_repeats=3),
        timing_seconds=timing,paired_ratios=ratios,timing_per_state=per_state,
        precision=errors,decision_counts=agreement,decision_disagreements=disagreement,
        preparation_ablations=ablations,derivative_panel=derivatives,interpolation=interpolation,
        profiles=profiles,historical_context=historical_context(),
        semantics=dict(timing='median of per-state medians, 11 equally weighted states, ranges retained',
            reference='qualified 4N/8N spectral refinement; not exact geometry or a rigorous bound',
            errors='parameter-aligned 2N curve evaluation; metres and normalized units; not Hausdorff',
            full_runtime='saved full-run counters include audit geometry; certificate time nested in trial',
            scope='geometry only; no inverse recovery or new physical-resolution evidence'))
    write(output/'report.json',report)
    lines=['# GC-001: current geometry runtime, precision and attribution','',
           f"Validated {len(precision)} common moves on 31 TG-002 replay states; zero physics calls.",
           f"Numerical source: `{manifest['source_commit']}`. Raw receipts and failures are preserved.",'',
           '## Repeated geometry timing','',
           'Median of per-state medians, 11 states × three repeats; milliseconds. First trial is 1 mm with a fresh',
           'space/cache; subsequent trial is 6 mm in that same space. Sizes differ, so first/subsequent',
           'columns do not isolate cache benefit. All attempts, including refusals, are timed.','',
           '| Arm | Preparation ms | First trial ms | Subsequent trial ms |',
           '|---|---:|---:|---:|']
    labels={'S':'Spline CPU','F':'Spectral CPU, sampled','B':'GPU-prepared spectral, sampled','C':'GPU-prepared spectral, certified'}
    for arm in ARMS:
        t=timing[arm]
        lines.append(f"| {labels[arm]} | {t['preparation']['median']*1000:.3f} | {t['first_trial']['median']*1000:.3f} | {t['subsequent_trial']['median']*1000:.3f} |")
    lines+=['','## Precision and native decisions','',
        f"Refined reference qualified on {len(qualified)}/279 moves. Errors below use only qualified references.",'',
        '| Map | Median maximum curve error, nm | Worst maximum curve error, nm | Median refinement / sigma0 | Accepted moves |',
        '|---|---:|---:|---:|---:|']
    for arm in ('S','F'):
        e=errors[arm]
        lines.append(f"| {labels[arm]} | {e['reference_maximum_m']['median']*1e9:.6g} | {e['reference_maximum_m']['maximum']*1e9:.6g} | {e['refinement_relative']['median']:.3g} | {agreement[arm].get('accepted',0)}/279 |")
    lines+=['',f"Decision disagreements: S/F {len(disagreement['S/F'])}; F/B {len(disagreement['F/B'])}; B/C {len(disagreement['B/C'])}.",
            'Spectral B/C use the same trial projection as F; their changed base-projection arithmetic is measured separately.',
            '', '## Interpolation attribution: six largest S/F disagreements','',
            'Errors are centred trial differences against the qualified refined spectral reference, in nm.',
            'The inverse/position replacements keep the native moved curve and native arclength primitive fixed.',
            'Vector contributions and their interaction are retained; norm reductions are not an additive error budget.','',
            '| State / move | Native | Refined inverse only | Fourier position only | Both |',
            '|---|---:|---:|---:|---:|']
    for r in interpolation:
        e=r['errors'];s=r['selection']
        label=s['state']+' / '+s['move']+(' (reference unresolved)' if not r['reference_qualified'] else '')
        lines.append(f"| {label} | "+' | '.join(f"{e[k]['maximum_m']*1e9:.6g}" for k in ('native','inverse','position','both'))+' |')
    lines+=['','Rows marked reference unresolved show diagnostic distances only; they are excluded from accuracy rankings.']
    lines+=['','## Whole-inverse context','',
            'These are historical internal runtime fractions, not matched inverse speed comparisons.','',
            '| Existing run | Recorded geometry-update share of total | Median case share | Total speedup if all geometry is 2× faster |',
            '|---|---:|---:|---:|']
    for name,context in report['historical_context'].items():
        c=context['all']
        lines.append(f"| {name} | {100*c['geometry_fraction']:.2f}% | {100*c['median_case_fraction']:.2f}% | {c['speedup_if_geometry_twice_faster']:.3f}× |")
    lines+=['','Boundary-update counters include preparation, trial construction and validity checks, including audits.',
            'They exclude geometry assembly charged inside physics. Fitting-only geometry fractions cannot be recovered',
            'exactly from those saved counters. Inverse steps/recovery did not run in this experiment.','',
            'The detailed interpretation is in [iteration 30](../../../../docs/iterations/cleaned_interfaces/iteration_30/01_results.md).',
            'Paired timing ranges, FD step sweeps, preparation ablations, exclusive component profiles and raw',
            'error vectors are retained in `report.json` and the per-phase directories.']
    (output/'README.md').write_text('\n'.join(lines)+'\n')
    write(output/'validation.json',dict(passed=True,checks=['31 fixed states/279 moves','11 × 3 × 4 timing arms',
        'source commit hashes','input seal and replay source hashes','zero device fallbacks',
        'five preparation/derivative/profile states','six predeclared ranked interpolation trials',
        'factorial vector closure','exclusive profiling accounting'],physics_calls=0))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    result=build(args.output)
    print('Validated',result['coverage'],'seconds',result['completed']['total_seconds'])
