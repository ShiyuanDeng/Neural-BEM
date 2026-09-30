"""Recompute the CI-001 campaign summary from its saved comparison and run receipts.

Run from the repository root: ``python results/validation/cleaned_interfaces/CI-001-campaign-review/summarize.py``.
Reads only ``results/validation/cleaned_interfaces/CI-001``; writes ``summary.json`` beside this script.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
CAMPAIGN = ROOT / 'results/validation/cleaned_interfaces/CI-001'
OUT = Path(__file__).with_name('summary.json')


def main():
    comparison = json.loads((CAMPAIGN / 'comparison.json').read_text())
    rows = comparison['rows']
    regressions = []
    for row in rows:
        if row['status'] != 'REGRESSION':
            continue
        result = json.loads((CAMPAIGN / 'runs' / row['id'] / 'result.json').read_text())
        returned = [d for d in result['decisions'] if d.get('reason') == 'stage returned']
        last = returned[-1]
        details = last['operation']['details']
        residual = np.asarray(row['relative_residual'])
        limit = np.asarray(row['residual_retention_limits'])
        reference = np.asarray(row['reference_relative_residual'])
        expected = details.get('expected_noise_loss') or None
        regressions.append(dict(
            id=row['id'], outcome=row['outcome'],
            failed_gates=[k for k, v in row['gates'].items() if not v],
            rms_mm=row['rms_mm'], reference_rms_mm=row['reference_rms_mm'], rms_limit_mm=row['rms_mm_limit'],
            rms_better_than_reference=row['rms_mm'] < row['reference_rms_mm'],
            hausdorff_upper_mm=row['hausdorff_upper_mm'],
            reference_hausdorff_upper_mm=row['reference_hausdorff_upper_mm'],
            residual_failed_frequency_indices=np.flatnonzero(residual > limit).tolist(),
            maximum_residual=float(residual.max()), reference_maximum_residual=float(reference.max()),
            reference_below_one_percent_frequencies=int(np.sum(reference < 0.01)),
            last_fit=last['operation']['label'], last_fit_outcome=last['outcome'],
            last_fit_loss=last['final_loss'],
            expected_noise_loss=details.get('expected_noise_loss'),
            noise_threshold=details.get('noise_threshold'),
            # Loss of the final per-frequency residuals, 0.5*mean(r^2), relative to the expected noise loss.
            loss_over_expected_noise=expected and float(0.5 * np.mean(residual ** 2) / expected),
            reference_loss_over_expected_noise=expected and float(0.5 * np.mean(reference ** 2) / expected),
            reference_source=json.loads((ROOT / row['reference']).read_text())['source']))
    noisy = [r for r in regressions if r['outcome'] == 'NOISE_DISCREPANCY_REACHED']
    summary = dict(
        campaign=str(CAMPAIGN.relative_to(ROOT)),
        cases=comparison['cases'], completed=comparison['completed'], passed=comparison['passed'],
        recovered=sum(bool(r.get('recovered')) for r in rows),
        reference_recovered=sum(bool(r['reference_recovered']) for r in rows),
        all_36_numerical_retention=comparison['all_36_numerical_retention'],
        runtime_retention=comparison['runtime_retention'],
        summed_case_seconds=sum(r['total_seconds'] for r in rows),
        maximum_case_seconds=max(r['total_seconds'] for r in rows),
        noise_discrepancy_regressions=len(noisy),
        noise_regressions_rms_better=sum(r['rms_better_than_reference'] for r in noisy),
        noise_regressions_geometry_gate_failed=[r['id'] for r in noisy
                                                if {'rms_mm', 'hausdorff_upper_mm'} & set(r['failed_gates'])],
        regressions=regressions)
    OUT.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'regressions'}, indent=2))


if __name__ == '__main__':
    main()
