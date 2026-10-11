"""CG-001 run03: unchanged real-control quota completion and adjacent fold probe.

Consumes run02 evidence without changing its failed outcome. No new physics,
fold selection, derivatives, starting shape, or continuation algorithm.
"""
import argparse
import json
from pathlib import Path
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.complex_radius import circle_path, pseudo_arclength, track
from . import cg001 as C

SOURCE = C.ROOT/'results/validation/complex_geometry/CG-001/run-02'
OUTPUT = SOURCE.parent/'run-03'


def decode_fold(row):
    return {k: C.z(v) if k in ('F', 'Fq', 'Fqq', 'Ft') else v for k, v in row.items()}


def refine_states(model, refined, result, path):
    C.write(path, result)
    checks = []
    for i, row in enumerate(result['states']):
        st = refined.state(row['q'], row['t'])
        checks.append(dict(field=C.relative(model.jets(row['q'])[0][0], refined.jets(row['q'])[0][0]),
            stationarity=abs(st['F'])/st['scale'],
            Fq_relative=abs(st['Fq']-row['Fq'])/max(1.,abs(row['Fq']))))
        if (i+1) % 500 == 0:
            result['refined_checks'] = checks
            C.write(path, result)
    result['refined_checks'] = checks
    C.write(path, result)


def run(source, output):
    if output.exists():
        raise FileExistsError('Preserve earlier run folders')
    output.mkdir(parents=True)
    started = perf_counter()
    C.ACTIVE_BUDGET = C.Budget(started)
    outcome = dict(status='STARTED')
    try:
        C.campaign.verify(require_inputs=True)
        manifest = json.loads((source/'manifest.json').read_text())
        if not all(C.sha(C.ROOT/p)==v for p,v in manifest['source_hashes'].items()):
            raise ValueError('Run02 numerical/qualification sources changed; cannot reuse evidence')
        saved = json.loads((source/'continuation.json').read_text())
        qualified = json.loads((source/'qualification.json').read_text())
        if not qualified['passed'] or saved['status'] != 'UNQUALIFIED_TRANSPORT':
            raise ValueError('Expected passed physics and underexposed run02 control')
        checks = saved['checks']
        if max(v for k,v in checks.items() if 'splitting' not in k) > 1e-7:
            raise ValueError('The earlier complex transport itself did not pass')
        sources = dict(manifest['source_hashes'])
        sources[str(Path(__file__).relative_to(C.ROOT))] = C.sha(__file__)
        sources['docs/iterations/complex_geometry/CG-001_run02.md'] = C.sha(
            C.ROOT/'docs/iterations/complex_geometry/CG-001_run02.md')
        C.write(output/'manifest.json', dict(experiment='CG-001', purpose='real-control quota completion',
            parent_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=C.ROOT,text=True).strip(),
            source_run=str(source.relative_to(C.ROOT)), source_hashes=sources,
            evidence_hashes={p.name:C.sha(p) for p in source.glob('*.json')},
            steps=6000, same_step_length=True, input_manifest_sha256=manifest['input_manifest_sha256']))
        model = C.instrument(saved['contrast'], saved['frequencies_ghz'])
        refined = C.instrument(saved['contrast'], saved['frequencies_ghz'], 12)
        fold = decode_fold(saved['fold'])
        radius, qb, tb = saved['loop_radius'], saved['base_q'], saved['base_t']
        splitting = np.sqrt(abs(2*(-fold['Ft']/fold['Fqq']).real*radius))
        ds = min(.002, splitting/30)
        result = pseudo_arclength(model, qb, tb, direction=np.sign(fold['q']-qb), steps=6000, ds=ds)
        result['summary'] = C.path_summary(model, result)
        result['ds'] = ds
        refine_states(model, refined, result, output/'path_arclength_completed.json')
        crossed = (result['states'][-1]['q'].real-fold['q'])*(qb-fold['q']) < 0
        prefix_old = json.loads((source/'path_arclength.json').read_text())['states']
        prefix_difference = max(abs(a['q']-C.z(b['q']))+abs(a['t']-C.z(b['t']))
                                for a,b in zip(result['states'][:len(prefix_old)],prefix_old))
        passed = (result['status']=='COMPLETED' and crossed and result['summary']['real']
            and result['summary']['hessian']*saved['start_hessian'] < 0 and prefix_difference < 1e-12
            and max(r['stationarity'] for r in result['refined_checks']) <= 1e-8
            and max(r['field'] for r in result['refined_checks']) <= 1e-8)
        summary = dict(control_passed=bool(passed), crossed_fold=bool(crossed), ds=ds,
            initial_200_step_reproduction=prefix_difference, summary=result['summary'],
            fold=fold, model_index=saved['model_index'],
            verdict='QUALIFIED_LOCAL_MONODROMY' if passed else 'CONTROL_COMPLETION_FAILED',
            exploration=dict(status='NOT_RUN_CONTROL_INCOMPLETE'))
        C.write(output/'completion.json', summary)
        print('CONTROL', summary, flush=True)
        if passed:
            # Keep the original conditional selection: nearest next radius fold
            # on the sheet exchanged by the already-qualified first loop.
            census = json.loads((source/f'census_{saved["model_index"]:02d}.json').read_text())
            other = C.z(saved['summaries']['one_loop']['endpoint_q']).real
            adjacent = sorted([decode_fold(f) for f in census['folds'] if f['qualified'] and
                (f['q']-fold['q'])*(other-fold['q']) > 0], key=lambda f: abs(f['q']-other))
            exploration = dict(status='NO_ADJACENT_QUALIFIED_FOLD')
            if adjacent:
                nf = adjacent[0]
                eps = min(radius, .2*abs(nf['t']-fold['t']))
                t2, pair, _ = C.local_pair(model, nf, eps)
                q2 = min(pair, key=lambda q:abs(q-other))
                travel_q = np.linspace(other,q2,1001)
                a,b,_ = model.ab(travel_q)
                travel_t = (a[:,0]/b[:,0]).real
                connected = (np.min(abs(b[:,0])) > 1e-8 and
                    np.all(np.sign(b[:,0].real)==np.sign(b[0,0].real)) and
                    np.min(travel_t)>=-2 and np.max(travel_t)<=3)
                exploration = dict(status='BRANCH_DOMAIN_REFUSAL', next_fold=nf,
                    q=travel_q,t=travel_t,B=b[:,0].real,minimum_B=float(np.min(abs(b[:,0]))),
                    sampled_attachment_passed=bool(connected))
                if connected:
                    angle = 0. if t2>nf['t'] else np.pi
                    second = track(model,q2,circle_path(nf['t'],eps,angle,1,1,points=256))
                    second['summary']=C.path_summary(model,second)
                    refine_states(model,refined,second,output/'path_adjacent_loop.json')
                    exploration.update(status='ADJACENT_LOCAL_TOUR', start_q=q2,start_t=t2,
                        start_hessian=model.state(q2,t2)['Fq'].real,
                        start_measured_loss=model.real_loss(q2),summary=second['summary'],
                        local_pair=pair,
                        note='Exploratory local tour attached by sampled real branch; not a t=1 fit.')
            summary['exploration']=exploration
            C.write(output/'completion.json',summary)
            print('EXPLORATION',exploration['status'],exploration.get('summary'),flush=True)
        summary.update(counters=model.counters(),refined_counters=refined.counters())
        C.write(output/'completion.json',summary)
        outcome=dict(status=summary['verdict'],sources_unchanged=all(C.sha(C.ROOT/p)==v for p,v in sources.items()))
    except Exception:
        outcome=dict(status='EXCEPTION',traceback=traceback.format_exc())
        print(outcome['traceback'],flush=True)
    outcome.update(seconds=perf_counter()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    C.write(output/'outcome.json',outcome)
    print('OUTCOME',outcome,flush=True)
    return outcome


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args()
    answer=run(args.source,args.output)
    if answer['status']=='EXCEPTION':
        raise SystemExit(1)
