"""Rebuild SC-034 tables, decisions and figures from saved evidence (no fitting, no field solves).

Run from the repository root:
PYTHONPATH=solvers:. python results/validation/shape_continuation/SC-034-spd-legacy-controls/report.py
Truth enters only the saved scores and the evaluation-only boundary figure.
"""
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc

HERE = Path(__file__).resolve().parent
SC030 = sc.ROOT / 'results/validation/shape_continuation/SC-030-spd008-comparison/runs/repeat_0'
SC032 = sc.ROOT / 'results/validation/shape_continuation/SC-032-regularizing-metric-prefix/runs/R2'
CASES = ast.CASES
SPD_ARMS = ('L', 'S', 'LS')
STAR = dict(wrong_circle=True, circle_to_star=True, circle_to_c=False, kite=True, peanut=True, hook=False)
NAMES = dict(wrong_circle='Circle', circle_to_star='Star', circle_to_c='C', kite='Kite', peanut='Peanut', hook='Hook')
FLOOR, RECOVERED_MM, BOUND_MM = 0.01, 0.05, 2.0


def read(path):
    return json.loads(Path(path).read_text())


def folder(arm, case):
    return dict(SPD008=SC030 / case / 'spd008', R0=SC030 / case / 'hybrid_cache', R2=SC032 / case).get(
        arm, HERE / 'runs' / arm / case)


def result(arm, case):
    return read(folder(arm, case) / 'result.json')


def rms(row):
    return row.get('score', {}).get('symmetric_rms_mm')


def gm(pairs):
    values = [np.log(max(a, FLOOR) / max(b, FLOOR)) for a, b in pairs]
    return float(np.exp(np.mean(values))), float(np.exp(np.max(values)))


def states(path):
    spd = sc.spd_modules()[0].p
    return [spd.driver.deserialize_state(json.loads(line)['state']) for line in path.read_text().splitlines()]


def points(state, count=4096):
    return sc.spd_modules()[0].p.boundary_points(state, count)[0]


def high_mode_rms_mm(state):
    """Radial RMS above mode 5 about the component centre (circle/star truths have none)."""
    offsets = points(state) - np.asarray(state.components[0].center)
    angle, radius = np.arctan2(offsets[:, 1], offsets[:, 0]), np.hypot(*offsets.T)
    order = np.argsort(angle)
    grid = np.linspace(-np.pi, np.pi, 4096, endpoint=False)
    spectrum = np.fft.rfft(np.interp(grid, angle[order], radius[order], period=2 * np.pi)) / len(grid)
    spectrum[:6] = 0
    return float(1e3 * np.sqrt(2 * np.sum(np.abs(spectrum) ** 2)))


def moves_mm(sequence):
    """Largest distance from each accepted boundary to the previous one (a normal-move proxy)."""
    out = []
    for before, after in zip(sequence, sequence[1:]):
        out.append(float(1e3 * np.max(cKDTree(points(before, 8192)).query(points(after))[0])))
    return out


def stage_folders(arm, case):
    return sorted(folder(arm, case).glob('stage_*'))


def mechanism(arm, case):
    stage_1 = folder(arm, case) / 'stage_1' / 'trajectory.jsonl'
    sequence = states(stage_1)
    moves = moves_mm(sequence)
    return dict(stage_1_accepted=len(moves), stage_1_largest_move_mm=max(moves, default=0.),
                stage_1_end_high_mode_rms_mm=high_mode_rms_mm(sequence[-1]))


def safeguard_stats(arm, case):
    proposals, candidates, all_moves = [], [], []
    for stage in stage_folders(arm, case):
        path = stage / 'safeguards.jsonl'
        if path.exists():
            for row in map(json.loads, path.read_text().splitlines()):
                (proposals if row['kind'] == 'proposal' else candidates).append(row)
        trajectory = stage / 'trajectory.jsonl'
        if trajectory.exists():
            all_moves += moves_mm(states(trajectory))
    bound = BOUND_MM * 1e-3
    return dict(proposals=len(proposals),
                trust_region_binding_fraction=float(np.mean([p['maximum_normal_displacement_m'] >= .999 * bound
                                                             for p in proposals])) if proposals else None,
                damping_range=[min(p['damping'] for p in proposals), max(p['damping'] for p in proposals)]
                if proposals else None,
                armijo_refusals=sum(1 for c in candidates if c['realized_change'] < 0 and not c['sufficient_decrease']),
                largest_accepted_move_mm=max(all_moves, default=0.))


