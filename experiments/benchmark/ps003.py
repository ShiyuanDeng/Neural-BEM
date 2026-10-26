"""PS-003: the pre-registered, sequential GPU slider comparisons (at most 13 fits)."""
import argparse
import os
import subprocess
import traceback

from bem_inverse.io import read, write
from bem_inverse.physics import Execution
from bem_inverse import policies
from . import campaign as c

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/PS-003'
TRACK = c.ROOT/'docs/iterations/policy_speed'
HOOK = 'hook__c13.3'
SAVED = {'GU-002': c.ROOT/'results/validation/cleaned_interfaces/GU-002/slider',
         'PS-002': c.ROOT/'results/validation/cleaned_interfaces/PS-002'}
CASES = ('circle__c4', 'kite__c0.5', 'c_shape__c13.3', 'aphex_twin__c13.3')
HOOK_ARMS = {'H1': 'feedback', 'H2': 'four_phase', 'H3': 'compact_release'}
CONTRACT = policies.BENCHMARK_CONTRACT


def result(folder, case=HOOK):
    path = folder/'runs'/case/'result.json'
    return read(path) if path.exists() else {}


def actual_calls(row):
    counts = row.get('physics', {}).get('counts', {})
    return sum(counts.get(k, 0) for k in ('evaluation_attempts', 'derivative_attempts'))


def fastest(ids):
    eligible = [(key, result(OUTPUT/key)) for key in ids]
    eligible = [(key, row) for key, row in eligible if row.get('recovered')]
    return min(eligible, key=lambda item: (item[1]['fit_and_localization_seconds'],
               actual_calls(item[1]), list(ids).index(item[0])), default=(None, None))[0]


def comparison():
    """D2's single pre-registered choice; no tuning after the decision."""
    best = fastest(HOOK_ARMS)
    if best in ('H2', 'H3'):
        return HOOK_ARMS[best], {'full_catalog_trace_cutoff': 128}, best, 'full-catalog Ku=128'
    if result(OUTPUT/'H1').get('recovered'):
        return 'feedback', {'minimum_relative_progress': 0.}, 'H1', 'disable shortened-progress exit'
    return 'baseline', dict(plain_progress_exit=True, progress_window=2,
        minimum_relative_progress=.05, progress_exit_minimum_modes=11), 'GU-002', '5% / two exit from M11'


def select():
    """Freeze selection before any other-scene fit."""
    path = OUTPUT/'selection.json'
    if path.exists():
        return read(path)
    best = fastest(('H1', 'H2', 'H3', 'D1', 'D2'))
    if best and result(OUTPUT/best)['fit_and_localization_seconds'] >= 30.294:
        best = None
    selected = dict(run=best, settings=read(OUTPUT/best/'manifest.json')['settings'] if best else None,
                    reference_seconds=30.294, rule='recovered; fastest fit, actual calls, then run ID')
    write(path, selected)
    return selected


def specification(run_id):
    options, reference = {}, 'GU-002'
    case, name = HOOK, HOOK_ARMS.get(run_id, 'baseline')
    reason = 'declared policy bundle'
    if run_id == 'D1':
        options, reason = {'release_bands': (19,)}, 'release directly at M19'
    elif run_id == 'D2':
        name, options, reference, reason = comparison()
    elif run_id not in HOOK_ARMS:
        index, arm = int(run_id[1])-1, run_id[2:]
        if run_id[0] != 'O' or index not in range(4) or arm not in ('B', 'S'):
            raise ValueError('Use H1-H3, D1-D2, or O1B/O1S through O4B/O4S')
        case, reason = CASES[index], 'other-scene baseline' if arm == 'B' else 'frozen selected alternative'
        if arm == 'S':
            selected = select()
            if selected['run'] is None:
                raise ValueError('No faster recovering alternative; selected arms are omitted')
            saved = selected['settings']
            name, options, reference = saved['policy']['recipe']['name'], saved['policy_adapter']['options'], selected['run']
    settings = c.settings_for(policy=name, policy_geometry_update='slider',
        policy_options=dict(options, record_diagnostics=True), contract=CONTRACT, localization='none',
        execution=Execution(device='cuda', preparation_device='cuda', frequency_threads=4))
    return case, settings, dict(reference=reference, change=reason)


def next_run():
    for key in ('H1', 'H2', 'H3', 'D1', 'D2'):
        if not (OUTPUT/key/'manifest.json').exists():
            return key
    selected = select()
    for i in range(1, 5):
        for arm in ('B', 'S') if selected['run'] else ('B',):
            key = f'O{i}{arm}'
            if not (OUTPUT/key/'manifest.json').exists():
                return key
    return None


