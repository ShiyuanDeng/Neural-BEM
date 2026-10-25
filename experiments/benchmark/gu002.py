"""GU-002: CUDA slider preparation and stronger level penalties on hook c13.3.

Plan: docs/iterations/geometry_updates/iteration_03/03_plan.md. Modal Müller physics
(as ``modal_fixed``) on CUDA, four frequency threads, centred start, no grid search,
default CumulativePolicy and the benchmark's endpoint audit. Run every command with
single-threaded BLAS (OMP/OPENBLAS/MKL_NUM_THREADS=1).

    python -m experiments.benchmark.gu002 compare              # saved-state CPU vs CUDA preparation, no fits
    python -m experiments.benchmark.gu002 run --arm slider     # one hook fit; timing arms run alone
    python -m experiments.benchmark.gu002 expand --method slider   # the three Aphex cases, if both directions work
    python -m experiments.benchmark.gu002 report               # tables from the saved results
    python -m experiments.benchmark.gu002 figure               # final curves from saved history
"""
import argparse
from dataclasses import replace
import json
import os
import subprocess

import numpy as np
import torch

from bem_inverse.continuation.geometry import FourierCurve, normal_basis, speed_ratio
from bem_inverse.geometry_update_methods import slider
from bem_inverse.io import curve_from, read, write
from bem_inverse.physics import Execution
from experiments.cleaned_interface import benchmark as ci
from . import campaign as c, gu001, scenes as S

OUTPUT = c.ROOT/'results/validation/cleaned_interfaces/GU-002'
CASE = gu001.CASE
APHEX = ('aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3')
FRACTIONS = (.1, 1., 10.)
EXECUTION = Execution(device='cuda', frequency_threads=4)
TIMING = ('spectral', 'slider_cpu', 'slider')  # each runs alone, after the comparison passes
ARMS = dict(spectral=dict(geometry_update='spectral', execution=EXECUTION),
            slider_cpu=dict(geometry_update='slider', execution=replace(EXECUTION, preparation_device='cpu')),
            slider=dict(geometry_update='slider', execution=EXECUTION),
            **{f'penalty_{f:g}': dict(geometry_update='n_update', level_penalty=f, execution=EXECUTION)
               for f in FRACTIONS})
# GU-001's slider stage-entry curves: (stage, update band M). Storage bands are 8, 192, 192.
STATES = (('stage_1_damped', 3), ('release_M11', 11), ('fixed_M67', 67))
REPEATS = 3
LIMITS = dict(relative_error=1e-6, curve_mm=1e-3)


