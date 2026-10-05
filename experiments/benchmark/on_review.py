"""Read-only outside review of the ON-001/002/003 overnight evidence (2026-10-05).

Recomputes every number quoted in
``docs/iterations/cleaned_interfaces/iteration_31/02_claude_review.md`` from the
saved receipts. It performs no physics solves, fits or source changes. Truth
geometry is read only after the fact, to locate where saved accepted paths
diverged; it plays no part in any fit decision.

    PYTHONPATH=solvers:. python -m experiments.benchmark.on_review
"""
import argparse
import csv
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np

from bem_inverse.io import read, write, curve_from
from experiments.cleaned_interface import benchmark as ci

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT/'results'/'validation'/'cleaned_interfaces'
ON001, ON002, ON003, PC001 = (VALIDATION/n for n in ('ON-001', 'ON-002', 'ON-003', 'PC-001'))
OUTPUT = VALIDATION/'ON-review-20261005'
FAILURES = ('aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3', 'hook__c13.3')
SCREEN_SUCCESSES = ('circle__c4', 'kite__c0.5', 'star__c13.3', 'c_shape__c13.3')
REFERENCE_SUCCESS = 'hook__c4'
COMPONENTS = ('geometry', 'assembly', 'waves', 'factorization', 'fields')
F_PROBE_STEP_M = 1e-7  # unchanged endpoint FD step, ON-001 iteration 31 report
ON002_PATHS = ('docs/iterations/CI-SPD/iteration_01/03_plan.md',
               'docs/iterations/CI-SPD/iteration_02/00_adapter_contract.md',
               'experiments/benchmark/on002.py', 'experiments/benchmark/on002_adapter.py',
               'experiments/benchmark/test_on002.py', 'results/validation/cleaned_interfaces/ON-002/launch.json',
               'results/validation/cleaned_interfaces/ON-002/adapter128/summary.json')
ON002_INTERRUPTION = dict(
    source='~/.codex/sessions/2026/10/05/rollout-2026-10-05T02-38-38-01a109b6-8198-7941-b131-05c48e411911.jsonl',
    launch_utc='2026-10-05T01:39:26Z', event='turn_aborted', reason='interrupted',
    at_utc='2026-10-05T01:48:40.382Z')


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def on001_arms():
    """E/B pairing, accuracy trade, physics shares, solve kinds and screen work counts."""
    final = read(ON001/'final_comparison.json')
    rows = {r['id']: r for r in final['rows']}
    common = sorted(i for i, r in rows.items() if r['B']['recovered'] and r['E']['recovered'])
    metric = {arm: {key: np.array([rows[i][arm]['metrics'][key] for i in common])
                    for key in ('rms_mm', 'hausdorff_upper_mm')} for arm in 'BE'}
    threads = read(ON001/'all_B'/'runs'/common[0]/'fit_result.json')['physics']['execution']['frequency_threads']
    physics = {}
    for arm in 'BE':
        seconds = final['phase_totals'][arm]['physics_seconds']
        fit = final['phase_totals'][arm]['total_fit_seconds']
        total = sum(seconds[k] for k in COMPONENTS) + seconds['jacobian']
        share = seconds['assembly']/threads/fit
        physics[arm] = dict(
            thread_seconds={k: seconds[k] for k in (*COMPONENTS, 'jacobian')}, fit_seconds=fit,
            frequency_threads=threads, jacobian_share_of_physics=seconds['jacobian']/total,
            assembly_share_of_physics=seconds['assembly']/total,
            assembly_share_of_fit_estimate=share, fit_speedup_cap_if_assembly_free=1/(1-share),
            note='thread-summed seconds divided by frequency threads; an estimate, not a wall-time partition')
    solves = {}
    for arm in ('all_B', 'all_E'):
        tally = {}
        for path in sorted((ON001/arm/'runs').glob('*/fit_result.json')):
            for key, count in read(path)['fit_work']['solves'].items():
                kind = key.split(':', 1)[1]
                tally[kind] = tally.get(kind, 0)+count
        total = sum(tally.values())
        solves[arm] = dict(counts=tally, total=total,
                           refined_acceptance_share=tally.get('acceptance_validation', 0)/total)
    screens = {}
    for case in SCREEN_SUCCESSES+FAILURES:
        screens[case] = {}
        for arm in ('screen_B', 'screen_G', 'screen_E', 'screen_EW'):
            result = read(ON001/arm/'runs'/case/'fit_result.json')
            p = result['physics']
            screens[case][arm] = dict(
                outcome=result['outcome'], fit_seconds=result['fit_and_localization_seconds'],
                evaluations=p['counts']['evaluations'], derivatives=p['counts']['derivatives'],
                evaluation_thread_seconds=p['seconds']['evaluations'],
                derivative_thread_seconds=p['seconds']['derivatives'])
    same = lambda c, a, b: all(screens[c][a][k] == screens[c][b][k] for k in ('evaluations', 'derivatives'))
    return dict(
        e_exit=dict(
            common_recoveries=len(common), recovered=final['paired']['recovered'],
            regressions=final['recovery_regressions'], additions=final['recovery_additions'],
            median_paired_speedup=final['paired']['median_speedup'],
            p10_paired_speedup=final['paired']['p10_speedup'],
            total_audited_seconds=final['paired']['total_audited_seconds'],
            median_rms_mm={a: float(np.median(metric[a]['rms_mm'])) for a in 'BE'},
            max_rms_mm={a: float(metric[a]['rms_mm'].max()) for a in 'BE'},
            max_hausdorff_upper_mm={a: float(metric[a]['hausdorff_upper_mm'].max()) for a in 'BE'},
            median_rms_ratio_E_over_B=float(np.median(metric['E']['rms_mm']/np.maximum(metric['B']['rms_mm'], 1e-12))),
            geometry_refusals={a: final['phase_totals'][a]['geometry_refusals'] for a in 'BE'}),
        physics=physics, solves=solves, screens=screens,
        g_identical_work_on_screen_successes=all(same(c, 'screen_G', 'screen_B') for c in SCREEN_SUCCESSES),
        ew_more_evaluations_than_e=[c for c in SCREEN_SUCCESSES
                                    if screens[c]['screen_EW']['evaluations'] > screens[c]['screen_E']['evaluations']])


