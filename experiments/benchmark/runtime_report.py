"""Per-scene runtime attribution for TG-002 run directories. Read-only; no fits or solves.

For each case the audited output time is split into exclusive phases that sum to it:
initial audit, early and terminal audits, the start stage, the damped frequency ladder,
the explicit real return, the full-catalog shape stages (net of their early audits),
other fitting work (localization, cleanup, frontier, bookkeeping) and the remainder
(setup and output). Alongside: the work that explains them (solves by category,
certificate and trial geometry seconds, refused proposals, stage entries).

For each run: the spread of recovered-case output times and an exact additive split of
its variance, Var(T) = sum_k Cov(T, c_k), by phase. For a pair of runs: recovery
changes, paired speedups on common recoveries, and whether the accepted paths are
identical, which is the acceptance test for an exact policy.

    python -m experiments.benchmark.runtime_report RUN_DIR [RUN_DIR ...] [--pair PARENT CHILD] [--out DIR]
"""
import argparse
import json
from pathlib import Path

import numpy as np

PHASES = ('initial_audit', 'early_audits', 'terminal_audits', 'start', 'ladder', 'return', 'shape', 'fit_other',
          'remainder')
CATEGORIES = ('initial_objective', 'candidate', 'acceptance_validation', 'derivative')


def _group(label):
    if label.startswith(('warmup', 'initialize')):
        return 'start'
    if label.endswith('_damped'):
        return 'ladder'
    if label.endswith('_undamped'):
        return 'return'
    return 'shape'


def case_row(result):
    """The attribution row of one ``result.json``; phases sum to the output time."""
    stages = result.get('stages') or []
    output = result.get('audited_output_seconds', result.get('total_seconds'))
    exclusive = result.get('exclusive_wall_seconds') or {}
    early = exclusive.get('early_audits', sum(a.get('seconds', 0.) for a in result.get('early_audits') or []))
    fit = exclusive.get('fit_and_localization', result.get('fit_and_localization_seconds', 0.))
    groups = dict.fromkeys(('start', 'ladder', 'return', 'shape'), 0.)
    shape_stages = entries = reused = steps = 0
    for stage in stages:
        group = _group(stage['stage'])
        groups[group] += stage['seconds']
        if group == 'shape':
            shape_stages += 1
            steps += stage['accepted_steps']
        entries += 1
        reused += bool(stage.get('entry_reused'))
    # Early audits run inside full-catalog stages but are excluded from fitting time.
    groups['shape'] = max(0., groups['shape']-early)
    phases = dict(initial_audit=exclusive.get('initial_audit', 0.), early_audits=early,
                  terminal_audits=exclusive.get('terminal_audits', 0.), **groups)
    phases['fit_other'] = fit-sum(groups.values())
    phases['remainder'] = (output or 0.)-sum(phases.values())
    work = result.get('fit_work') or {}
    solves = {c: 0 for c in CATEGORIES}
    for store in (work.get('solves') or {}, work.get('reciprocal_batches') or {}):
        for key, value in store.items():
            category = key.split(':', 1)[-1]
            if category in solves:
                solves[category] += value
    geometry = result.get('geometry_work') or {}
    counts = (result.get('physics') or {}).get('counts') or {}
    case = result.get('case') or {}
    metrics = result.get('metrics') or {}
    return dict(case=case.get('id', case) if isinstance(case, dict) else case, scene=case.get('case'),
        contrast=case.get('contrast'), recovered=bool(result.get('recovered')), outcome=result.get('outcome'),
        rms_mm=metrics.get('rms_mm'), output=output, fit=fit, phases=phases,
        last_stage=stages[-1]['stage'] if stages else None, shape_stages=shape_stages, shape_steps=steps,
        stage_entries=entries, entries_reused=reused, solves=solves,
        physics_evaluations=counts.get('evaluations'), certificate_seconds=geometry.get('certificate_seconds', 0.),
        trial_seconds=geometry.get('trial_seconds', 0.), refused_trials=geometry.get('refused_trials', 0),
        full_certificate_failures=geometry.get('full_certificate_failures', 0),
        promoted=any(e.get('action') == 'promoted' for s in stages for e in s.get('resolution_events', ())))


def load(run_dir):
    rows = {}
    for path in sorted(Path(run_dir).glob('runs/*/result.json')):
        result = json.loads(path.read_text())
        if 'stages' in result:
            row = case_row(result)
            rows[row['case']] = row
    return rows


def spread(rows):
    """Spread of recovered-case output times and the exact variance split by phase."""
    recovered = [r for r in rows.values() if r['recovered'] and r['output'] is not None]
    if not recovered:
        return dict(recovered=0)
    times = np.array([r['output'] for r in recovered])
    out = dict(recovered=len(recovered), minimum=float(times.min()), median=float(np.median(times)),
               maximum=float(times.max()), max_over_min=float(times.max()/times.min()),
               p10=float(np.percentile(times, 10)), p90=float(np.percentile(times, 90)),
               p90_over_p10=float(np.percentile(times, 90)/np.percentile(times, 10)),
               coefficient_of_variation=float(times.std()/times.mean()), total=float(times.sum()))
    variance = float(times.var())
    if variance > 0:
        out['variance_share'] = {p: float(np.mean((times-times.mean())*(np.array([r['phases'][p] for r in recovered]) -
                                 np.mean([r['phases'][p] for r in recovered]))))/variance for p in PHASES}
    out['phase_totals'] = {p: float(sum(r['phases'][p] for r in recovered)) for p in PHASES}
    out['failed_total'] = float(sum(r['output'] or 0. for r in rows.values() if not r['recovered']))
    return out


