"""Read-only scientific-contract audit of completed SC-041 artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import re

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def main():
    manifest, summary, completion = [read(HERE/name) for name in ('manifest.json','summary.json','completion.json')]
    checks = {}
    snapshots = read(HERE/'source_snapshots.json')
    for group in ('sources','inputs'):
        checks[group+'_preserved'] = all(hashlib.sha256(
            (ROOT/(snapshots[p]['snapshot'] if p in snapshots else p)).read_bytes()).hexdigest()==h
            for p,h in manifest[group].items())
    # The driver may receive a post-run reporting repair; no executed numerical
    # function may change. Preserve and inspect the exact originally run source.
    def numerical_tree(path):
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if not (isinstance(node,ast.FunctionDef) and node.name=='summarize')]
        return ast.dump(tree,include_attributes=False)
    checks['runner_numerics_unchanged'] = numerical_tree(HERE/'run.py')==numerical_tree(HERE/'frozen_run.py')
    plan_path = ROOT/'docs/iterations/shape_frequency_continuation/iteration_22/03_plan.md'
    def contract(text):
        return re.sub(r'^- \*\*Execution status:.*?(?=^- \*\*Question:)', '', text, flags=re.M|re.S)
    checks['contract_settings_unchanged'] = contract(plan_path.read_text())==contract((HERE/'frozen_plan.md').read_text())
    checks['completed'] = completion['status']=='COMPLETE'
    checks['screen_budget'] = summary['screen_units'] <= manifest['screen_cap']
    checks['inverse_budget'] = summary['inverse_units'] <= manifest['inverse_cap']
    checks['audit_budget'] = summary['audit_units'] <= manifest['audit_cap']
    checks['no_worker_exceptions'] = not summary['failures']
    for case, bands in manifest['arms'].items():
        screen = read(HERE/'diagnostics'/case/'screen.json')
        checks[case+'_screen_budget'] = screen['work']['work_units'] <= 1000
        prior = None
        for M in bands:
            prediction = read(HERE/'diagnostics'/case/f'M{M}_prediction.json')
            arrays = HERE/'diagnostics'/case/f'M{M}_model.npz'
            checks[f'{case}_M{M}_model_hash'] = hashlib.sha256(arrays.read_bytes()).hexdigest()==prediction['arrays_sha256']
            with np.load(arrays) as d:
                norm = np.sqrt(d['step']@d['metric']@d['step'])
                gain = -d['r']@(d['J']@d['step'])-.5*np.linalg.norm(d['J']@d['step'])**2
            checks[f'{case}_M{M}_physical_bound'] = norm <= prediction['radius']*(1+1e-10)
            checks[f'{case}_M{M}_gain_rebuilt'] = np.isclose(gain,prediction['predicted_decrease'],rtol=1e-10,atol=1e-25)
            folder = HERE/'runs'/case/f'M{M}'
            if not screen['passed']:
                checks[f'{case}_M{M}_gate_obeyed'] = not folder.exists()
                continue
            config, result, audit = [read(folder/name) for name in ('configuration.json','result.json','audit.json')]
            summary_row = next(r for r in summary['rows'] if r['case']==case and r['M']==M)
            checks[f'{case}_M{M}_summary_matches_raw'] = all(summary_row[k]==result[k] for k in
                ('outcome','stop','initial_loss','final_loss','score','initial_score','accepted_steps')) \
                and summary_row['units']==result['work']['work_units']
            checks[f'{case}_M{M}_qualified'] = audit['passed']
            checks[f'{case}_M{M}_budget'] = result['work']['work_units'] <= 1500 and audit['work']['work_units'] <= 130
            checks[f'{case}_M{M}_controls'] = config['M']==M and config['stage']['update_modes']==M and config['stage']['curve_modes']==192
            comparable = {k:v for k,v in config.items() if k not in ('M','stage')}
            comparable['stage'] = {k:v for k,v in config['stage'].items() if k not in ('update_modes','label')}
            checks[f'{case}_M{M}_matched'] = prior is None or comparable==prior
            prior = comparable
            accepted = read(folder/'accepted.json')['states']
            checks[f'{case}_M{M}_endpoint_preserved'] = accepted[-1]['curve']==result['curve']
            checks[f'{case}_M{M}_loss_monotone'] = all(b['loss']<a['loss'] for a,b in zip(accepted,accepted[1:]))
    common = {}
    for case in manifest['arms']:
        rows = [r for r in summary['rows'] if r['case']==case]
        if not rows:
            continue
        limited = [r['units'] for r in rows if r['outcome']!='NORMAL_OPTIMIZER_RETURN']
        ceiling = min(limited) if limited else max(r['units'] for r in rows)
        states = []
        for row in rows:
            history = read(HERE/'runs'/case/f"M{row['M']}"/'progress.json')['states']
            state = [s for s in history if s['work']['work_units']<=ceiling][-1]
            states.append(dict(M=row['M'],state_units=state['work']['work_units'],loss=state['loss'],score=state['score']))
        common[case] = dict(common_work_ceiling=ceiling,states=states)
    (HERE/'common_work.json').write_text(json.dumps(common,indent=2)+'\n')
    checks = {key:bool(value) for key,value in checks.items()}
    report = dict(passed=all(checks.values()), checks=checks, check_count=len(checks),
                  work=dict(screen=summary['screen_units'], inverse=summary['inverse_units'], audit=summary['audit_units']))
    (HERE/'integrity_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    assert report['passed'], 'SC-041 artifact audit failed'


if __name__=='__main__':
    main()