def stage_settings(run):
    plan = read(run/'plan.json')
    return {op['stage']['label']: op['stage'] for op in plan['operations'] if isinstance(op.get('stage'), dict)}


def stage_path(run, row):
    """Truth distance (post hoc) at the entry and exit of every executed fit stage."""
    path = []
    for record in read(run/'fit_result.json')['stages']:
        name = record['stage']
        if not (run/f'{name}.json').exists():
            continue
        data = read(run/f'{name}.json')
        accepted = [h for h in data['history'] if 'coefficients' in h]
        if not accepted:
            continue
        entry, exit_ = (ci.score(row, curve_from(h['coefficients'])) for h in (accepted[0], accepted[-1]))
        path.append(dict(stage=name, M=data['M'], K_geometry=data['K_geometry'],
                         accepted_steps=data['accepted_steps'], initial_loss=data['initial_loss'],
                         final_loss=data['final_loss'], outcome=data['outcome'], detail=data['detail'],
                         rms_mm=[entry['rms_mm'], exit_['rms_mm']],
                         hausdorff_mm=[entry['hausdorff_mm'], exit_['hausdorff_mm']]))
    return path


def killing_check(run, stage, settings):
    """The acceptance check and trial that raised the fatal resolution error."""
    data = read(run/f'{stage}.json')
    check, trial, base = data['acceptance_checks'][-1], data['trials'][-1], data['history'][-1]
    dp, dr = check['production_gain'], check['refined_gain']
    threshold = check['margin']+check['disagreement_allowance']
    tolerance = np.asarray(settings[stage]['discrepancy_tolerances'])
    discrepancy = np.asarray(check['prediction_discrepancy'])
    ratio = discrepancy/tolerance
    worst = int(np.argmax(ratio))
    return dict(
        stage=stage, detail=data['detail'], numerical_obstruction=check.get('numerical_obstruction'),
        trial_step_norm_m=trial['step_norm_m'], base_loss=base['loss'], trial_production_loss=trial.get('loss'),
        production_gain=dp, refined_gain=dr, relative_gain_disagreement=abs(dp-dr)/abs(dr),
        acceptance_threshold=threshold, acceptance_test_passes=bool(min(dp, dr) > threshold),
        gain_over_threshold=min(dp, dr)/threshold,
        worst_discrepancy=float(discrepancy[worst]), worst_tolerance=float(tolerance[worst]),
        worst_over_tolerance=float(ratio[worst]), worst_frequency_hz=settings[stage]['frequencies_hz'][worst],
        frequencies_over_tolerance=int((ratio > 1).sum()), frequency_count=len(tolerance),
        rule='acceptance(): min(production_gain, refined_gain) > margin + 5|production_gain - refined_gain|')


