"""GU-001: three gauge-keeping geometry updates against spectral on hook c13.3.

Four arms, one run each, modal Müller physics (as ``modal_fixed``), centred start,
no grid search, default CumulativePolicy and the benchmark's endpoint audit:

    spectral    centred spectral update (rerun so times compare under the same load)
    uncentred   uncentred refit R(w_a)
    n_update    N-update with the level penalty
    slider      slider, xi = 10, Q = 32K

Plan: docs/iterations/geometry_updates/iteration_02/03_plan.md.

    python -m experiments.benchmark.gu001 run --arm spectral   # one process per arm, run in parallel
    python -m experiments.benchmark.gu001 report               # the plan's table and per-step logs
    python -m experiments.benchmark.gu001 videos               # one video per arm from saved history
"""
import argparse
import csv
import json

import numpy as np

from bem_inverse.continuation.geometry import speed_ratio
from bem_inverse.io import curve_from, read, write
from bem_inverse.level_penalty import FRACTION, unevenness
from bem_inverse.physics import Execution
from . import campaign as c, scenes as S

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/GU-001'
CASE = 'hook__c13.3'
ARMS = dict(spectral=dict(geometry_update='spectral'),
            uncentred=dict(geometry_update='uncentred_spectral'),
            n_update=dict(geometry_update='n_update', level_penalty=FRACTION),
            slider=dict(geometry_update='slider'))
# Four arms share eight cores: two frequency threads each.
EXECUTION = Execution(device='auto', frequency_threads=2)


def run(arm):
    return c.run(OUTPUT/arm, [CASE], solver='modal_muller', localization='none', execution=EXECUTION,
                 workers=1, experiment='GU-001 arm '+arm, **ARMS[arm])


def _curve(record):
    return curve_from(dict(real=record['real'], imag=record['imag']))


def steps(arm, output=OUTPUT, case=CASE):
    """One row per accepted curve (and each stage entry), in fit order, from the saved stage records."""
    folder = output/arm/'runs'/case
    rows = []
    for stage in read(folder/'result.json')['stages']:
        record = read(folder/(stage['stage']+'.json'))
        accepted = {t['iteration']: t for t in record['trials'] if t.get('status') == 'accepted'}
        for h in record['history']:
            curve = _curve(h['coefficients'])
            trial = accepted.get(h['iteration'], {}) if h['iteration'] else {}
            rows.append(dict(stage=stage['stage'], iteration=h['iteration'], loss=h['loss'],
                             data_loss=h.get('data_loss', h['loss']), penalty_loss=h.get('penalty_loss'),
                             speed_ratio=speed_ratio(curve), level_E=unevenness(curve.coefficients),
                             maximum_normal_mm=1e3*h['maximum_normal_m'] if 'maximum_normal_m' in h else None,
                             zero_step_jump_mm=trial.get('zero_step_jump_mm'),
                             crop_mm=trial.get('intentional_projection_mm'), coefficients=h['coefficients']))
    return rows


def failed_trial(arm, output=OUTPUT, case=CASE):
    """The trial curve the physics refused at the end of the fit, from its failure record."""
    folder = output/arm/'runs'/case
    last = read(folder/'result.json')['stages'][-1]['stage']
    trials = read(folder/(last+'.json'))['trials']
    if not trials or trials[-1].get('status') != 'physics_failed':
        return None
    return dict(trials[-1], coefficients=trials[-1]['physics_failures'][0]['candidate_coefficients'])


def summary(arm, output=OUTPUT, case=CASE):
    result = read(output/arm/'runs'/case/'result.json')
    rows = steps(arm, output, case)
    last = rows[-1]
    stage = result['stages'][-1]
    geometry = result['geometry_work']
    return dict(arm=arm, outcome=result['outcome'], stop=stage.get('stop'), last_stage=stage['stage'],
                detail=c._short(result.get('detail')), recovered=result['recovered'],
                audit=result.get('final_audit_passed'), data_loss=last['data_loss'], penalty_loss=last['penalty_loss'],
                rms_mm=result['metrics']['rms_mm'], hausdorff_mm=result['metrics']['hausdorff_mm'],
                fit_seconds=result['fit_and_localization_seconds'], fit_units=result['fit_and_localization_units'],
                geometry_seconds=geometry['preparation_seconds']+geometry['trial_seconds'],
                preparations=geometry['preparations'], trials=geometry['trial_constructions'],
                stage_speed_ratios={r['stage']: r['speed_ratio'] for r in rows},
                speed_ratio=speed_ratio(curve_from(result['final_curve'])),
                maximum_speed_ratio=max(r['speed_ratio'] for r in rows), final_E=last['level_E'],
                maximum_E=max(r['level_E'] for r in rows), accepted=sum(r['iteration'] > 0 for r in rows),
                maximum_zero_step_jump_mm=max((r['zero_step_jump_mm'] for r in rows
                                               if r['zero_step_jump_mm'] is not None), default=None),
                maximum_crop_mm=max((r['crop_mm'] for r in rows if r['crop_mm'] is not None), default=None))


def _g(value, spec):
    return '—' if value is None else format(value, spec)


