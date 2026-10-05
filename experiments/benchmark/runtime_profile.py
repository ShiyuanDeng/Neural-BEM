"""Historical read-only TG-002 profile and uncorrected lean-LM model.

Counters include audits, while the fit timer excludes them. The subtraction
below is retained to reproduce the historical draft, not as a measured fit
partition. See docs/iterations/CI-SPD/INVERSE_PIPELINE_AUDIT.md for correction.

Recomputes the numbers in
``docs/iterations/cleaned_interfaces/iteration_32/01_results.md`` from saved
ON-001 and RG-001 receipts and, when present, the GGB-001 case-8 evidence in the
local Gau-Gal checkout. No solves, fits or source changes.

    PYTHONPATH=solvers:. python -m experiments.benchmark.runtime_profile
"""
import argparse
import collections
import json
import math
from pathlib import Path

import numpy as np

from bem_inverse.io import read, write

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT/'results'/'validation'/'cleaned_interfaces'
ON001, RG001 = VALIDATION/'ON-001', VALIDATION/'RG-001'
OUTPUT = VALIDATION/'runtime-profile-20261005'
GGB8 = Path('/home/drdeng/Gau-Gal/docs/iterations/GGB-001/evidence/sample_0008/result.json')
FAILURES = {'aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3', 'hook__c13.3'}
COMPONENTS = ('assembly', 'waves', 'factorization', 'fields', 'geometry')
ROLES = ('moved_coarse', 'moved_fine', 'candidate')
TIERS = ('increment', 'full', 'sampled_accepted', 'sampled_refused', 'area_refused')
# Low / central / high model assumptions: refined-to-production solve cost r,
# removable fraction of trial geometry, and the physics wall-time estimate.
SCENARIOS = {'low': (1.0, .55, 'parallel'), 'central': (1.3, .66, 'residual'), 'high': (1.6, .70, 'residual')}


def receipts(arm):
    for path in sorted((ON001/arm/'runs').glob('*/fit_result.json')):
        yield path.parent.name, read(path)


def stage_files(run, fit):
    for record in fit['stages']:
        path = run/f"{record['stage']}.json"
        if path.exists():
            yield read(path)


def profile(arm='all_E'):
    """Fit-time shares, physics components, solve mix and geometry tiers by group."""
    out = {}
    for group in ('successes', 'failures'):
        t = collections.Counter()
        tiers = collections.Counter()
        for case, fit in receipts(arm):
            if (case in FAILURES) != (group == 'failures'):
                continue
            g, p = fit['geometry_work'], fit['physics']
            t['fit'] += fit['fit_and_localization_seconds']
            t['geometry_trial'] += g['trial_seconds']
            t['geometry_preparation'] += g['preparation_seconds']
            t['certificates'] += g['certificate_seconds']
            t['projections'] += g['projection_seconds']
            for k in (*COMPONENTS, 'evaluations', 'derivatives'):
                t['thread_'+k] += p['seconds'].get(k, 0.)
            for key, n in fit['fit_work']['solves'].items():
                t['solves_'+key.split(':', 1)[1]] += n
            for role in ROLES:
                for tier in TIERS:
                    tiers[f'{role}_{tier}'] += g.get(f'{role}_{tier}', 0)
        physics_wall = t['fit']-t['geometry_trial']-t['geometry_preparation']
        named = sum(t['thread_'+k] for k in COMPONENTS)
        solves = sum(v for k, v in t.items() if k.startswith('solves_'))
        out[group] = dict(
            totals=dict(t), tiers=dict(tiers),
            fit_share=dict(physics=physics_wall/t['fit'], geometry_trial=t['geometry_trial']/t['fit'],
                           geometry_preparation=t['geometry_preparation']/t['fit']),
            physics_thread_share={k: t['thread_'+k]/t['thread_evaluations'] for k in COMPONENTS}
            | dict(unnamed_overhead=(t['thread_evaluations']-named)/t['thread_evaluations'],
                   derivatives_vs_evaluations=t['thread_derivatives']/t['thread_evaluations']),
            solve_share={k[7:]: v/solves for k, v in t.items() if k.startswith('solves_')},
            increment_tier_share={r: tiers[f'{r}_increment']/max(1, sum(tiers[f'{r}_{x}'] for x in TIERS)) for r in ROLES})
    final = read(ON001/'final_comparison.json')
    rows = {r['id']: r for r in final['rows']}
    out['successes']['audited_output'] = sum(rows[c]['E']['audited_output_seconds'] for c in rows if c not in FAILURES)
    out['successes']['audits_and_setup'] = out['successes']['audited_output']-out['successes']['totals']['fit']
    return out