def nodal_response(case):
    """PC-001 N1: nodal Kress with the RB-001 resolution response (reject, then promote)."""
    run = PC001/'N1'/'runs'/case
    result = read(run/'result.json')
    residual = result.get('relative_residual')
    return dict(outcome=result['outcome'], detail=result.get('detail'), metrics=result.get('metrics'),
                final_audit_passed=result.get('final_audit_passed'), recovered=result.get('recovered'),
                maximum_residual=None if residual is None else float(max(residual)),
                total_seconds=result.get('total_seconds'), last_stage=result['stages'][-1]['stage'],
                nodes=[result['stages'][-1].get('nodes'), result['stages'][-1].get('refined_nodes')])


def failure_terminators():
    cases = {}
    for case in FAILURES+(REFERENCE_SUCCESS,):
        run = ON001/'all_B'/'runs'/case
        result = read(run/'result.json')
        settings = stage_settings(run)
        path = stage_path(run, result['case'])
        record = dict(outcome=result['outcome'], detail=result.get('detail'), recovered=result['recovered'],
                      final_metrics=result['metrics'], path=path)
        if case in FAILURES:
            record.update(killing=killing_check(run, path[-1]['stage'], settings), pc001_n1=nodal_response(case))
        cases[case] = record
    obstructions, runs = 0, 0
    final = read(ON001/'final_comparison.json')
    for row in final['rows']:
        if not row['B']['recovered']:
            continue
        run, runs = ON001/'all_B'/'runs'/row['id'], runs+1
        for record in read(run/'fit_result.json')['stages']:
            if (run/f"{record['stage']}.json").exists():
                data = read(run/f"{record['stage']}.json")
                obstructions += sum(bool(c.get('numerical_obstruction')) for c in data.get('acceptance_checks', []))
    pipelines = (ROOT/'solvers'/'bem_inverse'/'pipelines.py').read_text()
    return dict(cases=cases, successful_B_runs=runs, numerical_obstructions_in_successful_runs=obstructions,
                modal_fixed_has_no_resolution_response=("Pipeline('modal_fixed', 'modal_muller', 'certified_spectral', None"
                                                        in pipelines))


def damped_prefix():
    """Post-hoc truth distance at the end of the damped prefix and across the switch to real data."""
    final = read(ON001/'final_comparison.json')
    rows = {}
    for row in final['rows']:
        run = ON001/'all_B'/'runs'/row['id']
        result = read(run/'result.json')
        path = {s['stage']: s for s in stage_path(run, result['case'])}
        damped = [s for s in path if s.endswith('_damped')]
        record = dict(recovered=row['B']['recovered'], last_damped_stage=damped[-1],
                      rms_end_of_damped_mm=path[damped[-1]]['rms_mm'][1])
        if 'stage_4_undamped' in path and 'stage_4_damped' in path:
            real = path['stage_4_undamped']
            record.update(loss_jump=real['initial_loss']/path['stage_4_damped']['final_loss'],
                          rms_across_real_stage_mm=real['rms_mm'])
        rows[row['id']] = record
    successes = [r for r in rows.values() if r['recovered']]
    return dict(cases=rows,
                successes_max_rms_end_of_damped_mm=max(r['rms_end_of_damped_mm'] for r in successes),
                successes_loss_jump_range=[min(r['loss_jump'] for r in successes), max(r['loss_jump'] for r in successes)],
                successes_with_rms_increase_in_real_stage=[i for i, r in rows.items() if r['recovered']
                                                           and r['rms_across_real_stage_mm'][1] > r['rms_across_real_stage_mm'][0]])