def _accepted(run_dir, case):
    path = Path(run_dir)/'runs'/case/'accepted.json'
    return json.loads(path.read_text())['states'] if path.exists() else None


def compare(parent_dir, child_dir):
    """Recovery changes, paired speedups and accepted-path identity, child against parent."""
    parent, child = load(parent_dir), load(child_dir)
    cases = sorted(set(parent) & set(child))
    rows, speedups = [], []
    for case in cases:
        a, b = parent[case], child[case]
        same_path = _accepted(parent_dir, case) == _accepted(child_dir, case)
        speedup = a['output']/b['output'] if a['recovered'] and b['recovered'] else None
        if speedup is not None:
            speedups.append(speedup)
        rows.append(dict(case=case, parent_recovered=a['recovered'], child_recovered=b['recovered'],
                         speedup=speedup, identical_accepted_path=same_path,
                         parent_output=a['output'], child_output=b['output']))
    return dict(parent=str(parent_dir), child=str(child_dir), common_cases=len(cases),
                regressions=[r['case'] for r in rows if r['parent_recovered'] and not r['child_recovered']],
                new_recoveries=[r['case'] for r in rows if r['child_recovered'] and not r['parent_recovered']],
                median_speedup=float(np.median(speedups)) if speedups else None,
                p10_speedup=float(np.percentile(speedups, 10)) if speedups else None,
                identical_paths=sum(r['identical_accepted_path'] for r in rows), rows=rows)


def markdown(name, rows, summary):
    lines = [f'## {name}', '',
             f'Recovered {summary.get("recovered", 0)}/{len(rows)}. Recovered output seconds: '
             + (f'min {summary["minimum"]:.2f}, median {summary["median"]:.2f}, max {summary["maximum"]:.2f} '
                f'(max/min {summary["max_over_min"]:.1f}x, p90/p10 {summary["p90_over_p10"]:.1f}x); '
                f'failed cases {summary["failed_total"]:.1f} s.' if summary.get('recovered') else 'none.'), '']
    if 'variance_share' in summary:
        lines += ['Share of the variance in recovered output time, by phase: ' +
                  ', '.join(f'{p} {100*v:.0f}%' for p, v in sorted(summary['variance_share'].items(),
                                                                    key=lambda kv: -kv[1]) if abs(v) >= .005) + '.', '']
    header = ['case', 'rec', 'output s'] + list(PHASES) + ['shape stages', 'steps', 'cert s', 'refused', 'last stage']
    lines += ['| ' + ' | '.join(header) + ' |', '|' + '---|'*len(header)]
    for r in sorted(rows.values(), key=lambda r: -(r['output'] or 0.)):
        lines.append('| ' + ' | '.join([r['case'], 'yes' if r['recovered'] else 'no', f'{r["output"]:.2f}'] +
                     [f'{r["phases"][p]:.2f}' for p in PHASES] +
                     [str(r['shape_stages']), str(r['shape_steps']), f'{r["certificate_seconds"]:.2f}',
                      str(r['refused_trials']), str(r['last_stage'])]) + ' |')
    return '\n'.join(lines)+'\n'


def report(run_dirs, pairs=(), out=None):
    value, text = dict(runs={}, pairs=[]), ['# Runtime attribution', '',
        'Read-only summary of saved receipts. Phases are exclusive and sum to each case\'s audited '
        'output time; shape stages are net of the early audits run inside them.', '']
    for run_dir in run_dirs:
        rows = load(run_dir)
        summary = spread(rows)
        value['runs'][str(run_dir)] = dict(summary=summary, rows=rows)
        text.append(markdown(Path(run_dir).name, rows, summary))
    for parent, child in pairs:
        result = compare(parent, child)
        value['pairs'].append(result)
        text += [f'## {Path(child).name} against {Path(parent).name}', '',
                 f'Common cases {result["common_cases"]}; regressions {result["regressions"] or "none"}; '
                 f'new recoveries {result["new_recoveries"] or "none"}; median paired speedup '
                 f'{result["median_speedup"] if result["median_speedup"] is None else round(result["median_speedup"], 3)}; '
                 f'identical accepted paths {result["identical_paths"]}/{result["common_cases"]}.', '']
    if out is not None:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out/'runtime_report.json').write_text(json.dumps(value, indent=1, default=str))
        (out/'runtime_report.md').write_text('\n'.join(text))
    return value, '\n'.join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--pair', nargs=2, action='append', default=[], metavar=('PARENT', 'CHILD'), type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    _, text = report(args.runs, args.pair, args.out)
    print(text)


if __name__ == '__main__':
    main()
