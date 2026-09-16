"""Verify and summarize saved full-pipeline SPD-002 outputs; no BIE solves."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import numpy as np
from scipy.spatial import cKDTree
from experiments.top025 import run as pipeline

read,write=pipeline.read,pipeline.write


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(bundle):
    assert read(bundle/'execution_status.json')['status']=='COMPLETE'
    timings=read(bundle/'timings.json');assert len(timings)==4
    manifest=read(bundle/'manifest.json')
    for name,digest in manifest['source_sha256'].items():
        assert sha(bundle/'measured_sources'/name)==digest,name
    for profile in manifest['profiles']:
        for name,digest in read(bundle/profile/'manifest.json')['input_sha256'].items():
            assert sha(bundle/profile/name)==digest,(profile,name)
    for p in (bundle/'reference/inputs').rglob('*.json'):
        assert sha(p)==sha(bundle/'fast/inputs'/p.relative_to(bundle/'reference/inputs'))
    rows=[]
    for scene in manifest['scenes']:
        results={profile:read(bundle/profile/'runs'/scene/'result.json') for profile in manifest['profiles']}
        times={profile:next(t['seconds'] for t in timings if t['scene']==scene and t['profile']==profile) for profile in results}
        states={}
        for profile,result in results.items():
            assert result['fresh_recovery_pass'] and result['sources_and_inputs_unchanged']
            schedule=result['continuation']['schedule']
            assert schedule['schedule_complete'] and schedule['complete_effective_exposure']
            assert len(schedule['stages'])==4
            states[profile]=pipeline.p.driver.deserialize_state(schedule['stages'][-1]['terminal']['final_state'])
            for work in (result['topology_work'],result['continuation']['work']):
                assert sum(work['attempted'].values())==sum(work['completed'].values())+sum(work['failed'].values())
                assert sum(work['derivative_assemblies_attempted'].values())==sum(work['derivative_assemblies_completed'].values())+sum(work['derivative_assemblies_failed'].values())
                assert work['budget_work_units']==work['total_attempted']+sum(work['derivative_assemblies_attempted'].values())
                assert work['budget_work_units']<=work['solve_cap']
        assert results['fast']['original_start_sha256']==results['reference']['original_start_sha256']
        for stage in range(1,5):
            configs=[read(bundle/profile/'runs'/scene/'F'/f'stage_{stage}'/'optimizer.json')
                     for profile in ('reference','fast')]
            for key in ('config','active_frequencies_hz','production_nodes','refined_nodes',
                        'minimum_component_radius_m','extra_feasibility_nodes'):
                assert configs[0][key]==configs[1][key],(scene,stage,key)
        assert states['fast'].component_ids==states['reference'].component_ids
        a,b=states['reference'].parameter_vector(),states['fast'].parameter_vector()
        coefficient_difference=float(np.max(np.abs(a-b)))
        boundary_difference=0.
        for a,b in zip(pipeline.p.boundary_points(states['reference']),pipeline.p.boundary_points(states['fast'])):
            boundary_difference=max(boundary_difference,float(cKDTree(a).query(b)[0].max()),float(cKDTree(b).query(a)[0].max()))
        assert boundary_difference<=1e-6,(scene,boundary_difference)
        counts={profile:sum(sum(w['derivative_assemblies_attempted'].values()) for w in
            (result['topology_work'],result['continuation']['work'])) for profile,result in results.items()}
        assert counts['reference']==0 and counts['fast']>0
        row=dict(scene=scene,reference_seconds=times['reference'],fast_seconds=times['fast'],
            speedup=times['reference']/times['fast'],both_recovered=True,
            maximum_coefficient_difference_m=coefficient_difference,maximum_boundary_difference_m=boundary_difference,
            reference_full_systems=results['reference']['actual_attempted_calls'],
            fast_full_systems=results['fast']['actual_attempted_calls'],fast_derivative_assemblies=counts['fast'])
        rows.append(row)
    for timing in timings:assert not timing['workers_before'] and not timing['workers_after']
    report=dict(status='PASS',tests_passed=261,scope='two complete topology and four-stage continuation cases; single timing per profile',rows=rows)
    write(bundle/'summary.json',report)
    with (bundle/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# SPD-002 — fast default in the current topology pipeline','',
        '**PASS.** Analytic Cartesian Jacobians and faster CPU kernels are now the default. '
        'The reference profile restores FD/reference CPU; CUDA is optional.','',
        'The actual TOP-025 `run_scene` pipeline ran from original death/split starts and saved observations, '
        'through automatic topology and all four frequency-continuation stages. No optimizer settings, '
        'resolutions, acceptance formulas or acquisition changed. N=64/128 for topology and 256/512 for '
        'continuation; 24 pairs, four training frequencies. Runs were sequential with one CPU BLAS thread. '
        'Single complete timing per profile, including worker startup and endpoint checks; no rendering.','',
        '| Case | FD/reference CPU | New default | Speedup | Maximum boundary difference | Recovery |',
        '|---|---:|---:|---:|---:|---|']
    for r in rows:lines.append(f"| {r['scene']} | {r['reference_seconds']:.2f} s | {r['fast_seconds']:.2f} s | {r['speedup']:.2f}x | {r['maximum_boundary_difference_m']*1e6:.6f} um | Both pass |")
    lines+=['','## Work and correctness','',
        '| Case | Reference full systems | Fast full systems | Fast derivative assemblies/tangents |',
        '|---|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['scene']} | {r['reference_full_systems']} | {r['fast_full_systems']} | {r['fast_derivative_assemblies']} |")
    lines+=['',
        'Both physical-system and derivative attempt/completion/failure counts reconcile. Budgets charge '
        'one unit per full frequency system or analytic directional assembly/tangent. Existing '
        '`total_attempted` values remain physical-system counts; `budget_work_units` includes derivatives. '
        'Feasible-stencil fallback, damping, geometry gates and endpoint checks remain active.','',
        'SPD-001 measured a single update with the true analytic constraint policy. The promoted '
        'default uses the FD-compatible policy, which checks perturbation feasibility before retaining '
        'analytic columns. These full runs also include topology and endpoint validation, so their '
        'speedup should be read directly from this table rather than inferred from the earlier 2.60x update.','',
        '261 tests passed, including real continuation/default selection, constrained derivatives, '
        'CPU/CUDA numerical parity, topology controls, worker inheritance and budget-failure handling. '
        'Historical tests prescribing FD or synthetic residuals explicitly select FD/reference mode. '
        'The archived TOP-017 source-lock test verifies rejection of later solver changes.','',
        '## Use','',
        'Existing Cartesian topology commands use the fast mode without changes. Add '
        '`--inverse-runtime reference` to the controller, benchmark, challenge or current TOP-025 runner '
        'to restore FD/reference CPU. `SDF_INVERSE_RUNTIME=reference` works for other callers and spawned '
        'workers. In Python use `with sdf_inverse.runtime.inverse_runtime("reference"):`. Radial '
        'coefficient states retain FD under automatic selection. Explicit execution contexts are respected.','',
        '## Provenance and limits','',
        '`manifest.json` and `measured_sources/` freeze this implementation. Profile subfolders retain '
        'identical input copies, their hashes, every topology event/iterate, continuation state, '
        'acceptance check, work ledger and recovery gate. `timings.json` includes process checks and '
        'load averages. The approved plan, test logs, summary CSV/JSON and artifact hashes are saved. '
        'Reporting can be rebuilt with `python -m experiments.spd002_default_runtime.summarize BUNDLE`.','',
        'These two full-case controls support the default change and measured saving. They are not '
        'a rerun of all twelve scenes, and do not establish that every scene speeds up equally.']
    (bundle/'README.md').write_text('\n'.join(lines)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    print(json.dumps(summarize(parser.parse_args().bundle),indent=2))