def decisions():
    """What each check and the halving actually decided in B/E/RG receipts."""
    refusals = {}
    for label, pattern in (('B', ON001/'all_B'/'runs'), ('E', ON001/'all_E'/'runs'), ('RG', RG001/'all'/'RG'/'runs')):
        c = collections.Counter()
        for path in pattern.glob('*/fit_result.json'):
            g = read(path)['geometry_work']
            for role in ROLES:
                c[role] += g.get(f'{role}_sampled_refused', 0)+g.get(f'{role}_area_refused', 0)
            for run_stage in stage_files(path.parent, read(path)):
                c['unresolved_projection'] += sum(t.get('reason') == 'unresolved_projection'
                                                  for t in run_stage.get('trials', []))
        refusals[label] = dict(c)
    margin = collections.Counter()
    ratios, backtracks, statuses = [], collections.Counter(), collections.Counter()
    for case, fit in receipts('all_E'):
        if case in FAILURES:
            continue
        for stage in stage_files(ON001/'all_E'/'runs'/case, fit):
            for t in stage.get('trials', []):
                statuses[t.get('status', 'none')] += 1
                if t.get('status') == 'accepted':
                    backtracks[t.get('backtrack')] += 1
            for c in stage.get('acceptance_checks', []):
                if c.get('accepted') or c.get('numerical_obstruction'):
                    continue
                dp, dr, m = c['production_gain'], c['refined_gain'], c['margin']
                margin['refined_reverses_sign' if dr <= 0 < dp else
                       'tiny_gain_below_margin' if min(dp, dr) <= m else 'resolution_disagreement'] += 1
                ratios.append(abs(dp-dr)/max(abs(dr), 1e-300))
    return dict(geometry_refusals_by_check=refusals, e_success_trial_statuses=dict(statuses),
                e_success_accepted_by_backtrack={str(k): v for k, v in sorted(backtracks.items())},
                e_success_margin_rejections=dict(margin),
                e_success_gain_disagreement_median=float(np.median(ratios)) if ratios else None)