def gaussian_map():
    out = {}
    for name in ('qualification_F', 'qualification_F_exact'):
        q = read(ON001/name/'qualification.json')
        rows = []
        for row in q['rows']:
            checks = [dict(label=c['label'], catalog=c['catalog'], passed=c['passed'],
                           full_trial_fd_relative=c.get('full_trial_fd_relative'),
                           alpha=c.get('gaussian', {}).get('gaussian_alpha'), C=c.get('gaussian', {}).get('gaussian_C'),
                           maximum_normal_m=c.get('gaussian', {}).get('maximum_normal_m'),
                           plus_alpha=c.get('plus_alpha'), minus_alpha=c.get('minus_alpha')) for c in row['checks']]
            rows.append(dict(case=row['case'], state=row['state'], M=row['M'], K=row['K'], controls=row['controls'],
                             width=row['width'], condition=row['condition'], passed=row['passed'], checks=checks))
        out[name] = dict(passed=sum(r['passed'] for r in rows), states=len(rows), rows=rows)
    endpoints = [r for r in out['qualification_F_exact']['rows'] if r['state'] == 'accepted_endpoint']
    probe = {r['case']: min(min(c['plus_alpha'], c['minus_alpha']) for c in r['checks']
                            if c['label'] == 'zero' and c['plus_alpha'] is not None) for r in endpoints}
    active = {r['case']: max(c['maximum_normal_m'] for c in r['checks'] if c['label'] == 'active')
              for r in endpoints if any(c['label'] == 'active' for c in r['checks'])}
    out['summary'] = dict(
        probe_step_m=F_PROBE_STEP_M, probe_clip_alpha_at_endpoints=probe,
        probe_saturation_displacement_m={c: a*F_PROBE_STEP_M for c, a in probe.items() if a < 1},
        active_check_displacement_m=active, maximum_condition=max(r['condition'] for r in out['qualification_F']['rows']),
        bound='C = exp(-1/2) * sum_j ||w_j|| / width; alpha = min(1, 0.8/C)',
        repair_trigger='half-width repair only on condition > 1e12 or interpolation error > 1e-4 (never fired)')
    return out


def ewald_truncation(assembly_share):
    """ON-003 measured circle errors beside the spectral-Ewald truncation term exp(-tau q_max^2)."""
    settings = read(ON003/'manifest.json')['settings']
    kstar, r0 = settings['k_star_per_m'], settings['R0_m']
    measured = {}
    with open(ON003/'operator_summary.csv') as f:
        for row in csv.DictReader(f):
            measured[(float(row['xi_over_kstar']), int(row['grid']), int(row['trace_cutoff']))] = {
                k: float(row[k]) for k in ('V_error_over_scale', 'K_error_over_scale', 'T_error_over_scale')}

    def term(ratio, grid, tau=None, r1=None):
        tau = 1/(4*(ratio*kstar)**2) if tau is None else tau
        r1 = r0+8*math.sqrt(tau) if r1 is None else r1
        period = 2.1*r1
        q = math.pi*grid/period
        return dict(tau_m2=tau, R1_m=r1, period_m=period, nyquist_per_m=q, tau_q2=tau*q*q,
                    truncation_term=math.exp(-tau*q*q), propagating_term=math.exp(-tau*(q*q-kstar*kstar)),
                    near_far_cancellation=math.exp(tau*kstar*kstar))

    registered = []
    for split in settings['split_geometries']:
        ratio = split['xi_over_kstar']
        for grid in (128, 256):
            row = dict(xi_over_kstar=ratio, grid=grid, **term(ratio, grid, split['tau_m2'], split['R1_m']))
            row['R1_formula_matches_manifest'] = abs(r0+8*math.sqrt(split['tau_m2'])-split['R1_m']) < 1e-12
            row['measured'] = {cut: measured[(float(ratio), grid, cut)] for cut in (64, 128)}
            registered.append(row)
    estimates = [dict(xi_over_kstar=r, grid=256, estimate=True, **term(r, 256)) for r in (0.5, 0.4, 0.35)]
    return dict(k_star_per_m=kstar, R0_m=r0, period_formula=settings['period_formula'], gate=1e-7,
                registered=registered, unregistered_estimates=estimates,
                fit_speedup_cap_if_assembly_free=1/(1-assembly_share),
                note='truncation_term is the Lindbo-Tornberg spectral-Ewald k-space tail; estimates are not measurements')


