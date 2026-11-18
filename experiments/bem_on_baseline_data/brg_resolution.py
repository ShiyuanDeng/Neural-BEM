"""Choose one BRG dataset resolution from true-shape forward checks only."""
import json
from pathlib import Path
import sys
import time
import numpy as np
from scipy.special import i0e

from brg_paper import (BASE, CASES, LADDER, GIB, SERIES_LOSS, ROOT, bulk_manifest,
                       context_for, digest, guarded, now, shape_info, solver_state, write,
                       qualifies_resolution)

OUT = BASE/'resolution_selection'


def admitted(case):
    info = shape_info(case)
    values = []
    refused = None
    for k in LADDER:
        x = k*info['wave_radius']
        loss = float(np.finfo(float).eps*i0e(x)*np.exp(x))
        if loss > SERIES_LOSS:
            refused = k
            break
        values.append(k)
    return values, refused


def prior_seconds(case):
    path = BASE/case/'forward/qualification.json'
    return json.loads(path.read_text())['wall_seconds'] if path.exists() else 0.


class Checks:
    def __init__(self):
        self.used = {case: prior_seconds(case) for case in CASES}
        self.peak = GIB
        self.cache = {}

    def one(self, K, case, k, phase):
        out = OUT/phase/f'trace_minimum_{K}'/case
        path = out/f'k_{k:g}.json'
        # Resume interrupted forward selection without repeating saved checks.
        if path.exists():
            row = json.loads(path.read_text())
            self.used[case] += row['wall_seconds']
            self.peak = max(self.peak, row['peak_rss_bytes'])
            return row, path
        profile = context_for('cpu', K).resolution_profile(shape_info(case)['true_curve_band'])
        key = (case, k, profile['production'], profile['refined'])
        state = solver_state()
        if key in self.cache and self.cache[key][0]['solver_end']['source_hashes'] == state['source_hashes']:
            return self.cache[key]
        remaining = 1800-self.used[case]
        if remaining <= 0:
            raise RuntimeError(f'30-minute accumulated forward budget reached for {case}')
        (out/'local').mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(ROOT/'experiments/bem_on_baseline_data/brg_paper.py'),
                   '_forward', '--case', case, '--one', str(k), '--trace-minimum', str(K), '--out', str(out)]
        receipt = guarded(command, out/'local'/f'k_{k:g}.log', remaining, expected_peak=self.peak)
        self.used[case] += receipt['wall_seconds']
        write(out/f'k_{k:g}_process.json', receipt)
        if not path.exists():
            raise RuntimeError(f'Forward process failed: {case} K={K} k={k}; {receipt}')
        row = json.loads(path.read_text())
        self.peak = max(self.peak, row['peak_rss_bytes'])
        self.cache[key] = row, path
        print(f'{phase} K={K} {case} k={k:g} pass={row["passes"]} '
              f'BRG={row.get("relative_brg_difference")} refine={row.get("relative_refinement_difference")} '
              f'exception={row.get("exception")}', flush=True)
        return row, path


def assessment(row, path):
    if 'relative_refined_brg_difference' not in row and 'relative_brg_difference' in row:
        arrays = np.load(path.parent/'local'/f'k_{row["k"]:g}.npz')
        row = dict(row, relative_refined_brg_difference=float(
            np.linalg.norm(arrays['refined']-arrays['observed'])/np.linalg.norm(arrays['observed'])))
    qualified = qualifies_resolution(row)
    result = dict(qualifies_resolution=qualified, brg_threshold_passes=row.get('relative_brg_difference', float('inf')) <= 1e-5,
                  refinement_threshold_passes=row.get('relative_refinement_difference', float('inf')) <= 1e-6,
                  brg_difference=row.get('relative_brg_difference'),
                  refined_brg_difference=row.get('relative_refined_brg_difference'),
                  refinement_difference=row.get('relative_refinement_difference'), source=str(path.relative_to(ROOT)))
    write(path.with_name(path.stem+'_assessment.json'), result)
    return result