def main():
    rows, lines = {}, []
    for case in CASES:
        for arm in ('SPD008', *SPD_ARMS, 'R0', 'R2'):
            row = result(arm, case)
            rows[arm, case] = dict(status=row['status'], reason=row.get('reason'), rms_mm=rms(row),
                hausdorff_upper_mm=row.get('score', {}).get('hausdorff_upper_mm'),
                qualified=row.get('score', {}).get('training_numerically_qualified'),
                units=row.get('work_units', row.get('work', {}).get('work_units')),
                accepted=[s.get('accepted') for s in row.get('stages', [])])
    # H1: adoption of LS as the SPD comparison reference.
    h1 = {case: dict(completed=rows['LS', case]['status'] == 'COMPLETED_SCHEDULE',
                     rms_mm=rows['LS', case]['rms_mm'], qualified=rows['LS', case]['qualified'])
          for case in ('wrong_circle', 'circle_to_star')}
    for value in h1.values():
        value['pass'] = bool(value['completed'] and value['rms_mm'] is not None
                             and value['rms_mm'] <= RECOVERED_MM and value['qualified'])
    h1_pass = all(v['pass'] for v in h1.values())
    classes = {}
    for case in ('kite', 'peanut'):
        ls, r0 = rows['LS', case], rows['R0', case]
        classes[case] = ('solved_by_restored_baseline' if ls['status'] == 'COMPLETED_SCHEDULE' and ls['rms_mm'] is not None
                         and ls['rms_mm'] <= RECOVERED_MM and ls['qualified'] else
                         'baseline_better_not_solved' if ls['rms_mm'] is not None and ls['rms_mm'] < r0['rms_mm']
                         else 'open')
    ratios = {}
    for label, cases in (('all_six', CASES), ('star_shaped_four', [c for c in CASES if STAR[c]])):
        for numerator in SPD_ARMS:
            for denominator in ('SPD008', 'R0', 'R2'):
                pairs = [(rows[numerator, c]['rms_mm'], rows[denominator, c]['rms_mm']) for c in cases
                         if rows[numerator, c]['rms_mm'] is not None and rows[denominator, c]['rms_mm'] is not None]
                ratios[f'{label}:{numerator}/{denominator}'] = gm(pairs) if len(pairs) == len(cases) else None
    mechanisms = {f'{arm}:{case}': mechanism(arm, case) for arm in ('SPD008', *SPD_ARMS)
                  for case in CASES if STAR[case]}
    safeguards = {f'{arm}:{case}': safeguard_stats(arm, case) for arm in ('S', 'LS') for case in CASES}
    summary = dict(experiment='SC-034', rows={f'{a}:{c}': v for (a, c), v in rows.items()}, h1=h1,
                   h1_pass=h1_pass, hard_case_classes=classes, gm_ratios=ratios, mechanisms=mechanisms,
                   safeguards=safeguards)
    (HERE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')

    fmt = lambda x, p=3: '—' if x is None else (f'{x:.{p}g}' if isinstance(x, float) else str(x))
    lines.append('| Case | Star-shaped | ' + ' | '.join(['SPD-008', 'L', 'S', 'LS', 'Hybrid R0', 'Hybrid R2']) + ' |')
    lines.append('|---|---|' + '---:|' * 6)
    for case in CASES:
        cells = []
        for arm in ('SPD008', *SPD_ARMS, 'R0', 'R2'):
            row = rows[arm, case]
            mark = '' if row['status'] == 'COMPLETED_SCHEDULE' else f" ({row['reason']})"
            cells.append(f"{fmt(row['rms_mm'])}{mark}")
        lines.append(f"| {NAMES[case]} | {'yes' if STAR[case] else 'no'} | " + ' | '.join(cells) + ' |')
    lines += ['', 'RMS in mm. Hausdorff upper bound (mm) / work units / accepted steps by stage:', '',
              '| Case | Arm | Status | Hausdorff upper | Units | Accepted by stage | Endpoint qualified |',
              '|---|---|---|---:|---:|---|---|']
    for case in CASES:
        for arm in ('SPD008', *SPD_ARMS):
            row = rows[arm, case]
            lines.append(f"| {NAMES[case]} | {arm} | {row['status']}{'' if row['reason'] is None else ' / ' + str(row['reason'])}"
                         f" | {fmt(row['hausdorff_upper_mm'])} | {row['units']} | {row['accepted']} | {row['qualified']} |")
    lines += ['', '| GM RMS ratio (0.01 mm floor) | GM | Worst |', '|---|---:|---:|']
    for key, value in ratios.items():
        lines.append(f"| {key} | {fmt(None if value is None else value[0])} | {fmt(None if value is None else value[1])} |")
    lines += ['', '| Arm:case | Stage-1 accepted | Largest stage-1 move mm | Stage-1 end radial RMS above mode 5 mm |',
              '|---|---:|---:|---:|']
    for key, value in mechanisms.items():
        lines.append(f"| {key} | {value['stage_1_accepted']} | {value['stage_1_largest_move_mm']:.2f} | "
                     f"{value['stage_1_end_high_mode_rms_mm']:.3f} |")
    lines += ['', '| Arm:case | Proposals | Trust region binding | Damping range | Armijo refusals | Largest accepted move mm |',
              '|---|---:|---:|---|---:|---:|']
    for key, value in safeguards.items():
        lines.append(f"| {key} | {value['proposals']} | {fmt(value['trust_region_binding_fraction'])} | "
                     f"{'—' if value['damping_range'] is None else '%.2g–%.2g' % tuple(value['damping_range'])} | "
                     f"{value['armijo_refusals']} | {value['largest_accepted_move_mm']:.3f} |")
    lines += ['', f'H1 (LS recovers circle and star): **{"PASS" if h1_pass else "FAIL"}** — {json.dumps(h1)}',
              '', f'Kite/peanut classes: {json.dumps(classes)}']
    (HERE / 'tables.md').write_text('\n'.join(lines) + '\n')
    figure(rows)
    print('\n'.join(lines))


def figure(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Categorical slots 1-3 of the validated reference palette; truth in neutral ink.
    series = (('L', 'SPD, ladder only (L)', '#2a78d6'), ('LS', 'SPD, ladder + step controls (LS)', '#eb6834'),
              ('R0', 'Hybrid R0', '#1baf7a'))
    fig, axes = plt.subplots(2, 3, figsize=(11, 7.8))
    for axis, case in zip(axes.ravel(), CASES):
        truth = ast.curve_from(read(ast.source_folder(case) / 'truth.json')).values(2048) * sc.LENGTH + sc.CENTER
        axis.plot(1e3 * truth.real, 1e3 * truth.imag, color='#52514e', lw=1.4, ls=(0, (4, 3)), label='Truth')
        for arm, label, color in series:
            curve = ast.curve_from(result(arm, case)['final_curve']).values(2048) * sc.LENGTH + sc.CENTER
            axis.plot(1e3 * np.r_[curve.real, curve.real[0]], 1e3 * np.r_[curve.imag, curve.imag[0]], color=color,
                      lw=1.6, label=label)
        stop = lambda arm: '' if rows[arm, case]['status'] == 'COMPLETED_SCHEDULE' else '*'
        axis.set_title(f"{NAMES[case]}{'' if STAR[case] else ' (not star-shaped)'}\n"
                       f"RMS mm: L {rows['L', case]['rms_mm']:.2g}{stop('L')}, LS {rows['LS', case]['rms_mm']:.2g}{stop('LS')}, "
                       f"R0 {rows['R0', case]['rms_mm']:.2g}", fontsize=8.5, color='#0b0b0b')
        axis.set_aspect('equal')
        axis.tick_params(labelsize=7, colors='#52514e')
        for spine in axis.spines.values():
            spine.set_color('#c9c8c2')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, fontsize=9)
    fig.text(.5, .015, 'Coordinates in mm. * = hard stop (last accepted state shown). Truth is used only for this evaluation plot.', ha='center', fontsize=8,
             color='#52514e')
    fig.tight_layout(rect=(0, .03, 1, .95))
    fig.savefig(HERE / 'boundaries.png', dpi=150)


if __name__ == '__main__':
    main()
