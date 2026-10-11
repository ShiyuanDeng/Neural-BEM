"""Read-only NG-001 evidence validation, breakdowns and scientific plots."""
from collections import Counter
from pathlib import Path
import argparse

import numpy as np

from bem_inverse.io import read, write, digest


def stats(values):
    return None if not values else dict(count=len(values), median=float(np.median(values)),
        maximum=float(np.max(values)), sum=float(np.sum(values)))


def analyze(output):
    output=Path(output)
    manifest=read(output/'manifest.json')
    rows=[read(p) for p in sorted((output/'states').glob('*/*m-d*.json'))]
    preparations={p.parent.name:read(p) for p in (output/'states').glob('*/preparation.json')}
    hashes={name:digest(output/'source_snapshot'/name)==expected
            for name,expected in manifest['source_hashes'].items()}
    assert all(hashes.values()), 'Measured source snapshot was modified.'
    keys=[(r['state'],r['move']['id']) for r in rows]
    assert len(keys)==len(set(keys)), 'Duplicate moves.'
    completion=read(output/'completion.json') if (output/'completion.json').exists() else None
    if completion:
        assert completion['completed'] and not completion['source_changes']
        assert len(rows)==9*len(manifest['states'])
        assert set(preparations)=={s['id'] for s in manifest['states']}
        assert completion['no_curve_sample_guards_passed'] and completion['physics_calls']==0
    assert manifest['physics_calls']==0

    def group(selected):
        constructed=[r for r in selected if r['arms']['coarse']['success']]
        qualified=[r for r in constructed if r.get('reference_qualified')]
        checks=[c for r in selected for n in ('coarse','fine')
                for c in r['arms'][n].get('validity',{}).values()]
        return dict(trials=len(selected), current_accepted=sum(r['current']['accepted'] for r in selected),
            constructed=len(constructed), refined_reference_qualified=len(qualified),
            production_accurate=sum(r['arms']['coarse']['error']['l1_relative']<=1e-5 for r in qualified),
            tight_accurate=sum(r['arms']['coarse']['error']['l1_relative']<=1e-7 for r in qualified),
            certified=sum(r['arms']['coarse'].get('accepted',False) for r in selected),
            qualified_certified=sum(r['arms']['coarse'].get('accepted',False) and
                r['arms']['coarse']['error']['l1_relative']<=1e-5 for r in qualified),
            failures=dict(Counter(r['arms']['coarse'].get('reason') for r in selected
                                  if not r['arms']['coarse']['success'])),
            certificate_outcomes=dict(Counter(c['outcome'] for c in checks)),
            certificate_reasons=dict(Counter(c['reason'] for c in checks if c['outcome']!='valid')),
            l1_error_nm=stats([r['arms']['coarse']['error']['l1_m']*1e9 for r in qualified]))

    result=dict(completed=completion is not None, snapshot_hashes=hashes,
        overall=group(rows), by_size={str(s):group([r for r in rows if r['move']['size_m']==s])
                                     for s in sorted({r['move']['size_m'] for r in rows})},
        by_state={s:group([r for r in rows if r['state']==s]) for s in preparations},
        base_failures={s:{n:p['arms'][n].get('reason') for n in ('coarse','fine')
                         if not p['arms'][n]['success']} for s,p in preparations.items()
                       if not all(p['arms'][n]['success'] for n in ('coarse','fine'))},
        base_certificate_reasons=dict(Counter(p['base_certificate']['reason'] for p in preparations.values())),
        current_device_counts=dict(Counter(p['arms']['current']['settings']['prepare_device']
                                          for p in preparations.values())))
    validity_seconds=sum(c.get('total_seconds',c['seconds']) for r in rows for n in ('coarse','fine')
                         for c in r['arms'][n].get('validity',{}).values())
    result['work_seconds_including_refusals']=dict(
        current_full_preparation=sum(p['arms']['current']['seconds'] for p in preparations.values()),
        current_all_trials=sum(r['current']['seconds'] for r in rows),
        coefficient_two_band_preparation=sum(p['arms'][n]['seconds'] for p in preparations.values()
                                             for n in ('coarse','fine')),
        coefficient_all_trial_constructions=sum(r['arms'][n]['seconds'] for r in rows for n in ('coarse','fine')),
        base_interval_certification=sum(p['base_certificate']['seconds'] for p in preparations.values()),
        trial_interval_certification=validity_seconds,
        comparison_wall_time=None if completion is None else completion['total_seconds'])
    tangents=[read(p) for p in sorted((output/'derivatives').glob('*.json'))]
    result['tangent_reference_refinement_max']=max((e for t in tangents for e in t['reference_refinement']),default=None)
    result['tangent_tight_gate']={n:sum(e<=1e-5 for t in tangents if t['arms'][n]['timing']['success']
                                      for e in t['arms'][n]['reference_relative_errors']) for n in ('coarse','fine')}
    write(output/'breakdown.json',result)
    return result,rows


def figures(output,result,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=Path(output)
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    groups=list(result['by_size'].items())
    x=np.arange(len(groups))
    for offset,key,label in [(-.26,'current_accepted','Current accepted'),
                             (0.,'constructed','Coefficient constructed'),
                             (.26,'certified','Coefficient certified')]:
        axes[0].bar(x+offset,[100*v[key]/v['trials'] for _,v in groups],width=.25,label=label)
    axes[0].set(xticks=x,xticklabels=[f'{float(k)*1e3:g} mm' for k,_ in groups],
                ylabel='Fraction of tested moves (%)',ylim=(0,105),title='Finite construction and proof decisions')
    axes[0].legend(fontsize=8)
    paired=[r for r in rows if all(r['arms'][n]['success'] for n in ('coarse','fine'))]
    current=[r['current']['seconds'] for r in paired]
    complete=[sum(r['arms'][n]['seconds'] for n in ('coarse','fine'))+
              sum(c.get('total_seconds',c['seconds']) for n in ('coarse','fine')
                  for c in r['arms'][n].get('validity',{}).values()) for r in paired]
    for values,label in [(current,'Current'),(complete,'Coefficient: both bands + proof')]:
        if values:
            axes[1].plot(np.sort(values),np.arange(1,len(values)+1)/len(values),label=label)
    axes[1].set(xscale='log',xlabel='Seconds per trial',ylabel='Cumulative fraction',
                title=f'Paired costs on {len(paired)} common constructions')
    axes[1].legend(fontsize=8)
    fig.savefig(output/'comparison.png',dpi=180)
    fig.savefig(output/'comparison.svg')
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--figures',action='store_true')
    args=parser.parse_args()
    result,rows=analyze(args.output)
    if args.figures:
        figures(args.output,result,rows)
    print(result['overall'])