def main():
    assert not (OUT/'fixed_resolution.json').exists(), 'Keep the fixed resolution; no inverse-driven changes.'
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    checks = Checks()
    reach = {case: admitted(case) for case in CASES}
    rule_path = OUT/'declared_rule.json'
    if rule_path.exists():
        rule_path = OUT/'declared_rule_with_recorded_brg_failures.json'
    write(rule_path, dict(started=now(), solver_start=solver_state(),
          candidate_minima=list(range(32, 257, 32)), margin=32, series_loss=SERIES_LOSS,
          thresholds=dict(brg=1e-5, refinement=1e-6),
          cases={case: dict(passing_series_prefix=v[0], first_series_refused_k=v[1], shape=shape_info(case))
                 for case, v in reach.items()},
          command=sys.argv, no_inverse_results_used=True))
    candidates = []
    try:
        for K in range(32, 257, 32):
            record = dict(K=K, passes=True, evidence=[])
            # High-eta glider is a cheap rejection witness; all cases still use one setting.
            order = ('glider_10', 'cavity_2', 'cavity_09', 'star_full', 'star_limited', 'glider_033')
            for case in order:
                for k in reversed(reach[case][0]):
                    row, path = checks.one(K, case, k, 'candidates')
                    record['evidence'].append(str(path.relative_to(ROOT)))
                    if not assessment(row, path)['qualifies_resolution']:
                        record.update(passes=False, failed_case=case, failed_k=k,
                                      failure=row.get('exception', 'forward/refinement threshold failed'))
                        break
                if not record['passes']:
                    break
            candidates.append(record)
            write(OUT/'candidate_summary.json', dict(candidates=candidates, used_seconds=checks.used))
            if record['passes']:
                break
        else:
            raise RuntimeError('No common trace_minimum at or below 256 passes; stop for coordinator.')
        fixed_K = K+32
        print(f'BASE K={K} passes all reachable checks. Fixed dataset K={fixed_K}; checking margin.', flush=True)
        qualifications = {}
        for case in CASES:
            rows, evidence, failed_brg = [], [], []
            for k in reach[case][0]:
                row, path = checks.one(fixed_K, case, k, 'final')
                assessed = assessment(row, path)
                if not assessed['qualifies_resolution']:
                    raise RuntimeError(f'Final margin setting failed: {case} k={k}; stop for coordinator.')
                if not assessed['brg_threshold_passes']:
                    failed_brg.append(dict(k=k, **assessed))
                if row['profile']['K_trace'] != fixed_K or row['profile']['K_trace_refined'] != fixed_K+32:
                    raise RuntimeError('Final minimum does not supply the declared production/refined cutoff.')
                rows.append(row)
                evidence.append(str(path.relative_to(ROOT)))
            refused = reach[case][1]
            if refused is not None:
                row, path = checks.one(fixed_K, case, refused, 'final')
                if 'Regular-wave series cancellation' not in row.get('exception', ''):
                    raise RuntimeError(f'Expected first series refusal differs for {case}: {row.get("exception")}')
                evidence.append(str(path.relative_to(ROOT)))
            qualifications[case] = dict(passes=True, passing_prefix=reach[case][0], cap=max(reach[case][0]),
                  first_refused_k=refused, evidence=evidence,
                  failed_brg_thresholds=failed_brg,
                  maximum_brg_difference=max(r['relative_brg_difference'] for r in rows),
                  maximum_refinement_difference=max(r['relative_refinement_difference'] for r in rows),
                  production_seconds=[r['production_seconds'] for r in rows],
                  refined_seconds=[r['refined_seconds'] for r in rows],
                  peak_rss_bytes=max(r['peak_rss_bytes'] for r in rows))
            write(OUT/'final'/f'trace_minimum_{fixed_K}'/case/'qualification.json', qualifications[case])
        write(OUT/'fixed_resolution.json', dict(passes=True, base_K=K, fixed_K=fixed_K,
              cases=qualifications, used_forward_seconds=checks.used,
              wall_seconds=time.monotonic()-started, solver_end=solver_state(),
              expected_fit_peak_bytes=1.2*max(v['peak_rss_bytes'] for v in qualifications.values())))
        print(f'QUALIFIED: fixed K={fixed_K}; peak worker={checks.peak/GIB:.3f} GiB', flush=True)
    except Exception as error:
        write(OUT/'selection_stop.json', dict(failure=repr(error), used_seconds=checks.used,
              wall_seconds=time.monotonic()-started, solver_end=solver_state()))
        print(f'STOP: {error}', flush=True)
        raise
    finally:
        for local in OUT.glob('*/*/*/local'):
            write(local.parent/'bulk_manifest.json', dict(files=bulk_manifest(local.parent)))


if __name__ == '__main__':
    main()