def lean_model():
    """Per-case lean-LM prediction on the 26 E successes, plus suite totals."""
    final = read(ON001/'final_comparison.json')
    rows = {r['id']: r for r in final['rows']}
    successes = [c for c in rows if rows[c]['E']['recovered']]
    fail_out_e = sum(rows[c]['E']['audited_output_seconds'] for c in FAILURES)
    fail_out_rg = sum(read(RG001/'all'/'RG'/'runs'/c/'result.json')['audited_output_seconds'] for c in FAILURES)
    out = {}
    for name, (r, geometry_fraction, mode) in SCENARIOS.items():
        fit_old = fit_new = out_new = 0.
        fit_speedups, out_speedups, b_speedups = [], [], []
        for case in successes:
            fit = read(ON001/'all_E'/'runs'/case/'fit_result.json')
            g, p = fit['geometry_work'], fit['physics']
            t_fit = fit['fit_and_localization_seconds']
            residual = max(t_fit-g['trial_seconds']-g['preparation_seconds'], 0.)
            thread = p['seconds']['evaluations']+p['seconds']['derivatives']
            wall = residual if mode == 'residual' else min(residual, thread/p['execution']['frequency_threads'])
            s = fit['fit_work']['solves']
            n_ref = sum(v for k, v in s.items() if k.endswith(':acceptance_validation'))
            n_prod = sum(s.values())-n_ref
            cut = wall*n_ref*r/(n_prod+n_ref*r)+geometry_fraction*g['trial_seconds']
            new_fit, out_e = t_fit-cut, rows[case]['E']['audited_output_seconds']
            fit_old, fit_new, out_new = fit_old+t_fit, fit_new+new_fit, out_new+out_e-cut
            fit_speedups.append(t_fit/new_fit)
            out_speedups.append(out_e/(out_e-cut))
            b_speedups.append(rows[case]['B']['audited_output_seconds']/(out_e-cut))
        out[name] = dict(assumptions=dict(refined_cost_ratio=r, geometry_trial_removed=geometry_fraction,
                                          physics_wall=mode),
                         success_fit_seconds=[fit_old, fit_new], success_audited_output_new=out_new,
                         median_fit_speedup=float(np.median(fit_speedups)),
                         median_output_speedup_vs_E=float(np.median(out_speedups)),
                         median_output_speedup_vs_B=float(np.median(b_speedups)),
                         p10_output_speedup_vs_B=float(np.percentile(b_speedups, 10)),
                         suite_with_failures_to_cap=out_new+fail_out_rg,
                         suite_with_E_like_failure_stop=out_new+fail_out_e)
    out['reference'] = dict(E_suite=final['paired']['total_audited_seconds']['E'],
                            B_suite=final['paired']['total_audited_seconds']['B'],
                            failures_E_output=fail_out_e, failures_RG_output=fail_out_rg)
    return out


def ggb_case8():
    """Historical single-frequency far-start trajectory, if local evidence exists."""
    if not GGB8.exists():
        return None
    result = read(GGB8)
    stages = []
    for st in result['bem']['stages']:
        rel = [math.sqrt(2*h['loss']) for h in st['history']]
        sec = [(h.get('work') or {}).get('seconds') for h in st['history']]
        reasons = collections.Counter(t.get('reason') for t in st['trials'] if t.get('status') == 'refused')
        stall = next((i for i in range(5, len(rel)) if rel[i] > .98*rel[i-5]), None)
        stages.append(dict(stage=st['stage_label'], accepted=st['accepted_steps'], trials=len(st['trials']),
                           refusals=dict(reasons), seconds=st['seconds'], residual=[rel[0], rel[-1]],
                           residual_and_seconds_at_step_12=[rel[min(12, len(rel)-1)], sec[min(12, len(sec)-1)]],
                           stall_rule_2pct_step=stall, stall_rule_seconds=None if stall is None else sec[stall],
                           cap22_residual_and_seconds=[rel[min(22, len(rel)-1)], sec[min(22, len(sec)-1)]]))
    physics = result['bem']['physics_receipt']['seconds']
    return dict(fit_seconds=result['bem']['fit_seconds'], gaugal_optimization_seconds=result['gaugal']['optimization_sec'],
                physics_call_seconds=physics['evaluations']+physics['derivatives']+physics.get('failed_evaluations', 0.),
                final_residual=result['bem']['rel_data_error'], gaugal_residual=result['gaugal']['rel_data_error'],
                stages=stages)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=OUTPUT)
    output = parser.parse_args(argv).output
    summary = dict(status='HISTORICAL_UNCORRECTED_MODEL',
        accounting_limitation='Geometry/physics counters include audit work, while the fit timer excludes audits. '
            'Subtracting these counters from fit-only time does not yield measured component shares; '
            'the lean-LM forecasts inherit this limitation.',
        corrected_analysis='docs/iterations/CI-SPD/INVERSE_PIPELINE_AUDIT.md',
        profile_E=profile('all_E'), decisions=decisions(), lean_model=lean_model(), ggb_case8=ggb_case8())
    write(output/'summary.json', summary)
    print(json.dumps(dict(lean=summary['lean_model']['central'], decisions=summary['decisions']), indent=1)[:3000])


if __name__ == '__main__':
    main()