def _single_threaded_blas():
    if any(os.environ.get(k) != '1' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')):
        raise SystemExit('Run GU-002 with OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1.')


def run(arm):
    _single_threaded_blas()
    if arm in TIMING and not _comparison_passed():
        raise SystemExit('The timing fits run only after the saved-state comparison passes.')
    return c.run(OUTPUT/arm, [CASE], solver='modal_muller', localization='none', workers=1,
                 experiment='GU-002 arm '+arm, **ARMS[arm])


def _comparison_passed():
    return (OUTPUT/'comparison.json').exists() and read(OUTPUT/'comparison.json')['passed']


def _environment():
    git = lambda *a: subprocess.check_output(['git', *a], cwd=c.ROOT, text=True).strip()
    return dict(ci.environment(), commit=git('rev-parse', 'HEAD'), status=git('status', '--short'))


def _bounded_update(curve, modes):
    """A fixed step whose requested normal push peaks at 0.1 mm."""
    a = np.cos(1+np.arange(2*modes+1))
    h = normal_basis(curve.nodes(slider.SAMPLES_PER_MODE*curve.band), modes)@a
    return 1e-4*a/np.max(np.abs(h))


def _speed_change_spread(curve, step):
    """RMS over arclength of the uneven part of the relative speed change dJ/J."""
    nodes = curve.nodes(slider.SAMPLES_PER_MODE*curve.band)
    tangent = nodes.tangents@np.array([1, 1j])
    relative = (FourierCurve(step).values(nodes.num_nodes, 1)*np.conj(tangent)).real/nodes.speeds
    weights = nodes.arc_length_weights/nodes.perimeter
    return float(np.sqrt(weights@(relative-weights@relative)**2))


def compare():
    """CPU (numpy lstsq) against CUDA (eigh) preparation at three saved states; no fits."""
    _single_threaded_blas()
    rows, settings = [], {}
    for stage, modes in STATES:
        curve = gu001._curve(read(gu001.OUTPUT/'slider'/'runs'/CASE/(stage+'.json'))['history'][0]['coefficients'])
        a = _bounded_update(curve, modes)
        by_device = {}
        for device in ('cpu', 'cuda'):
            update = slider.SliderUpdate(S.LENGTH, device=device)
            settings[device] = update.settings()
            first = update.prepare(curve, modes, curve.band)
            warm = [update.prepare(curve, modes, curve.band) for _ in range(REPEATS)]
            step = first.derivatives@a
            by_device[device] = dict(
                prepared=first, step=step, rank=first.rank, first_seconds=first.preparation_seconds,
                first_parts=first.seconds, seconds=float(np.median([w.preparation_seconds for w in warm])),
                parts={k: float(np.median([w.seconds[k] for w in warm])) for k in first.seconds},
                **update.measure(first, a), relative_speed_spread=_speed_change_spread(curve, step),
                speed_ratio=speed_ratio(FourierCurve(curve.coefficients+step)))
        cpu, cuda = by_device['cpu'], by_device['cuda']
        error = np.linalg.norm(cuda['prepared'].derivatives-cpu['prepared'].derivatives)/np.linalg.norm(
            cpu['prepared'].derivatives)
        count = 4096
        moved = {d: FourierCurve(curve.coefficients+v['step']).values(count) for d, v in by_device.items()}
        curve_mm = 1e3*S.LENGTH*float(np.max(np.abs(moved['cuda']-moved['cpu'])))
        large = curve.band >= 192
        row = dict(state=stage, K=curve.band, M=modes, size=2*(2*curve.band+1), rank_cpu=cpu['rank'],
                   rank_cuda=cuda['rank'], relative_error=float(error), curve_difference_mm=curve_mm,
                   maximum_normal_difference_m=abs(cuda['maximum_normal_m']-cpu['maximum_normal_m']),
                   rms_normal_difference_m=abs(cuda['rms_normal_m']-cpu['rms_normal_m']),
                   relative_speed_spread_difference=abs(cuda['relative_speed_spread']-cpu['relative_speed_spread']),
                   speed_ratio_difference=abs(cuda['speed_ratio']-cpu['speed_ratio']),
                   speedup=cpu['seconds']/cuda['seconds'], requires_speedup=large,
                   devices={d: {k: v for k, v in r.items() if k not in ('prepared', 'step')} for d, r in by_device.items()})
        row['accurate'] = bool(row['rank_cpu'] == row['rank_cuda'] and error <= LIMITS['relative_error']
                               and curve_mm <= LIMITS['curve_mm'])
        row['passed'] = row['accurate'] and (not large or cuda['seconds'] < cpu['seconds'])
        rows.append(row)
    result = dict(experiment='GU-002 saved-state comparison', limits=LIMITS, repeats=REPEATS, settings=settings,
                  bounded_update='requested normal push cos(1+l) over the 2M+1 coefficients, peak 0.1 mm',
                  states=rows, passed=all(r['passed'] for r in rows), environment=_environment())
    write(OUTPUT/'comparison.json', result)
    (OUTPUT/'comparison.md').write_text(comparison_markdown(result))
    return result


def comparison_markdown(result):
    lines = ['| State | K | M | Rank CPU / CUDA | Relative error | Curve difference (mm) | CPU s | CUDA s | '
             'Speedup | CUDA first use s | Passed |', '|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|']
    for r in result['states']:
        cpu, cuda = r['devices']['cpu'], r['devices']['cuda']
        lines.append(f"| {r['state']} | {r['K']} | {r['M']} | {r['rank_cpu']} / {r['rank_cuda']} | "
                     f"{r['relative_error']:.1e} | {r['curve_difference_mm']:.1e} | {cpu['seconds']:.4f} | "
                     f"{cuda['seconds']:.4f} | {r['speedup']:.1f} | {cuda['first_seconds']:.3f} | "
                     f"{'yes' if r['passed'] else 'no'} |")
    lines += ['', 'Median parts of a warmed preparation (s):', '',
              '| State | Device | Sampling | Transfer | Dense rows and products | Solve |', '|---|---|---:|---:|---:|---:|']
    for r in result['states']:
        for device in ('cpu', 'cuda'):
            p = r['devices'][device]['parts']
            lines.append(f"| {r['state']} | {device} | {p['sampling']:.4f} | {p['transfer']:.4f} | "
                         f"{p['dense']:.4f} | {p['solve']:.4f} |")
    lines += ['', 'CPU against CUDA, one bounded step (requested normal push peaking at 0.1 mm):', '',
              '| State | Max normal move diff (m) | RMS normal move diff (m) | Speed-change spread diff | '
              'Speed ratio diff |', '|---|---:|---:|---:|---:|']
    for r in result['states']:
        lines.append(f"| {r['state']} | {r['maximum_normal_difference_m']:.1e} | {r['rms_normal_difference_m']:.1e} | "
                     f"{r['relative_speed_spread_difference']:.1e} | {r['speed_ratio_difference']:.1e} |")
    return '\n'.join(lines)+'\n'


def _result(arm, case=CASE):
    path = OUTPUT/arm/'runs'/case/'result.json'
    return read(path) if path.exists() else None


def _release_seconds(result):
    """Cumulative fit seconds on entering release_M11 (the end of stage_4_undamped), or None if never entered."""
    stages = {record['stage']: record for record in result['stages']}
    return stages['stage_4_undamped']['work']['seconds'] if 'release_M11' in stages else None


def _crashed(result):
    """A run that ended without stage records (for example a worker exception)."""
    return 'stages' not in result or not result['stages']


def timing_row(arm):
    result = _result(arm)
    if _crashed(result):
        return dict(arm=arm, outcome=result.get('outcome'), detail=c._short(result.get('detail')), crashed=True)
    work = result['geometry_work']
    seconds, units = result['fit_and_localization_seconds'], result['fit_and_localization_units']
    return dict(arm=arm, outcome=result['outcome'], last_stage=result['stages'][-1]['stage'],
                recovered=result['recovered'], fit_seconds=seconds, units=units, seconds_per_unit=seconds/units,
                preparations=work['preparations'], preparation_seconds=work['preparation_seconds'],
                preparation_share=work['preparation_seconds']/seconds,
                parts={k: work[k] for k in ('sampling_seconds', 'transfer_seconds', 'dense_seconds', 'solve_seconds',
                                            'dropped_directions') if k in work},
                prepare_device=result['geometry_settings'].get('prepare_device'),
                to_release_seconds=_release_seconds(result),
                stage_seconds={s['stage']: s['seconds'] for s in result['stages']})


def penalty_row(arm, output=OUTPUT, case=CASE):
    result = read(output/arm/'runs'/case/'result.json')
    fraction = (result.get('level_penalty') or {}).get('fraction', ARMS.get(arm, {}).get('level_penalty'))
    if _crashed(result):
        return dict(arm=arm, fraction=fraction, outcome=result.get('outcome'), detail=c._short(result.get('detail')),
                    crashed=True)
    row = gu001.summary(arm, output, case)
    steps = gu001.steps(arm, output, case)
    last = read(output/arm/'runs'/case/(result['stages'][-1]['stage']+'.json'))['history'][-1]
    return dict(row, case=case, fraction=fraction, hausdorff_upper_mm=result['metrics'].get('hausdorff_upper_mm'),
                maximum_residual=result.get('maximum_residual'), penalty_weight=last.get('penalty_weight'),
                maximum_normal_mm=max((r['maximum_normal_mm'] for r in steps if r['maximum_normal_mm'] is not None),
                                      default=None),
                stage_data_losses={r['stage']: r['data_loss'] for r in steps})


def _ratio(a, b):
    return None if a is None or b is None else a/b


def report():
    lines = ['# GU-002 tables', '']
    if (OUTPUT/'comparison.json').exists():
        lines += ['## Saved-state preparation, CPU against CUDA', '', (OUTPUT/'comparison.md').read_text()]
    timing = {arm: timing_row(arm) for arm in TIMING if _result(arm) is not None}
    if timing:
        lines += ['## Hook c13.3 fits, one at a time on this machine', '',
                  '| Arm | Outcome in last stage | Recovered | Fit s | Units | s per unit | Preparations | '
                  'Preparation s | Share | s to release_M11 |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for r in timing.values():
            if r.get('crashed'):
                lines.append(f"| {r['arm']} | {r['outcome']}: {r['detail']} |"+' — |'*8)
                continue
            lines.append(f"| {r['arm']} | {r['outcome']} in {r['last_stage']} | {'yes' if r['recovered'] else 'no'} | "
                         f"{r['fit_seconds']:.1f} | {r['units']} | {r['seconds_per_unit']:.4f} | {r['preparations']} | "
                         f"{r['preparation_seconds']:.2f} | {100*r['preparation_share']:.1f}% | "
                         f"{gu001._g(r['to_release_seconds'], '.1f')} |")
        ratios = {}
        complete = {arm: r for arm, r in timing.items() if not r.get('crashed')}
        gpu_slider = complete.get('slider')
        if gpu_slider and 'slider_cpu' in complete:
            cpu = complete['slider_cpu']
            ratios['slider_cpu/slider'] = dict(
                fit=_ratio(cpu['fit_seconds'], gpu_slider['fit_seconds']),
                preparation=_ratio(cpu['preparation_seconds'], gpu_slider['preparation_seconds']),
                per_preparation=_ratio(cpu['preparation_seconds']/cpu['preparations'],
                                       gpu_slider['preparation_seconds']/gpu_slider['preparations']),
                to_release=_ratio(cpu['to_release_seconds'], gpu_slider['to_release_seconds']),
                seconds_per_unit=_ratio(cpu['seconds_per_unit'], gpu_slider['seconds_per_unit']))
        if gpu_slider and 'spectral' in complete:
            # Spectral stops in release_M11, so its total fit time is no like-for-like ratio.
            spectral = complete['spectral']
            ratios['spectral/slider'] = dict(
                to_release=_ratio(spectral['to_release_seconds'], gpu_slider['to_release_seconds']),
                seconds_per_unit=_ratio(spectral['seconds_per_unit'], gpu_slider['seconds_per_unit']))
        if ratios:
            lines += ['', 'Ratios above 1 mean the CUDA-preparation slider is faster:', '',
                      '| Ratio | Fit time | Preparation | Per preparation | Time to release_M11 | s per unit |',
                      '|---|---:|---:|---:|---:|---:|']
            for name, r in ratios.items():
                lines.append(f"| {name} | {gu001._g(r.get('fit'), '.2f')} | {gu001._g(r.get('preparation'), '.1f')} | "
                             f"{gu001._g(r.get('per_preparation'), '.1f')} | {gu001._g(r.get('to_release'), '.2f')} | "
                             f"{gu001._g(r.get('seconds_per_unit'), '.2f')} |")
        stages = list(dict.fromkeys(s for r in complete.values() for s in r['stage_seconds']))
        lines += ['', 'Seconds per stage:', '', '| Stage | '+' | '.join(complete)+' |', '|---|'+'---:|'*len(complete)]
        for stage in stages:
            lines.append(f'| {stage} | '+' | '.join(gu001._g(r['stage_seconds'].get(stage), '.1f')
                                                    for r in complete.values())+' |')
        write(OUTPUT/'timing.json', dict(arms=timing, ratios=ratios))
    penalties = [penalty_row(f'penalty_{f:g}') for f in FRACTIONS if _result(f'penalty_{f:g}') is not None]
    if penalties:
        reference = penalty_row('n_update', gu001.OUTPUT)  # fraction 0.01, Mac CPU: times do not compare
        rows = [reference]+penalties
        lines += ['', '## N-update with the level penalty on hook c13.3', '',
                  'Losses are at the last accepted curve, so they compare only where the last stage matches.', '',
                  '| Fraction | Outcome in last stage | Recovered | RMS (mm) | Hausdorff upper (mm) | Max residual | '
                  'Data loss | Penalty | Last stage weight | Max speed ratio | Final E | Max normal move (mm) | '
                  'Units | Fit s |', '|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r in rows:
            if r.get('crashed'):
                lines.append(f"| {r['fraction']:g} | {r['outcome']}: {r['detail']} |"+' — |'*12)
                continue
            lines.append(f"| {r['fraction']:g}{' (GU-001)' if r is reference else ''} | {r['outcome']} "
                         f"({r['stop'] or r['detail']}) in {r['last_stage']} | {'yes' if r['recovered'] else 'no'} | "
                         f"{r['rms_mm']:.4f} | {gu001._g(r['hausdorff_upper_mm'], '.4f')} | "
                         f"{gu001._g(r['maximum_residual'], '.2e')} | {r['data_loss']:.3g} | "
                         f"{gu001._g(r['penalty_loss'], '.2g')} | {gu001._g(r['penalty_weight'], '.2e')} | "
                         f"{r['maximum_speed_ratio']:.3f} | {r['final_E']:.2e} | "
                         f"{gu001._g(r['maximum_normal_mm'], '.3f')} | {r['fit_units']} | {r['fit_seconds']:.0f} |")
        rows = [r for r in rows if not r.get('crashed')]
        stages = list(dict.fromkeys(k for r in rows for k in r['stage_speed_ratios']))
        for title, key, spec in (('Data loss', 'stage_data_losses', '.3g'), ('Speed ratio', 'stage_speed_ratios', '.3f')):
            lines += ['', f'{title} of the last accepted curve in each stage:', '',
                      '| Stage | '+' | '.join(f"{r['fraction']:g}" for r in rows)+' |', '|---|'+'---:|'*len(rows)]
            for stage in stages:
                lines.append(f'| {stage} | '+' | '.join(gu001._g(r[key].get(stage), spec) for r in rows)+' |')
        write(OUTPUT/'penalty.json', dict(rows=rows, selected=selected_fraction()))
    fraction = selected_fraction()
    methods = [('slider', 'aphex_slider')]+([(f'penalty_{fraction:g}', f'aphex_penalty_{fraction:g}')] if fraction else [])
    expanded = [(folder, case) for _, folder in methods for case in APHEX if _result(folder, case) is not None]
    if expanded:
        lines += ['', '## Four-case comparison', '', '| Run | Case | Outcome in last stage | Recovered | RMS (mm) | '
                  'Units | Fit s |', '|---|---|---|---|---:|---:|---:|']
        for folder, case in [(hook, CASE) for hook, _ in methods]+expanded:
            r = _result(folder, case)
            if _crashed(r):
                lines.append(f"| {folder} | {case} | {r.get('outcome')}: {c._short(r.get('detail'))} | no | — | — | — |")
                continue
            lines.append(f"| {folder} | {case} | {r['outcome']} in {r['stages'][-1]['stage']} | "
                         f"{'yes' if r['recovered'] else 'no'} | {r['metrics']['rms_mm']:.4f} | "
                         f"{r['fit_and_localization_units']} | {r['fit_and_localization_seconds']:.0f} |")
    text = '\n'.join(lines)+'\n'
    (OUTPUT/'table.md').write_text(text)
    return text


def selected_fraction():
    """The smallest tested fraction whose hook fit meets the TG-002 recovery criteria, else None."""
    recovered = [f for f in FRACTIONS if (r := _result(f'penalty_{f:g}')) is not None and r.get('recovered')]
    return min(recovered) if recovered else None


def expand(method):
    """The plan's conditional step: run one frozen method on the three Aphex cases."""
    _single_threaded_blas()
    slider_fit, fraction = _result('slider'), selected_fraction()
    if not (_comparison_passed() and slider_fit and slider_fit.get('recovered') and fraction):
        raise SystemExit('Both directions must work first: comparison passed, slider and one weight recover hook.')
    arm = dict(slider=('aphex_slider', ARMS['slider']),
               penalty=(f'aphex_penalty_{fraction:g}', ARMS[f'penalty_{fraction:g}']))[method]
    return c.run(OUTPUT/arm[0], list(APHEX), solver='modal_muller', localization='none', workers=2,
                 experiment='GU-002 '+arm[0], **arm[1])


def figure():
    """The last accepted curve of each hook arm, with any curve the physics refused, against truth."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ink, muted, surface, accent, track, refused = '#0b0b0b', '#52514e', '#fcfcfb', '#eda100', '#2a78d6', '#c0392b'
    arms = [a for a in ('slider', *[f'penalty_{f:g}' for f in FRACTIONS])
            if _result(a) is not None and not _crashed(_result(a))]
    truth = S.CENTER+S.LENGTH*curve_from(read(c.INPUTS/'inputs'/CASE.split('__')[0]/'truth.json')).values(2048)
    fig, axes = plt.subplots(1, len(arms), figsize=(4*len(arms), 4.3), facecolor=surface, squeeze=False)
    for ax, arm in zip(axes[0], arms):
        row = gu001.steps(arm, OUTPUT)[-1]
        failed = gu001.failed_trial(arm, OUTPUT)
        ax.set_facecolor(surface)
        closed = lambda z: 100*np.r_[z, z[:1]]
        ax.plot(closed(truth).real, closed(truth).imag, color=track, lw=1.6, label='truth')
        z = S.CENTER+S.LENGTH*gu001._curve(row['coefficients']).values(2048)
        ax.plot(closed(z).real, closed(z).imag, color=accent, lw=1.4, label='last accepted curve')
        if failed is not None:
            z = S.CENTER+S.LENGTH*gu001._curve(failed['coefficients']).values(2048)
            ax.plot(closed(z).real, closed(z).imag, color=refused, lw=1., ls='--', label='refused trial curve')
        ax.set_xlim(*[100*S.CENTER.real+d for d in (-10, 10)])
        ax.set_ylim(*[100*S.CENTER.imag+d for d in (-10, 10)])
        ax.set_aspect('equal')
        ax.set_title(arm.replace('penalty_', 'level penalty '), color=ink, fontsize=11, loc='left')
        ax.text(.02, .97, f"{row['stage']}\nspeed ratio {row['speed_ratio']:.2f}", transform=ax.transAxes,
                va='top', fontsize=9, color=muted)
        ax.set_xlabel('cm', color=muted)
        ax.legend(loc='lower right', fontsize=7, frameon=False)
    fig.tight_layout()
    path = OUTPUT/'final_curves.png'
    fig.savefig(path, dpi=130, facecolor=surface)
    plt.close(fig)
    return str(path)


def main():
    parser = argparse.ArgumentParser(description='GU-002 CUDA slider preparation and level penalties on hook c13.3')
    parser.add_argument('command', choices=('compare', 'run', 'expand', 'report', 'figure'))
    parser.add_argument('--arm', choices=list(ARMS))
    parser.add_argument('--method', choices=('slider', 'penalty'))
    args = parser.parse_args()
    if args.command == 'compare':
        result = compare()
        print(comparison_markdown(result), 'passed' if result['passed'] else 'FAILED')
    elif args.command == 'run':
        if not args.arm:
            parser.error('run needs --arm')
        print(json.dumps(run(args.arm), indent=2, default=str))
    elif args.command == 'expand':
        if not args.method:
            parser.error('expand needs --method')
        print(json.dumps(expand(args.method), indent=2, default=str))
    elif args.command == 'report':
        print(report())
    else:
        print(figure())


if __name__ == '__main__':
    main()