def markdown(rows):
    lines = ['| Arm | Outcome | Data loss | RMS error (mm) | Max error (mm) | Fit time | Speed ratio |',
             '|---|---|---:|---:|---:|---:|---:|']
    for r in rows:
        outcome = f"{r['outcome']} ({r['stop'] or r['detail']}) in {r['last_stage']}"
        loss = _g(r['data_loss'], '.3g')+('' if r['penalty_loss'] is None else f" + penalty {r['penalty_loss']:.2g}")
        lines.append(f"| {r['arm']} | {outcome} | {loss} | {r['rms_mm']:.2f} | {r['hausdorff_mm']:.2f} | "
                     f"{r['fit_seconds']:.0f} s, {r['fit_units']} units | {r['speed_ratio']:.3f} |")
    lines += ['', '| Arm | Accepted steps | Max speed ratio | Final E | Max E | Max zero-step jump (mm) | '
              'Max crop (mm) | Geometry s | s per unit | Audit |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['arm']} | {r['accepted']} | {r['maximum_speed_ratio']:.3f} | {r['final_E']:.2e} | "
                     f"{r['maximum_E']:.2e} | {_g(r['maximum_zero_step_jump_mm'], '.3f')} | "
                     f"{_g(r['maximum_crop_mm'], '.2e')} | {r['geometry_seconds']:.0f} | "
                     f"{r['fit_seconds']/r['fit_units']:.3f} | {'passed' if r['audit'] else 'failed'} |")
    stages = list(dict.fromkeys(k for r in rows for k in r['stage_speed_ratios']))
    lines += ['', 'Speed ratio of the last accepted curve in each stage:', '',
              '| Stage | '+' | '.join(r['arm'] for r in rows)+' |', '|---|'+'---:|'*len(rows)]
    for stage in stages:
        lines.append(f'| {stage} | '+' | '.join(_g(r['stage_speed_ratios'].get(stage), '.3f') for r in rows)+' |')
    return '\n'.join(lines)+'\n'


def report():
    rows = [summary(arm) for arm in ARMS if (OUTPUT/arm/'runs'/CASE/'result.json').exists()]
    for arm in ARMS:
        if (OUTPUT/arm/'runs'/CASE/'result.json').exists():
            with open(OUTPUT/arm/'steps.csv', 'w', newline='') as handle:
                fields = [k for k in steps(arm)[0] if k != 'coefficients']
                writer = csv.DictWriter(handle, fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(steps(arm))
    write(OUTPUT/'report.json', dict(case=CASE, arms=rows))
    (OUTPUT/'table.md').write_text(markdown(rows))
    return markdown(rows)


def video(arm, output=OUTPUT, case=CASE, experiment='GU-001'):
    """Every accepted curve over the fit with the truth overlaid; a failed trial curve ends it."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter
    ink, muted, surface, accent, track = '#0b0b0b', '#52514e', '#fcfcfb', '#eda100', '#2a78d6'
    scene = case.split('__')[0]
    truth = S.CENTER+S.LENGTH*curve_from(read(c.INPUTS/'inputs'/scene/'truth.json')).values(2048)
    frames = [(r, False) for r in steps(arm, output, case)]
    failed = failed_trial(arm, output, case)
    if failed is not None:
        frames.append((dict(frames[-1][0], coefficients=failed['coefficients'], stage=frames[-1][0]['stage'],
                            speed_ratio=failed.get('speed_ratio', float('nan'))), True))
    fig, ax = plt.subplots(figsize=(6, 6), facecolor=surface)
    writer = FFMpegWriter(fps=8)
    with writer.saving(fig, str(output/arm/f'{arm}.mp4'), dpi=120):
        for number, (row, is_failed) in enumerate(frames):
            ax.clear()
            ax.set_facecolor(surface)
            z = S.CENTER+S.LENGTH*_curve(row['coefficients']).values(2048)
            ax.plot(100*np.r_[truth, truth[:1]].real, 100*np.r_[truth, truth[:1]].imag, color=track, lw=1.6,
                    label='truth')
            ax.plot(100*np.r_[z, z[:1]].real, 100*np.r_[z, z[:1]].imag, color='#c0392b' if is_failed else accent,
                    lw=1.4, label='failed trial curve' if is_failed else 'accepted curve')
            ax.set_xlim(*[100*S.CENTER.real+d for d in (-10, 10)])
            ax.set_ylim(*[100*S.CENTER.imag+d for d in (-10, 10)])
            ax.set_aspect('equal')
            ax.legend(loc='lower right', fontsize=8, frameon=False)
            ax.set_title(f"{experiment} {arm}, {case}", color=ink, fontsize=11, loc='left')
            label = 'FAILED TRIAL (physics refused)' if is_failed else f"loss {row['loss']:.3g}"
            ax.text(.02, .97, f"{row['stage']}  step {row['iteration']}\n{label}\nspeed ratio {row['speed_ratio']:.3f}",
                    transform=ax.transAxes, va='top', fontsize=9, color=muted)
            ax.set_xlabel('cm', color=muted)
            writer.grab_frame()
            if is_failed or number == len(frames)-1:
                for _ in range(15):  # hold the last frame
                    writer.grab_frame()
    plt.close(fig)
    return str(output/arm/f'{arm}.mp4')


def main():
    parser = argparse.ArgumentParser(description='GU-001 geometry updates on hook c13.3')
    parser.add_argument('command', choices=('run', 'report', 'videos'))
    parser.add_argument('--arm', choices=list(ARMS))
    args = parser.parse_args()
    if args.command == 'run':
        if not args.arm:
            parser.error('run needs --arm')
        print(json.dumps(run(args.arm), indent=2, default=str))
    elif args.command == 'report':
        print(report())
    else:
        for arm in ARMS:
            print(video(arm))


if __name__ == '__main__':
    main()