def run(run_id):
    expected = next_run()
    if run_id != expected:
        raise ValueError(f'Next permitted fit is {expected}; existing attempts cannot be retried')
    if any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')):
        raise RuntimeError('Set OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS to 1')
    if len(list(OUTPUT.glob('*/manifest.json'))) >= 13:
        raise RuntimeError('All 13 fit slots consumed')
    case, settings, comparison_record = specification(run_id)
    folder = OUTPUT/run_id
    if folder.exists():
        raise FileExistsError(f'Preserve existing attempt at {folder}')
    c.verify(c.INPUTS, require_inputs=True)
    problem = c.problem(case)
    physics, _ = c.physics_for(settings)
    physics.validate(problem)
    manifest = c.open_run(folder, [case], settings, experiment='PS-003 '+run_id)
    manifest.update(comparison=comparison_record, resolved_plan=c.adapted_policy(settings).plan(problem, physics),
                    fit_slot=len(list(OUTPUT.glob('*/manifest.json'))),
                    source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    write(folder/'manifest.json', manifest)
    try:
        row = c.run_case((folder, c.row(case), settings))
    except BaseException:
        write(folder/'interrupted.json', dict(traceback=traceback.format_exc(), consumes_fit_slot=True))
        raise
    finally:
        report()
    return dict(run=run_id, recovered=row.get('recovered'), outcome=row.get('outcome'))


def summarize_row(row):
    return dict(recovered=row.get('recovered', False), outcome=row.get('outcome', 'INTERRUPTED'),
        fit_seconds=row.get('fit_and_localization_seconds'), check_seconds=row.get('audit_seconds'),
        accepted=sum(s['accepted_steps'] for s in row.get('stages', [])), actual_calls=actual_calls(row),
        forward_calls=row.get('physics', {}).get('counts', {}).get('evaluation_attempts'),
        reciprocal_calls=row.get('physics', {}).get('counts', {}).get('derivative_attempts'),
        charged_units=row.get('fit_and_localization_units'), rms_mm=row.get('metrics', {}).get('rms_mm'),
        hausdorff_mm=row.get('metrics', {}).get('hausdorff_upper_mm'), residual=row.get('maximum_residual'),
        checks_passed=row.get('final_audit_passed'))


def stage_rows(folder, case):
    rows = []
    for stage in result(folder, case).get('stages', []):
        detail = read(folder/'runs'/case/(stage['stage']+'.json'))
        history, trials = detail['history'], detail['trials']
        row = {k: stage.get(k) for k in ('stage', 'M', 'K_geometry', 'nodes', 'F', 'seconds',
                'accepted_steps', 'initial_loss', 'final_loss', 'stop', 'diagnostics', 'entry_reused')}
        row.update(rejected=sum(t.get('status') != 'accepted' for t in trials),
            maximum_backtrack=max([t['backtrack'] for t in trials] or [0]),
            entry_gradient=history[0]['gradient_inf'] if history else None,
            final_gradient=history[-1]['gradient_inf'] if history else None,
            accepted_timestamps=[h['work']['seconds'] for h in history],
            losses=[h['loss'] for h in history],
            raw_norms=[t['raw_step_norm_m'] for t in trials if 'raw_step_norm_m' in t],
            clipped_norms=[t['clipped_step_norm_m'] for t in trials if 'clipped_step_norm_m' in t],
            used_norms=[h['step_norm_m'] for h in history[1:]])
        rows.append(row)
    return rows


def report():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = {name: summarize_row(result(folder)) for name, folder in SAVED.items()}
    stages = {name: stage_rows(folder, HOOK) for name, folder in SAVED.items()}
    completed = []
    for manifest_path in sorted(OUTPUT.glob('*/manifest.json')):
        manifest = read(manifest_path)
        key, case = manifest_path.parent.name, manifest['cases'][0]
        row = result(manifest_path.parent, case)
        rows[key] = dict(summarize_row(row), case=case, reference=manifest['comparison']['reference'])
        stages[key] = stage_rows(manifest_path.parent, case)
        completed.append(key)
    write(OUTPUT/'comparison.json', rows)
    write(OUTPUT/'stages.json', stages)
    next_id = next_run() if completed else 'H1'
    lines = ['# PS-003: GPU slider policy comparisons', '',
        'Questions: why are hook fits slow, which declared policy helps, and does slider recover other TG-002 cases?', '',
        f'Consumed fits: {len(completed)}/13. Next fit: {next_id or "none; planned fits complete"}.', '',
        'Saved GU-002 and PS-002 are references, not concurrent controls. No reference reruns.', '',
        '| Run | Case | Recovered | Fit s | Final checks s | Accepted | Actual calls | Charged units | RMS mm |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    def fmt(value):
        return '—' if value is None else f'{value:.4g}' if isinstance(value, float) else str(value)
    for key, row in rows.items():
        lines.append('| '+' | '.join(fmt(v) for v in (key, row.get('case', HOOK), row['recovered'],
            row['fit_seconds'], row['check_seconds'], row['accepted'], row['actual_calls'],
            row['charged_units'], row['rms_mm']))+' |')
    lines += ['', '## Saved-run explanation', '',
        'GU-002 used 40 accepted iterations and 15.926 s in M11/M15, with no rejected trials there.',
        'Its loss fell from 0.14065 to 0.024019. Releasing M19 then reached 0.000072 in four iterations.',
        'This is consistent with restricted update directions, but the saved run alone cannot establish the cause.', '',
        'PS-002 left stage_3_damped after six iterations at loss 0.005709; GU-002 used 19 and reached 0.000656.',
        'PS-002 entered M11 at loss 0.550665 versus 0.14065. Its early exits changed the later path.',
        'M43/M49 then cost 9.703 s, with eight rejected trials; it failed recovery in M55.', '',
        'The saved runs lack raw/clipped proposal sizes, skipped tiny proposals and damping retry counts.',
        'Thread-level physics times overlap and are not wall-time totals. New batch timers measure wall time.', '',
        '## Stage evidence', '',
        '| Run | Stage (M/K/Ku/F) | Accepted | Seconds | Entry loss | Final loss | Rejected | Stop |',
        '|---|---|---:|---:|---:|---:|---:|---|']
    for key, ss in stages.items():
        for s in ss:
            label = f"{s['stage']} ({s['M']}/{s['K_geometry']}/{s['nodes']//8}/{s['F'] or '—'})"
            lines.append('| '+' | '.join(fmt(v) for v in (key, label, s['accepted_steps'], s['seconds'],
                s['initial_loss'], s['final_loss'], s['rejected'], s['stop']))+' |')
    lines += ['', 'Full scalar records, settings, histories and failures are in each run directory.',
        'All fits use CUDA physics/preparation, four frequency threads, single-threaded BLAS, a centred start,',
        '13,412 units / 120 s fit limits and 300 s final-check limits. Four-phase uses similarity only at warm-up.',
        'One fit per setting cannot establish repeatability or a 30-case result. Defaults remain unchanged.', '']
    (OUTPUT/'README.md').write_text('\n'.join(lines))
    page = TRACK/'iteration_03/01_results.md'
    page.parent.mkdir(exist_ok=True)
    page.write_text('\n'.join(lines[:lines.index('## Stage evidence')])+ '\n\nDetailed stages: '
        '[PS-003 evidence](../../../../results/validation/cleaned_interfaces/PS-003/README.md).\n')
    (TRACK/'README.md').write_text('# Policy speed\n\nCurrent work: [PS-003 results](iteration_03/01_results.md).\n'
        f'Consumed fits: {len(completed)}/13. Completed attempts: {", ".join(completed) or "none"}.\n'
        f'Exact next fit: {next_id or "none; planned fits complete"}.\n\n'
        'Plan: [PS-003](iteration_02/03_plan.md). Saved references: GU-002 and PS-002.\n'
        'The default policy is unchanged. No retries or extra fits are authorized.\n')
    return rows


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    arms = dict(SAVED)
    arms.update({k: OUTPUT/k for k in ('H1', 'H2', 'H3', 'D1', 'D2') if (OUTPUT/k/'manifest.json').exists()})
    fig, axes = plt.subplots(len(arms), 2, figsize=(13, 2.8*len(arms)), squeeze=False)
    for (key, folder), pair in zip(arms.items(), axes):
        offset = 0
        for stage in stage_rows(folder, HOOK):
            losses = stage['losses']
            xs = [offset+i for i in range(len(losses))]
            for ax, x in zip(pair, (xs, stage['accepted_timestamps'])):
                ax.semilogy(x, losses, '.-', lw=1)
                if x:
                    ax.axvline(x[0], color='.7', lw=.5, ls=':')
                    ax.text(x[0], 1., stage['stage'].replace('release_', '').replace('fixed_', ''),
                            rotation=90, fontsize=5, va='top', transform=ax.get_xaxis_transform())
            offset += stage['accepted_steps']
        for ax in pair:
            ax.set_ylim(1e-15, 2)
            ax.set_title(key)
            ax.set_ylabel('Stage loss')
        pair[0].set_xlabel('Cumulative accepted iterations')
        pair[1].set_xlabel('Fit elapsed seconds (accepted-history timestamps)')
    fig.tight_layout()
    fig.savefig(OUTPUT/'hook_loss.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'report', 'figures', 'next'))
    parser.add_argument('--id')
    args = parser.parse_args()
    if args.action == 'run':
        print(run(args.id or next_run()), flush=True)
    elif args.action == 'report':
        print(report(), flush=True)
    elif args.action == 'figures':
        figures()
    else:
        print(next_run())
