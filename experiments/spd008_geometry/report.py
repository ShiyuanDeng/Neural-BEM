"""Saved-evidence comparisons; no new solver calls."""
from collections import Counter
import json
from statistics import median
import numpy as np
from . import common as c


def _lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def compare_pair(out,scene,rep):
    folders = [out/f'{arm}_{rep}'/'runs'/scene for arm in c.ARMS]
    if not all((path/'geometry_validation.json').exists() for path in folders):
        return None
    results = [c.read(f/'result.json') for f in folders]
    metrics = [c.read(f/'F/metrics.json') for f in folders]
    topology = [c.read(f/'topology/terminal.json') for f in folders]
    stages = [[c.read(p) for p in sorted((f/'F').glob('stage_*/terminal.json'))] for f in folders]
    states = [c.p.driver.deserialize_state(x['final_state']) for x in metrics]
    checks = dict(both_recovered=all(r['fresh_recovery_pass'] for r in results),
                  source_integrity=all(r['sources_and_inputs_unchanged'] for r in results),
                  final_state_equal=c.m.state_hash(states[0])==c.m.state_hash(states[1]),
                  topology_events_equal=[e['kind'] for e in topology[0]['events']]==[e['kind'] for e in topology[1]['events']],
                  accepted_steps_equal=[s['accepted_steps'] for s in stages[0]]==[s['accepted_steps'] for s in stages[1]],
                  stage_outcomes_equal=[(s['stage_outcome'],s['optimizer_stop']) for s in stages[0]]==[
                      (s['stage_outcome'],s['optimizer_stop']) for s in stages[1]])
    trajectories = [[(r['label'],r['cycle'],c.m.state_hash(r['state']),r['loss'])
                     for r in _lines(folder/'topology/trajectory.jsonl')] for folder in folders]
    checks['topology_trajectory_equal'] = trajectories[0]==trajectories[1]
    for filename,keys in (
        ('trajectory.jsonl',('state_sha256','loss','gradient')),
        ('production_candidates.jsonl',('base_state_sha256','candidate_state_sha256','production_gain')),
        ('jacobians.jsonl',('state_sha256','directions','one_sided_columns','unresolved_columns')),
        ('feasibility.jsonl',('category','state_sha256','reason')),
    ):
        values = []
        for folder in folders:
            values.append([[{k:row[k] for k in keys} for row in _lines(path)]
                           for path in sorted((folder/'F').glob('stage_*/'+filename))])
        checks[filename+'_equal'] = values[0]==values[1]
    if not all(checks.values()):
        raise RuntimeError('Paired geometry regression: '+repr((scene,rep,checks)))
    return dict(scene=scene,repetition=rep,checks=checks,coefficient_difference_m=float(np.max(abs(
        states[0].parameter_vector()-states[1].parameter_vector()))),
        accepted_steps=[s['accepted_steps'] for s in stages[0]])


def _reconcile(work):
    counts = {}
    assert work['total_attempted']==sum(work['attempted'].values())
    for prefix,name in (('', 'physical'),('derivative_assemblies_','operator'),
                        ('reciprocal_batches_','reciprocal'),('compiled_batches_','compiled')):
        attempted = sum(work.get(prefix+'attempted',{}).values())
        assert attempted == sum(work.get(prefix+'completed',{}).values())+sum(work.get(prefix+'failed',{}).values())
        counts[name] = attempted
    assert work['budget_work_units']==sum(counts.values())
    assert work['within_solve_cap']
    for part in work.get('parts',[]):
        _reconcile(part)
    return counts


def report(out):
    c.verify(out)
    timings = c.read(out/'timings.json')
    pairs = [compare_pair(out,scene,rep) for rep in range(2) for scene in c.SCENES]
    rows = []
    for timing in timings:
        folder = out/timing['arm']/'runs'/timing['scene']
        result = c.read(folder/'result.json')
        stats = c.read(folder/'geometry_validation.json')
        counts,seconds,work = Counter(),Counter(),Counter()
        for fit in stats['fits']:
            counts.update(fit['counts']); seconds.update(fit['seconds'])
            assert fit['peak_bytes'] <= fit['max_bytes']
        for part in (result['topology_work'],result['continuation']['work']):
            work.update(_reconcile(part))
        rows.append(dict(arm=timing['arm'],scene=timing['scene'],seconds=timing['seconds'],
            recovered=result['fresh_recovery_pass'],fit_count=len(stats['fits']),geometry_counts=dict(counts),
            geometry_seconds=dict(seconds),work=dict(work),
            peak_cache_bytes=max((f['peak_bytes'] for f in stats['fits']),default=0),
            final=c.read(folder/'F/metrics.json').get('final')))
    aggregates = []
    for scene in c.SCENES:
        times = {arm:[r['seconds'] for r in rows if r['scene']==scene and r['arm'].startswith(arm+'_')]
                 for arm in c.ARMS}
        assert all(len(x)==2 for x in times.values())
        medians = {k:median(v) for k,v in times.items()}
        aggregates.append(dict(scene=scene,median_seconds=medians,paired_samples=times,
            speedup=medians['reference']/medians['certified'],
            reduction=1-medians['certified']/medians['reference']))
    for pair in pairs:
        assert pair is not None
        ref,test = [next(r for r in rows if r['scene']==pair['scene'] and
                        r['arm']==f"{arm}_{pair['repetition']}") for arm in c.ARMS]
        assert ref['work']==test['work'],(pair['scene'],'work mismatch')
    campaign = c.read(out/'execution_status.json')
    assert campaign['status']=='COMPLETE' and len(rows)==16 and all(r['returncode']==0 for r in timings)
    useful = all(a['reduction']>=.2 for a in aggregates if a['scene'] in c.SCENES[2:])
    easy = all(a['reduction']>=-.05 for a in aggregates if a['scene'] in c.SCENES[:2])
    summary = dict(status='PASS',campaign=campaign,rows=rows,comparisons=pairs,aggregate=aggregates,
        twenty_percent_hard_gate=useful,easy_nonregression_five_percent_gate=easy,
        recommended='retain qualified opt-in; default promotion remains separate' if useful and easy else 'record bounded result; do not promote',
        scope='Four noiseless scenes; two repeats per arm; sequential CPU workers; full inverse including endpoint checks',
        host_isolation='Host-wide isolation unverified',geometry_policy='fd_compatible in both arms',
        timing_note='Both arms collect fit-local validation diagnostics; nested geometry timings must not be added')
    c.write(out/'summary.json',summary)
    print(json.dumps(dict(status=summary['status'],aggregate=aggregates,recommended=summary['recommended']),indent=2))