def tracked_links_to(target):
    """Tracked markdown files under docs/ whose relative links resolve to ``target``."""
    goal, hits = (ROOT/target).resolve(), []
    for name in git('ls-files', 'docs').split():
        if not name.endswith('.md'):
            continue
        path = ROOT/name
        for link in re.findall(r'\]\(([^)#\s]+)', path.read_text()):
            if not link.startswith(('http:', 'https:')) and (path.parent/link).resolve() == goal:
                hits.append(name)
                break
    return hits


def on002_status():
    tracked = set(git('ls-files', '--', *ON002_PATHS).split())
    summary = ON002/'adapter128'/'summary.json'
    adapter = None
    if summary.exists():
        data = read(summary)
        adapter = dict(fields_qualified=data.get('fields_qualified'), configurations=[
            dict(contrast=r['contrast'], catalog=r['catalog'], frequency_hz=r['frequency_hz'],
                 true_residual=r['true_residual'], physical_relative=r['physical_relative'],
                 iterations=[s['iterations'] for s in r['linear_stats']], field_passed=r['field_passed'])
            for r in data['records']])
        adapter['converged'] = sum(r['true_residual'] <= 1e-6 for r in adapter['configurations'])
        adapter['true_residual_range'] = [min(r['true_residual'] for r in adapter['configurations']),
                                          max(r['true_residual'] for r in adapter['configurations'])]
    interruption = dict(ON002_INTERRUPTION, verified=False)
    log = Path(ON002_INTERRUPTION['source']).expanduser()
    if log.exists():
        events = [json.loads(line) for line in log.read_text().splitlines() if '"turn_aborted"' in line]
        aborted = [e for e in events if e.get('payload', {}).get('type') == 'turn_aborted']
        interruption['verified'] = bool(aborted) and aborted[-1]['timestamp'] == ON002_INTERRUPTION['at_utc'] \
            and aborted[-1]['payload'].get('reason') == 'interrupted'
    return dict(paths={p: (p in tracked) for p in ON002_PATHS}, adapter128=adapter, interruption=interruption,
                tracked_docs_linking_untracked_plan=tracked_links_to(ON002_PATHS[0]))


