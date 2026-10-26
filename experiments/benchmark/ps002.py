"""PS-002: one GPU slider hook fit with <5% progress over two accepted iterations."""
import argparse
import os

from bem_inverse.io import read, write
from bem_inverse.physics import Execution
from . import campaign as c

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/PS-002'
BASELINE = c.ROOT/'results/validation/cleaned_interfaces/GU-002/slider'
CASE = 'hook__c13.3'
OPTIONS = dict(plain_progress_exit=True, progress_window=2, minimum_relative_progress=.05)


def run():
    if OUTPUT.exists():
        raise FileExistsError(f'Preserve existing evidence at {OUTPUT}; this driver permits one fresh run.')
    if any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')):
        raise RuntimeError('Set OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS to 1.')
    return c.run(OUTPUT, [CASE], solver='modal_muller', geometry_update='slider', localization='none',
                 execution=Execution(device='cuda', frequency_threads=4), workers=1,
                 cumulative_options=OPTIONS, experiment='PS-002: 5% progress over two accepted iterations, all stages')


def report():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    arms = {'GU-002 baseline': BASELINE, 'PS-002 5% / 2': OUTPUT}
    results = {name: read(folder/'runs'/CASE/'result.json') for name, folder in arms.items()}
    rows = {}
    for name, result in results.items():
        rows[name] = dict(outcome=result['outcome'], recovered=result['recovered'],
                         accepted_iterations=sum(s['accepted_steps'] for s in result.get('stages', [])),
                         fit_seconds=result.get('fit_and_localization_seconds'),
                         work_units=result.get('fit_and_localization_units'),
                         endpoint_passed=result.get('final_audit_passed'),
                         rms_mm=result.get('metrics', {}).get('rms_mm'),
                         hausdorff_upper_mm=result.get('metrics', {}).get('hausdorff_upper_mm'),
                         maximum_residual=result.get('maximum_residual'))
    a, b = rows.values()
    comparison = dict(arms=rows, fit_time_ratio=a['fit_seconds']/b['fit_seconds'] if b['fit_seconds'] else None,
                      options=OPTIONS, baseline_rerun=False)
    write(OUTPUT/'comparison.json', comparison)
    lines = ['# PS-002: 5% over two accepted iterations', '',
             'One new hook c13.3 fit on CUDA; comparison uses the saved GU-002 slider run.', '',
             '| Run | Recovered | Accepted iterations | Fit seconds | Work units | RMS mm |',
             '|---|---|---:|---:|---:|---:|']
    for name, r in rows.items():
        lines.append(f"| {name} | {r['recovered']} | {r['accepted_iterations']} | {r['fit_seconds']} | "
                     f"{r['work_units']} | {r['rms_mm']} |")
    lines += ['', f"Fit-time ratio (saved baseline / new): {comparison['fit_time_ratio']}.",
              'A ratio involving failed recovery is not a speedup to a recovered result.', '',
              'Only stage progress exits changed. The rule is active in every stage, including warm-up.',
              'K/M/Ku/F choices, scheduled LM damping, backtracking and final recovery checks are unchanged.',
              'Earlier exits change later curves; the dynamically selected final bands may therefore differ.', '',
              '| Stage | Baseline accepted | New accepted | New stop | New final loss |', '|---|---:|---:|---|---:|']
    old = {s['stage']: s for s in results['GU-002 baseline']['stages']}
    new = {s['stage']: s for s in results['PS-002 5% / 2'].get('stages', [])}
    for label in dict.fromkeys([*old, *new]):
        s = new.get(label, {})
        lines.append(f"| {label} | {old.get(label, {}).get('accepted_steps', '—')} | {s.get('accepted_steps', '—')} | "
                     f"{s.get('stop', '—')} | {s.get('final_loss', '—')} |")
    lines += ['', 'The baseline ran on the same machine earlier, rather than being rerun beside this fit.',
              'This one-case result does not establish performance on other TG-002 scenes.', '',
              '![Loss history](loss_vs_iteration.png)', '']
    (OUTPUT/'README.md').write_text('\n'.join(lines))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for ax, (name, folder) in zip(axes, arms.items()):
        offset = 0
        result = results[name]
        tail_start = None
        for s in result.get('stages', []):
            history = read(folder/'runs'/CASE/(s['stage']+'.json'))['history']
            xs = [offset+h['iteration'] for h in history]
            ax.semilogy(xs, [h['loss'] for h in history], marker='.', lw=1.5)
            if s['stage'].startswith('fixed_') and tail_start is None:
                tail_start = offset
            if s['accepted_steps'] and not s['stage'].startswith('fixed_'):
                ax.text((xs[0]+xs[-1])/2, 1.02,
                        s['stage'].replace('warmup_025_damped', 'warm-up').replace('stage_', 'D')
                        .replace('_undamped', ' real').replace('_damped', '').replace('release_', '').replace('fixed_', ''),
                        rotation=90, ha='center', va='bottom', transform=ax.get_xaxis_transform(), fontsize=8)
            if offset:
                ax.axvline(offset, color='.8', lw=.6, ls=':')
            offset += s['accepted_steps']
        if tail_start is not None:
            ax.text((tail_start+offset)/2, 1.02, 'M25–'+str(result['stages'][-1]['M']),
                    ha='center', va='bottom', transform=ax.get_xaxis_transform(), fontsize=8)
        ax.set_title(f"{name}: {offset} accepted, {rows[name]['fit_seconds']:.2f} s", pad=60)
        ax.set_ylim(1e-15, 2)
        ax.set_xlabel('Cumulative accepted iteration')
        ax.set_ylabel('Data loss (log scale)')
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Hook c13.3 | unchanged LM; earlier stage exits', y=.99)
    fig.text(.5, .015, 'Same loss scale; separate iteration axes. Lines break where stage objectives or update bands change.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .045, 1, .93))
    fig.savefig(OUTPUT/'loss_vs_iteration.png', dpi=170)
    fig.savefig(OUTPUT/'loss_vs_iteration.svg')
    plt.close(fig)
    return comparison


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'report'))
    args = parser.parse_args()
    print(run() if args.action == 'run' else report(), flush=True)
