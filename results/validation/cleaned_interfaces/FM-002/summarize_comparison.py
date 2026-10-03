"""Summarize sealed saved runs; never used to select or alter a fit."""
from pathlib import Path

import numpy as np

from experiments.cleaned_interface.fm002 import ARMS, CASES, INPUT, OUTPUT, verify
from experiments.cleaned_interface.io import digest, read, write


def main():
    verify(OUTPUT)
    manifest_hash = digest(OUTPUT / 'manifest.json')
    inputs, rows, baselines = {}, [], []
    for case in CASES:
        for arm in ARMS:
            path = OUTPUT / 'runs' / case / arm / 'result.json'
            result = read(path)
            assert result['manifest_sha256'] == manifest_hash
            inputs[str(path.relative_to(OUTPUT))] = digest(path)
            last = result['stages'][-1]
            rows.append(dict(
                case=case, arm=arm, outcome=result['outcome'],
                recovered=result['recovered'], paired_recovered=result['paired_recovered'],
                rms_mm=result['metrics']['rms_mm'],
                maximum_residual=result['maximum_residual'],
                elapsed_seconds=result['elapsed_seconds'],
                fit_seconds=result['fit_and_localization_seconds'],
                fit_units=result['fit_and_localization_units'],
                total_units=result['total_units'],
                last_stage=last['stage'], detail=result['detail'],
                final_audit_passed=result['final_audit_passed'],
                relaxed_gradient_calls=result['physics']['counts'].get('relaxed_gradients', 0),
                relaxed_gradient_seconds=result['physics']['seconds'].get('relaxed_gradients', 0),
                prefix=[{k: stage[k] for k in (
                    'stage', 'accepted_steps', 'stop', 'initial_loss', 'final_loss')}
                    for stage in result['stages'][:5]],
            ))
        old_path = INPUT / 'F' / 'runs' / case / 'result.json'
        old = read(old_path)
        new = read(OUTPUT / 'runs' / case / 'D0' / 'result.json')
        def decisions(result):
            return [(s['stage'], s['stop'], s['accepted_steps']) for s in result['stages']]
        delta = max(float(np.max(abs(np.asarray(old['final_curve'][part]) -
                                    np.asarray(new['final_curve'][part]))))
                    for part in ('real', 'imag'))
        baselines.append(dict(
            case=case, reference=str(old_path.relative_to(INPUT)), reference_sha256=digest(old_path),
            final_coefficient_max_abs_difference=delta,
            same_stage_stops_and_accepted_counts=decisions(old) == decisions(new),
            same_total_units=old['total_units'] == new['total_units'],
            same_outcome_and_recovery=(old['outcome'], old['recovered'], old['paired_recovered']) ==
                                     (new['outcome'], new['recovered'], new['paired_recovered']),
        ))
    totals = {}
    for arm in ARMS:
        selected = [row for row in rows if row['arm'] == arm]
        totals[arm] = dict(
            runs=len(selected), recovered=sum(row['recovered'] for row in selected),
            paired_recovered=sum(row['paired_recovered'] for row in selected),
            numerical_stops=sum(row['outcome'] == 'NUMERICAL_FAILURE' for row in selected),
            elapsed_seconds=sum(row['elapsed_seconds'] for row in selected),
            fit_units=sum(row['fit_units'] for row in selected),
            total_units=sum(row['total_units'] for row in selected),
            relaxed_gradient_calls=sum(row['relaxed_gradient_calls'] for row in selected),
            relaxed_gradient_seconds=sum(row['relaxed_gradient_seconds'] for row in selected),
        )
    write(OUTPUT / 'comparison.json', dict(
        completed=len(rows), scheduled=len(CASES) * len(ARMS),
        manifest_sha256=manifest_hash, script_sha256=digest(Path(__file__)),
        inputs=inputs, rows=rows, totals=totals, ordinary_baseline_regressions=baselines,
        runtime_scope='Single runs; another NU-007a campaign overlapped on the shared host. '
                      'No matched-runtime or speedup claim.',
        conclusion_scope='Three fixed cases, one penalty schedule, approximate curvature and '
                         'fixed resolution/work budgets; numerical stops are not convergence.',
    ))


if __name__ == '__main__':
    main()
