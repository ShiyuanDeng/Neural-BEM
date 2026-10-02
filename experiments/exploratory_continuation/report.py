"""Summarize every requested scene, charging all eight SCIF trials."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

from .run import OUTPUT, ROOT, write


def load(path):
    return json.loads(path.read_text()) if path.exists() else dict(status='MISSING')


def audit_solves(row):
    return (row.get('audit_forward_work',{}).get('completed',0)
            +row.get('endpoint',{}).get('audit_work',{}).get('totals',{}).get('bie_frequency_solve_count',0))


def count_work(rows):
    return dict(known_lm_work_units=sum(r.get('work',{}).get('work_units',0) for r in rows),
        known_bie_solves=sum(sum(r.get('work',{}).get('solves',{}).values()) for r in rows),
        known_reciprocal_batches=sum(sum(r.get('work',{}).get('reciprocal_batches',{}).values()) for r in rows),
        known_audit_bie_solves=sum(audit_solves(r) for r in rows),
        summed_job_wall_seconds=sum(r.get('wall_seconds',0) for r in rows))


def main():
    spec = load(ROOT/'config/topology_scenes_v1.json')
    scenes = [s['id'] for s in spec['scenes']]
    data = load(OUTPUT/'initializers'/'summary.json')['rows']
    report = dict(scene_count=len(scenes),initializer=dict(
        correct_count=sum(d['topo']['geometry']['component_count']==d['topo']['geometry']['truth_component_count'] for d in data),
        improved_iou=sum(d['topo']['geometry']['union_iou']>d['current']['geometry']['union_iou'] for d in data),
        initializer_bie_solves=sum(d['initializer_work']['totals']['bie_frequency_solve_count'] for d in data),
        seconds=sum(d['initializer_seconds'] for d in data)))
    controller={}
    for arm in ('current','topo'):
        rows = [load(OUTPUT/'controller'/arm/f'{scene}.json') for scene in scenes]
        controller[arm]=dict(status_counts=dict(Counter(r['status'] for r in rows)),
            passes=sum(r['status']=='COMPLETED' and r.get('endpoint',{}).get('passed',False) and all(r.get('trajectory_checks',{}).values()) for r in rows),
            known_inversion_bie_solves=sum(r.get('work',{}).get('totals',{}).get('bie_frequency_solve_count',0) for r in rows),
            work_total_complete=all('work' in r for r in rows),
            summed_job_wall_seconds=sum(r.get('wall_seconds',0) for r in rows))
    report['controller']=controller
    for phase in ('controller_guarded','controller_full'):
        phase_rows={}
        for arm in ('current','topo'):
            rows=[load(OUTPUT/phase/arm/f'{scene}.json') for scene in scenes]
            phase_rows[arm]=dict(status_counts=dict(Counter(r['status'] for r in rows)),
                passes=sum(r['status']=='COMPLETED' and r.get('endpoint',{}).get('passed',False) and all(r.get('trajectory_checks',{}).values()) for r in rows),
                known_inversion_bie_solves=sum(r.get('work',r.get('last_checkpoint',{}).get('work',{})).get('totals',{}).get('bie_frequency_solve_count',0) for r in rows),
                known_audit_bie_solves=sum(audit_solves(r) for r in rows),
                work_total_complete=all('work' in r and not r.get('work_incomplete',False) for r in rows),
                summed_job_wall_seconds=sum(r.get('wall_seconds',0) for r in rows))
        report[phase]=phase_rows
    results={}
    arm_names=['sc_fixed_band','rla_0.5','rla_1.0','rla_1.5']
    for arm in arm_names:
        rows=[load(OUTPUT/'continuation'/arm/f'{s}.json') for s in scenes]
        results[arm]=dict(rows=rows,status_counts=dict(Counter(r['status'] for r in rows)),
            passes=sum(r.get('endpoint',{}).get('passed',False) and r.get('path_completed',False) for r in rows),
            completed_paths=sum(r.get('path_completed',False) for r in rows),
            known_lm_work_units=sum(r.get('work',{}).get('work_units',0) for r in rows),
            known_bie_solves=sum(sum(r.get('work',{}).get('solves',{}).values()) for r in rows),
            known_reciprocal_batches=sum(sum(r.get('work',{}).get('reciprocal_batches',{}).values()) for r in rows),
            known_audit_bie_solves=sum(audit_solves(r) for r in rows),
            summed_job_wall_seconds=sum(r.get('wall_seconds',0) for r in rows),
            work_total_complete=all('work' in r and not r.get('work_incomplete',False) for r in rows))
    selected=[]
    trials=[load(OUTPUT/'continuation'/f'scif_{seed}'/f'{scene}.json') for scene in scenes for seed in range(8)]
    for scene in scenes:
        rows=[load(OUTPUT/'continuation'/f'scif_{seed}'/f'{scene}.json') for seed in range(8)]
        candidates=[r for r in rows if r.get('path_completed',False) and np.isfinite(r.get('selection_score',np.nan))]
        selected.append(min(candidates,key=lambda r:r['selection_score']) if candidates else dict(scene=scene,status='NO_COMPLETED_PATH'))
    results['scif_best_of_8']=dict(rows=selected,trial_status_counts=dict(Counter(r['status'] for r in trials)),
        completed_paths=sum(r.get('path_completed',False) for r in trials),
        passes=sum(r.get('endpoint',{}).get('passed',False) for r in selected),
        known_lm_work_units=sum(r.get('work',{}).get('work_units',0) for r in trials),
        known_bie_solves=sum(sum(r.get('work',{}).get('solves',{}).values()) for r in trials),
        known_reciprocal_batches=sum(sum(r.get('work',{}).get('reciprocal_batches',{}).values()) for r in trials),
        known_audit_bie_solves=sum(audit_solves(r) for r in trials),
        summed_job_wall_seconds=sum(r.get('wall_seconds',0) for r in trials),
        work_total_complete=all('work' in r and not r.get('work_incomplete',False) for r in trials),
        selection='lowest mean squared relative residual over five training frequencies among completed paths')
    report['continuation']={arm:{k:v for k,v in rows.items() if k!='rows'} for arm,rows in results.items()}
    if (OUTPUT/'cap_extension_campaign.json').exists():
        augmented=[]
        replayed=[]
        reused=[]
        for original in trials:
            if original.get('reason')=='TRIAL_SOLVE_CAP':
                row=load(OUTPUT/'continuation_cap512'/original['arm']/f"{original['scene']}.json")
                replayed.append(row)
            else:
                row=original
                reused.append(row)
            augmented.append(row)
        selected=[]
        for scene in scenes:
            candidates=[r for r in augmented if r.get('scene')==scene and r.get('path_completed',False)
                        and np.isfinite(r.get('selection_score',np.nan))]
            selected.append(min(candidates,key=lambda r:r['selection_score']) if candidates else dict(scene=scene,status='NO_COMPLETED_PATH'))
        report['scif_cap512_supplement']=dict(
            completed_paths=sum(r.get('path_completed',False) for r in augmented),
            status_counts=dict(Counter(r['status'] for r in augmented)),
            passes=sum(r.get('endpoint',{}).get('passed',False) for r in selected),
            reused_endpoints=len(reused),rerun_endpoints=len(replayed),
            effective_96_path_work=count_work(augmented),
            actual_original_plus_replay_work=count_work(trials+replayed),
            input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for scene in scenes for p in (OUTPUT/'frequency_data'/f'{scene}.npz',OUTPUT/'initializers'/f'{scene}.json')},
            previous_manifest_core_source_hashes_match=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
                for name,digest in load(OUTPUT/'manifest.json').get('source_sha256',{}).items()
                if not name.startswith('experiments/exploratory_continuation/')),
            reuse_audit='Same immutable frequency arrays, initializer inputs and unchanged core solver sources. Larger cap only changes reservation termination; deterministic update computations before that stop are unchanged.')
        write(OUTPUT/'cap512_selected_endpoints.json',selected)
    write(OUTPUT/'selected_endpoints.json', {arm:rows['rows'] for arm,rows in results.items()})
    write(OUTPUT/'summary.json',report)
    files=list((ROOT/'experiments/exploratory_continuation').glob('*.py'))
    files += [ROOT/'config/topology_scenes_v1.json',ROOT/'run_topology_scene_benchmark.py',
              ROOT/'experiments/shape_continuation/lm_backend.py',ROOT/'experiments/shape_continuation/multi_object.py',
              ROOT/'experiments/shape_continuation/forward.py',ROOT/'solvers/sdf_inverse/radial_topology.py',
              ROOT/'solvers/sdf_inverse/topology_controller.py']
    write(OUTPUT/'manifest.json',dict(git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        original_spec=spec,known_contract_changes=dict(
            controller_primary=dict(directory='controller_full',policy='H for both arms',
                frozen_budgets=spec['controller'],extra_policy_flags=dict(refined_feasibility_guard=True,feasible_fd_jacobian=True),
                workers=4,per_job_timeout_seconds=600,timeout_origin='Original benchmark run_topology_scene_benchmark.py declared per-run cap',
                passed_requires_completed_job=True),
            controller_pilots=dict(directories=['controller','controller_guarded'],
                maximum_cycles=2,fixed_iterations=6,candidate_refinement_iterations=2,maximum_candidates_per_type=12,
                policy='A then H',timeout_seconds=[120,180]),
            continuation_primary=dict(training_frequencies_hz=[.25e9,.375e9,.5e9,.75e9,1e9],
                topology='fixed-count TD initialization',curve_modes=24,nodes=64,refined_nodes=128,
                updates_per_visit=2,work_cap=160,scif_upward_probability=.603,seeds=list(range(8)),maximum_path_visits=32),
            continuation_supplement=dict(work_cap=512,rerun_pure_work_stops=16,reused_deterministic_endpoints=80,
                accounting='Both effective96-path and actual original-plus-replay totals saved; all failed attempts charged'),
            resolution_diagnostic=dict(separate_from_primary=True,node_pairs=[[64,128],[128,256],[256,512]],
                frozen_proposal_nodes=[256,512,1024],
                same_candidate_fine_relative_change=load(OUTPUT/'frozen_candidate_resolution.json').get('resolution',[{}])[-1].get('relative_change'))),
        shared_heldout_frequencies_hz=[1.5e9,2.5e9],cpu_only=True,blas_threads=1,
        wall_comparison_controlled=False))
    write_readme(report,scenes)
    print(json.dumps(report,indent=2))


def write_readme(report,scenes):
    full=report['controller_full']
    finished=all(sum(n for status,n in arm['status_counts'].items() if status not in ('MISSING','STARTED'))==12 for arm in full.values())
    lines=['# Sampling and frequency paths — October 2, 2026','',
        'The topological initializer and the frequency-path experiments retain all twelve scene configurations. '
        'They are separate comparisons with different training-data contracts. '
        'The [implementation README](../../experiments/exploratory_continuation/README.md) records primary literature, derivations, commands and limitations.','',
        '## Initializer comparison','',
        'The image uses only the archived 0.5 GHz paired training measurements. It improves starting IoU in '
        f"{report['initializer']['improved_iou']}/12 scenes and identifies the correct component count in "
        f"{report['initializer']['correct_count']}/12, requiring zero BIE solves. The two count failures are merge (three seeds for one ellipse) and repeated-birth (four seeds for three circles). "
        'Truth is used only for evaluation. LSM is explicitly unsupported for the frozen paired acquisition; missing cross-source/receiver measurements are never fabricated.','',
        '![Data-only initial circles (white) and evaluation truth (cyan)](initializers/all_scenes.png)','',
        'The original-budget comparison uses the same existing H feasibility policy for both arms: ten cycles,22 fixed iterations,three candidate refinement iterations and48 candidates per type. '
        'The per-job600-second cap is inherited from the original benchmark. '
        +('All24 jobs have returned or reached that cap.' if finished else '**The full-budget campaign is still running; counts below are provisional.**'),'',
        '| Initializer | All-gate passes /12 | Known inverse BIE solves | Audit BIE solves | Summed job seconds | Complete work counts? |',
        '|---|---:|---:|---:|---:|---|']
    for arm,label in [('current','Original starts'),('topo','Topological starts')]:
        row=full[arm]
        lines.append(f"| {label} | {row['passes']} | {row['known_inversion_bie_solves']} | {row['known_audit_bie_solves']} | {row['summed_job_wall_seconds']:.1f} | {row['work_total_complete']} |")
    lines += ['', 'A timeout is a failed benchmark run and remains in the denominator. Its last checkpoint retains partial work; reported inverse counts are lower bounds whenever a job did not return its final ledger. Parallel shared CPU load makes timing descriptive.','',
        '| Scene | Original start | Topological start |','|---|---|---|']
    for scene in scenes:
        cells=[]
        for arm in ('current','topo'):
            row=load(OUTPUT/'controller_full'/arm/f'{scene}.json')
            passed=row['status']=='COMPLETED' and row.get('endpoint',{}).get('passed',False) and all(row.get('trajectory_checks',{}).values())
            cells.append('PASS' if passed else 'FAIL: '+row.get('stop_reason',row['status']))
        lines.append(f"| {scene} | {' | '.join(cells)} |")
    lines += ['', 'The initial two-cycle A-policy pilot had five topological-arm exceptions after newly born components approached the10mm cross-quadrature gap. All seed geometries had passed their initial refined audits. '
        'The existing H refined-feasibility guard removes those exceptions: the matched two-cycle H pilot completed24/24 jobs, with2/12 passes from original starts and5/12 from topological starts. '
        'All earlier attempts remain under `controller/` and `controller_guarded/`; `controller_full/` owns the original-budget comparison.','',
        '## Frequency-path comparison','',
        'The frozen suite has only one training frequency, so a nontrivial frequency walk requires additional observations. '
        'This declared extension uses0.25,0.375,0.5,0.75 and1GHz training, preserving1.5/2.5GHz holdout data. '
        'All12 synthetic training sets qualified at N128/256 and against the original0.5GHz samples. '
        'All arms use the same data-only topological seeds, fixed component count, K24, N64/128 and two LM updates per visit. '
        '`SC fixed M=5` is a small SC-backend control, not the full cleaned-interface/MA cumulative strategy.','',
        '| Policy | Passes /12 | Completed paths | Fit BIE solves | Reciprocal batches | Audit BIE solves | LM units |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,label in [('sc_fixed_band','SC fixed M=5'),('rla_0.5','RLA c=0.5'),('rla_1.0','RLA c=1'),('rla_1.5','RLA c=1.5'),('scif_best_of_8','SCIF best of8,160-unit cap')]:
        row=report['continuation'][name]
        lines.append(f"| {label} | {row['passes']} | {row['completed_paths']} | {row['known_bie_solves']} | {row['known_reciprocal_batches']} | {row['known_audit_bie_solves']} | {row['known_lm_work_units']} |")
    supplement=report.get('scif_cap512_supplement')
    if supplement:
        work=supplement['effective_96_path_work']
        lines.append(f"| SCIF best of8,512-unit supplement | {supplement['passes']} | {supplement['completed_paths']}/96 | {work['known_bie_solves']} | {work['known_reciprocal_batches']} | {work['known_audit_bie_solves']} | {work['known_lm_work_units']} |")
        actual=supplement['actual_original_plus_replay_work']
        lines += ['', f"The supplement reran16 work-capped paths and explicitly reused80 deterministic endpoints under unchanged input/core-source hashes. "
            f"Actual cost including the original capped attempts is {actual['known_lm_work_units']} LM units, {actual['known_bie_solves']} fit BIE solves, {actual['known_reciprocal_batches']} reciprocal batches and {actual['known_audit_bie_solves']} audit BIE solves. "
            'Best-of-eight selection uses only training residual and excludes incomplete or nonfinite endpoints; all eight trials are charged. It did not improve pass count over RLA c=1, and costs substantially more. This small bounded comparison establishes no general superiority claim.']
    lines += ['', 'The seven remaining primary SCIF failures occur on the fixed-count three-seed merge initialization. '
        'A separate resolution diagnostic preserves those failures and checks progressively finer physics; its results are in [resolution_diagnostic.json](resolution_diagnostic.json). '
        'The [frozen proposal audit](frozen_candidate_resolution.json) isolates the same geometrically admissible proposal: N256/512 disagrees by 1.8833e-5, while N512/1024 disagrees by 4.6697e-6, below the 1e-5 gate. '
        'Thus higher quadrature can resolve this numerical stop; it is not a geometry rejection. '
        'Changing quadrature does not change the incorrect component count: fixed-count disjoint normal updates cannot turn three components into one. '
        'The diagnostic does not claim a completed high-resolution inverse or recovery.','',
        '## Numerical controls and evidence','',
        'The separate32-by-32 full-ring LSM disk control attains its1% right-hand-side discrepancy at all6561 image points; its peak is exactly at the disk center on the grid. '
        'Its N64/128 forward change is2.04e-15. This is a synthetic full-matrix control, not a claim about noise selection or LSM on the frozen paired data.','',
        'Four focused sampling/path tests and six half-space tests pass. '
        '[path_completion_audit.json](path_completion_audit.json) preserves the correction of seven false completion flags, and '
        '[frequency_metadata_audit.json](frequency_metadata_audit.json) documents correcting descriptive frequency values from indices to Hz. Neither correction changes any forward solve. '
        'The one implementation-development failure is retained in `development_failures/`.','',
        'Machine-readable evidence: [summary.json](summary.json), [manifest.json](manifest.json), '
        '[selected_endpoints.json](selected_endpoints.json), [cap512_selected_endpoints.json](cap512_selected_endpoints.json), '
        'individual run records, logs, checkpoints, qualified observations and source/input hashes. '
        'Setup required120 frequency solves for the extra training-data qualification; endpoint audits and initialization audits are separately recorded.']
    text='\n'.join(lines)+'\n'
    for a,b in {'ten cycles,22':'ten cycles, 22','iterations,three':'iterations, three','and48':'and 48','per-job600':'per-job 600','All24':'All 24','completed24':'completed 24','with2/12':'with 2/12','and5/12':'and 5/12','the10mm':'the 10 mm','uses0.25,0.375,0.5,0.75 and1GHz':'uses 0.25, 0.375, 0.5, 0.75 and 1 GHz','preserving1.5/2.5GHz':'preserving 1.5/2.5 GHz','All12':'All 12','original0.5GHz':'original 0.5 GHz','best of8,160':'best of 8, 160','best of8,512':'best of 8, 512','reran16':'reran 16','reused80':'reused 80','separate32':'separate 32','its1%':'its 1%','all6561':'all 6561','is2.04':'is 2.04','required120':'required 120'}.items():text=text.replace(a,b)
    (OUTPUT/'README.md').write_text(text)


if __name__=='__main__':
    main()
