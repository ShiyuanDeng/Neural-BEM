"""Rebuild SPD-001 timing/equivalence tables from saved outputs; no BIE work."""
from pathlib import Path
import argparse,csv,hashlib,json,statistics
import numpy as np


def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def summarize(bundle):
    assert read(bundle/'qualification.json')['status']=='PASS'
    assert read(bundle/'execution_status.json')==dict(status='COMPLETE',phase='all')
    manifest=read(bundle/'manifest.json')
    for name,h in manifest['source_sha256'].items():
        assert digest(bundle/'measured_sources'/name)==h,name
    for name,h in manifest['input_sha256'].items():
        saved=bundle/Path(name).name.replace('.json','_input.json')
        assert digest(saved)==h,name
    rows=[read(p) for p in sorted((bundle/'arms').glob('*/result.json'))]
    assert len(rows)==24,(len(rows),'expected 18 Jacobian and six optimizer rows')
    assert all(r['status']=='PASS' and not r['environment_before']['workers'] and not r['environment_after']['workers'] for r in rows)
    budget=read(bundle/'budget.json')
    assert all(v<=3600 for v in budget['seconds'].values())
    assert all(budget['counts'][k]<=v for k,v in dict(assembly_equivalents=8000,derivative_assemblies=4000,factorizations=5000).items())
    arms=[r[0] for r in read(bundle/'manifest.json')['arms']]
    matrix_reference=np.load(bundle/'arms/jacobian_fd_cpu_0/jacobian_0.npy')
    jrows=[]
    for arm in arms:
        subset=[r for r in rows if r['kind']=='jacobian' and r['arm']==arm]
        assert len(subset)==3 and all(r['accepted_updates']==0 for r in subset)
        vals=[r['seconds'] for r in subset]
        matrix=np.load(bundle/f'arms/jacobian_{arm}_0/jacobian_0.npy')
        assert matrix.shape==matrix_reference.shape==(48,34)
        error=np.linalg.norm(matrix-matrix_reference)/np.linalg.norm(matrix_reference)
        jrows.append(dict(arm=arm,median_seconds=statistics.median(vals),minimum_seconds=min(vals),maximum_seconds=max(vals),
            relative_jacobian_difference_from_fd=float(error),execution_counts=subset[0]['execution_counts'],
            work=subset[0]['work'],assembly_equivalents=subset[0]['assembly_equivalents']))
    baseline=jrows[0]['median_seconds']
    for row in jrows:row['speedup']=baseline/row['median_seconds']
    orows=[next(r for r in rows if r['kind']=='optimizer' and r['arm']==a) for a in arms]
    baseline=orows[0]['seconds'];base=np.array(orows[0]['final_parameters'])
    analytic_base=np.array(orows[1]['final_parameters'])
    for row in orows:
        assert row['optimizer_config']==orows[0]['optimizer_config']
        assert row['frequencies_hz']==orows[0]['frequencies_hz']
        assert row['events']['jacobian_complete']==2
        row['speedup']=baseline/row['seconds']
        row['maximum_coefficient_difference_from_fd_m']=float(np.max(np.abs(np.array(row['final_parameters'])-base)))
        same=analytic_base if row['arm'].startswith('analytic') else base
        row['maximum_backend_coefficient_difference_m']=float(np.max(np.abs(np.array(row['final_parameters'])-same)))
        row['matched_fd_trajectory_within_1um']=row['maximum_coefficient_difference_from_fd_m']<=1e-6
        row['matched_backend_trajectory_within_1um']=row['maximum_backend_coefficient_difference_m']<=1e-6
    assert all(r['matched_backend_trajectory_within_1um'] for r in orows)
    same_updates=len({r['accepted_updates'] for r in orows})==1
    assert same_updates and orows[0]['accepted_updates']==1
    assert all(r['one_sided_columns']==r['unresolved_columns']==0 for r in orows)
    assert all(r['final_loss']<r['initial_loss'] for r in orows)
    matched_fd=all(r['matched_fd_trajectory_within_1um'] for r in orows)
    result=dict(status='PASS',scope='one saved terminal two-star geometry; bounded fixed-topology optimizer, not a full recovery',
        verdict='MATCHED_ONE_UPDATE_SPEEDUP' if matched_fd else 'BACKEND_PARITY_WITH_ANALYTIC_FD_TRAJECTORY_DIVERGENCE',
        same_accepted_update_count=same_updates,jacobian=jrows,optimizer=orows,budget=budget,
        measured_sources_and_inputs_verified=True)
    write(bundle/'summary.json',result)
    with (bundle/'comparison.csv').open('w',newline='') as stream:
        fields=['kind','arm','seconds','minimum_seconds','maximum_seconds','speedup','accepted_updates','final_loss','coefficient_difference_from_fd_m']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for r in jrows:writer.writerow(dict(kind='jacobian',arm=r['arm'],seconds=r['median_seconds'],minimum_seconds=r['minimum_seconds'],maximum_seconds=r['maximum_seconds'],speedup=r['speedup']))
        for r in orows:writer.writerow(dict(kind='optimizer',arm=r['arm'],seconds=r['seconds'],speedup=r['speedup'],accepted_updates=r['accepted_updates'],final_loss=r['final_loss'],coefficient_difference_from_fd_m=r['maximum_coefficient_difference_from_fd_m']))
    lines=['# SPD-001 — measured analytic Jacobian and CPU/CUDA speed','',
        '**Controlled six-arm comparison complete.** Numerical defaults remain FD/reference CPU.','',
        'The current TOP-023 terminal two-star geometry was replayed with current production geometry validation, '
        '24 paired sources, N=256 per component, complex128 and single-thread CPU BLAS. All arms ran sequentially '
        'after TOP-025 and its renderer finished; their process checks found no sibling numerical/render worker. '
        'CUDA timings include copies, factorization, solves and synchronization. Python imports and one-time '
        'CUDA context initialization precede timing; these are warm-process measurements.','',
        '## Complete one-frequency Jacobian','',
        'At 1.25 GHz, 34 directions. Each row includes the base objective, initial refined feasibility and the complete '
        'Jacobian assembled by the actual optimizer. An intentionally large gradient stopping tolerance ends this '
        'timing after the initial Jacobian; it is not used for optimizer-update measurements. Three alternating-order '
        'repetitions per arm, with setup charged in each.','',
        '| Arm | Median [min, max] seconds | Speedup | Relative difference from FD Jacobian |',
        '|---|---:|---:|---:|']
    for r in jrows:lines.append(f"| {r['arm']} | {r['median_seconds']:.3f} [{r['minimum_seconds']:.3f}, {r['maximum_seconds']:.3f}] | {r['speedup']:.2f}x | {r['relative_jacobian_difference_from_fd']:.3e} |")
    lines+=['','## Actual bounded optimizer','',
        'Four training frequencies (0.5/0.75/1.0/1.25 GHz), production FD step 1e-4, N=256 production/N=512 '
        'feasibility and candidate acceptance. One update opportunity, including the initial and terminal Jacobians, '
        'line search and production/refined acceptance. Stored optimizer settings are identical across arms. '
        'These are single complete measurements per arm, not repeat medians or full reconstruction times.','',
        '| Arm | Seconds | Speedup | Accepted updates | Final objective | Max coefficient difference from FD (m) |',
        '|---|---:|---:|---:|---:|---:|']
    for r in orows:lines.append(f"| {r['arm']} | {r['seconds']:.3f} | {r['speedup']:.2f}x | {r['accepted_updates']} | {r['final_loss']:.8e} | {r['maximum_coefficient_difference_from_fd_m']:.3e} |")
    lines+=['',
        ('All six arms accepted one update and their final coefficient differences from FD stayed within '
         'the declared 1e-6 m tolerance.' if matched_fd else
         'Analytic and FD endpoints exceeded the declared 1e-6 m coefficient tolerance. Their time ratio '
         'is not a matched-trajectory speedup; hardware parity within each Jacobian mode passed.')]
    lines+=['','## Where the optimizer time goes','',
        '| Arm | Full systems assembled/factored | Derivative assemblies | Derivative assembly seconds (% of wall time) |',
        '|---|---:|---:|---:|']
    for r in orows:
        derivative=r['execution_seconds'].get('derivative_assembly',0.)
        lines.append(f"| {r['arm']} | {r['assembly_equivalents']['factorizations']} | {r['assembly_equivalents']['derivative_assemblies']} | {derivative:.3f} ({100*derivative/r['seconds']:.1f}%) |")
    lines+=['',
        'A full system solve and a derivative assembly are different units of work. The analytic path retains '
        'one LU per base geometry/frequency and solves tangent RHSs with it, but each direction still assembles '
        'dense derivative operators. Those assemblies dominate the analytic runtime. Execution phase timers '
        'are nested (for example, tangent response contains RHS solves); do not sum them as disjoint phases.']
    lines+=['','## Interpretation and limits','',
        'Derivative choice and hardware choice are measured separately. Analytic derivatives eliminate perturbed '
        'forward solves, while fast real-argument Bessel routines also accelerate derivative assembly. CUDA reuses '
        'one LU per geometry/frequency for all tangent columns. Its incremental contribution is the difference '
        'between the fast-CPU and fast-CUDA rows within the same Jacobian mode.','',
        'Analytic columns need not equal a finite-step FD approximation exactly; trajectory discrepancies are '
        'reported above. Backend comparisons within a derivative mode must stay within 1e-6 m in coefficient '
        'infinity norm. No claim covers a completed recovery, a changed default, all scenes, or lossless-to-lossy '
        'extension. The optional FD-compatible constrained-stencil mode was unit-tested; this terminal state uses '
        'the true analytic mode and has no FD-refused columns in the continuation comparison.','',
        '## Validation and provenance','',
        '- 116 Kress, analytic/backend and FD-constraint tests passed before dispatch. The isolation test explicitly '
        'allows function-local Torch use in the optional execution and existing geometry-pullback modules; '
        'a clean CPU import/factorization still verifies that Torch is not loaded.',
        '- `accounting_hooks_tests.log`: 29 additional optimizer-hook, work-accounting and recovery-handoff '
        'regression tests passed after the timing process exited.',
        '- `qualification.json`: all 192x34 four-frequency columns compared with the archived FD Jacobian; '
        'accelerated analytic paths compared directly with analytic CPU; selected refined-grid sensitivities checked.',
        '- `arms/`: every measured trajectory, matrix, acceptance check, phase count, timing and environment.',
        '- `baseline_sources/` and `measured_sources/`: original and measured numerical source snapshots.',
        '- `manifest.json`, `workspace_before.json`, `budget.json`, `approved_plan.md`, `tests.log`, `execution.log`: '
        'provenance, setup and all charged work. `comparison.csv` and `summary.json` are generated from the arm records.',
        '- `verification.json` reconciles charged work and verifies original/measured/current source hashes '
        'and saved numerical errors. `artifact_manifest.json` hashes every final bundle file except itself.',
        '', 'Rebuild: `PYTHONPATH=solvers:. python -m experiments.spd001_analytic_jacobian.summarize <bundle>`. No BIE solves occur during reporting.']
    (bundle/'README.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    report=summarize(parser.parse_args().bundle)
    print(json.dumps(dict(jacobian=[{k:r[k] for k in ('arm','median_seconds','speedup')} for r in report['jacobian']],
        optimizer=[{k:r[k] for k in ('arm','seconds','speedup','final_loss','maximum_coefficient_difference_from_fd_m')} for r in report['optimizer']]),indent=2))