def figure(failures, ewald, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    surface, ink, muted, spine = '#fcfcfb', '#0b0b0b', '#52514e', '#c9c8c2'
    colours = {'aphex_twin__c0.5': '#2a78d6', 'aphex_twin__c4': '#1baf7a', 'aphex_twin__c13.3': '#eb6834',
               'hook__c13.3': ink, REFERENCE_SUCCESS: muted}
    labels = {'aphex_twin__c0.5': 'aphex 0.5', 'aphex_twin__c4': 'aphex 4', 'aphex_twin__c13.3': 'aphex 13.3',
              'hook__c13.3': 'hook 13.3', REFERENCE_SUCCESS: 'hook 4 (recovered)'}
    # Frontier stages are generated during a fit, so take the longest executed schedule.
    schedule = [s['stage'] for s in read(PC001/'N1'/'runs'/'aphex_twin__c4'/'result.json')['stages']]
    for record in failures['cases'].values():
        schedule += [s['stage'] for s in record['path'] if s['stage'] not in schedule]
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': spine, 'axes.labelcolor': muted,
                         'xtick.color': muted, 'ytick.color': muted, 'text.color': ink})
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 5.2), facecolor=surface,
                               gridspec_kw=dict(width_ratios=[1.35, 1]))
    for ax in (a, b):
        ax.set_facecolor(surface)
        ax.grid(True, color=spine, linewidth=.5, alpha=.6)
        for side in ('top', 'right'):
            ax.spines[side].set_visible(False)

    dodge = {'aphex_twin__c0.5': -.12, 'aphex_twin__c13.3': .12}  # both end in stage 3 at ~4 mm
    label_offset = {'aphex_twin__c0.5': (-30, 7), 'aphex_twin__c13.3': (8, -10)}
    for case in (REFERENCE_SUCCESS,)+FAILURES:
        record = failures['cases'][case]
        x = [-0.6+dodge.get(case, 0)]+[schedule.index(s['stage'])+dodge.get(case, 0) for s in record['path']]
        y = [record['path'][0]['rms_mm'][0]]+[s['rms_mm'][1] for s in record['path']]
        style = dict(color=colours[case], linewidth=1.6 if case != REFERENCE_SUCCESS else 1.2,
                     linestyle='--' if case == REFERENCE_SUCCESS else '-', marker='o', markersize=4,
                     label=labels[case])
        a.plot(x, y, **style)
        if case in FAILURES:
            kill = record['killing']
            a.plot(x[-1], y[-1], marker='X', markersize=10, color=colours[case], markeredgecolor=surface)
            a.annotate(f"{kill['worst_over_tolerance']:.3g}x", (x[-1], y[-1]),
                       xytext=label_offset.get(case, (7, -3)), textcoords='offset points', fontsize=7.5, color=muted)
    n1 = failures['cases']['aphex_twin__c4']['pc001_n1']
    xn = schedule.index(n1['last_stage'])
    a.plot(xn, n1['metrics']['rms_mm'], marker='D', markersize=8, markerfacecolor=surface,
           markeredgecolor=colours['aphex_twin__c4'], markeredgewidth=1.6, linestyle='none',
           label='aphex 4 endpoint with nodal resolution response (PC-001 N1)')
    a.annotate(f"{n1['metrics']['rms_mm']:.2f} mm RMS,\nHausdorff upper {n1['metrics']['hausdorff_upper_mm']:.2f} mm",
               (xn, n1['metrics']['rms_mm']), xytext=(-12, -8), textcoords='offset points', fontsize=7,
               color=muted, ha='right', va='top')
    a.axhline(1, color=muted, linestyle=':', linewidth=1)
    a.text(len(schedule)-1, 1.12, 'RMS gate 1 mm', ha='right', fontsize=7, color=muted)
    a.set_yscale('log')
    short = [s.replace('warmup_025_damped', 'warm').replace('stage_', 'd').replace('_damped', '')
             .replace('_undamped', ' real').replace('release_', '').replace('fixed_', '') for s in schedule]
    a.set_xticks(range(len(schedule)), short, rotation=45, ha='right', fontsize=7)
    a.set_ylabel('RMS distance to truth (mm), post hoc')
    a.set_title('What ends the four TG-002 failures', loc='left', fontweight='bold', fontsize=11, color=ink, pad=26)
    a.text(0, 1.035, 'Baseline B paths. X = run killed by the absolute field gate (factor over 1e-7 shown);\n'
           'every killing trial reduced the loss and passed the acceptance test by 10^3 to 10^5',
           transform=a.transAxes, fontsize=7.5, color=muted)
    a.legend(loc='lower left', fontsize=7, frameon=False)

    ratios = np.geomspace(.3, 8, 200)
    kstar, r0 = ewald['k_star_per_m'], ewald['R0_m']
    tau = 1/(4*(ratios*kstar)**2)
    q = math.pi*256/(2.1*(r0+8*np.sqrt(tau)))
    b.axvspan(1, 8, color=spine, alpha=.25, linewidth=0)
    b.text(2.83, 3e-13, 'registered range', ha='center', fontsize=7, color=muted)
    b.plot(ratios, np.exp(-tau*q*q), color='#eda100', linewidth=1.8, label='truncation term exp(-tau q_max^2)')
    rows = [r for r in ewald['registered'] if r['grid'] == 256]
    b.plot([r['xi_over_kstar'] for r in rows], [r['measured'][128]['T_error_over_scale'] for r in rows],
           color='#2a78d6', marker='o', markersize=6, linewidth=1.6, label='measured worst T error / block scale')
    b.axhline(ewald['gate'], color=muted, linestyle=':', linewidth=1)
    b.text(8, 1.6e-7, 'circle-control gate 1e-7', fontsize=7, color=muted, ha='right')
    for row in ewald['unregistered_estimates']:
        if row['xi_over_kstar'] == .4:
            b.plot(.4, row['truncation_term'], marker='o', markersize=7, markerfacecolor=surface,
                   markeredgecolor='#eda100', markeredgewidth=1.6, linestyle='none')
            b.annotate(f"xi/k* = 0.4: term {row['truncation_term']:.0e} (estimate)",
                       (.4, row['truncation_term']), xytext=(10, 0), textcoords='offset points',
                       fontsize=7, color=muted, va='center')
    b.set_xscale('log', base=2)
    b.set_yscale('log')
    b.set_ylim(1e-14, 10)
    b.set_xlabel('split parameter xi / k*')
    b.set_title('ON-003 errors follow the Ewald truncation term', loc='left', fontweight='bold', fontsize=11,
                color=ink, pad=26)
    b.text(0, 1.035, '256 grid, trace cutoff 128. Only xi >= k* was registered;\n'
           'the unregistered side falls below the gate', transform=b.transAxes, fontsize=7.5, color=muted)
    b.legend(loc='upper left', fontsize=7, frameon=False)
    fig.text(.01, .01, 'Data: saved ON-001 all_B, PC-001 N1 and ON-003 receipts; truth used only after the fact; '
             'no new solves.', fontsize=7, color=muted)
    fig.tight_layout(rect=(0, .03, 1, 1))
    fig.savefig(path, dpi=150, facecolor=surface)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=OUTPUT)
    output = parser.parse_args(argv).output
    arms = on001_arms()
    failures = failure_terminators()
    prefix = damped_prefix()
    gaussian = gaussian_map()
    ewald = ewald_truncation(arms['physics']['B']['assembly_share_of_fit_estimate'])
    on002 = on002_status()
    for name, value in (('on001_arms', arms), ('failure_terminators', failures), ('damped_prefix', prefix),
                        ('gaussian_map', gaussian),
                        ('ewald_truncation', ewald), ('on002_status', on002)):
        write(output/f'{name}.json', value)
    kills = {c: failures['cases'][c]['killing'] for c in FAILURES}
    summary = dict(
        e_median_paired_speedup=arms['e_exit']['median_paired_speedup'],
        e_median_rms_mm=arms['e_exit']['median_rms_mm'],
        refined_acceptance_share_of_solves={a: arms['solves'][a]['refined_acceptance_share'] for a in arms['solves']},
        jacobian_share_of_physics_B=arms['physics']['B']['jacobian_share_of_physics'],
        assembly_share_of_fit_B=arms['physics']['B']['assembly_share_of_fit_estimate'],
        fit_speedup_cap_if_assembly_free_B=arms['physics']['B']['fit_speedup_cap_if_assembly_free'],
        g_identical_work_on_screen_successes=arms['g_identical_work_on_screen_successes'],
        killing_trials={c: dict(stage=k['stage'], acceptance_test_passes=k['acceptance_test_passes'],
                                gain_over_threshold=k['gain_over_threshold'],
                                worst_over_tolerance=k['worst_over_tolerance'],
                                relative_gain_disagreement=k['relative_gain_disagreement'],
                                rms_mm_at_abort=failures['cases'][c]['path'][-1]['rms_mm'][1]) for c, k in kills.items()},
        numerical_obstructions_in_successful_runs=failures['numerical_obstructions_in_successful_runs'],
        damped_prefix={k: prefix[k] for k in ('successes_max_rms_end_of_damped_mm', 'successes_loss_jump_range',
                                              'successes_with_rms_increase_in_real_stage')}
        | {c: prefix['cases'][c] for c in FAILURES},
        pc001_n1_aphex_c4=failures['cases']['aphex_twin__c4']['pc001_n1'],
        f_probe_clip_alpha=gaussian['summary']['probe_clip_alpha_at_endpoints'],
        f_active_check_displacement_m=gaussian['summary']['active_check_displacement_m'],
        ewald_256_cutoff128={r['xi_over_kstar']: dict(term=r['truncation_term'], T=r['measured'][128]['T_error_over_scale'])
                             for r in ewald['registered'] if r['grid'] == 256},
        ewald_estimates={r['xi_over_kstar']: r['truncation_term'] for r in ewald['unregistered_estimates']},
        on002_adapter_converged=None if on002['adapter128'] is None else on002['adapter128']['converged'],
        on002_interruption=on002['interruption'],
        on002_tracked=on002['paths'], on002_broken_links=on002['tracked_docs_linking_untracked_plan'])
    write(output/'summary.json', summary)
    figure(failures, ewald, output/'review_figure.png')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
