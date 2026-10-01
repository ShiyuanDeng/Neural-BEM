"""Compare the modal_muller all-36 campaign (CI-001-modal) with the nodal CI-001 campaign.

Run from the repository root after ``report --output .../CI-001-modal``:
``python results/validation/cleaned_interfaces/CI-001-modal-review/summarize.py [CAMPAIGN OUTPUT]``.
Reads both campaign directories; writes ``summary.json`` beside this script, or
compares another modal campaign directory and writes OUTPUT.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
MODAL = ROOT/(sys.argv[1] if len(sys.argv) > 1 else 'results/validation/cleaned_interfaces/CI-001-modal')
NODAL = ROOT/'results/validation/cleaned_interfaces/CI-001'
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).with_name('summary.json')


def read(path):
    return json.loads(Path(path).read_text())


def stages(result):
    return [(s['stage'], s['outcome'], s['stop'], s['accepted_steps']) for s in result.get('stages', [])]


def divergence(modal, nodal):
    """First stage whose label, outcome, stop or accepted-step count differs."""
    a, b = stages(modal), stages(nodal)
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return dict(index=i, modal=x, nodal=y)
    if len(a) != len(b):
        return dict(index=min(len(a), len(b)), modal=a[len(b):][:1], nodal=b[len(a):][:1])
    return None


def discrepancy(run):
    """Largest LM production/refined prediction discrepancy over every stage of one case."""
    values = []
    for path in Path(run).glob('*.json'):
        record = read(path)
        if isinstance(record, dict):
            values += [max(c['prediction_discrepancy']) for c in record.get('acceptance_checks') or []]
    return max(values, default=None)


def frontier(result):
    rows = [d for d in result.get('decisions', []) if d['operation']['operation'] == 'frontier' and 'measured' in d]
    return rows[0]['measured']['frontier'] if rows else None


def main():
    modal_cmp, nodal_cmp = read(MODAL/'comparison.json'), read(NODAL/'comparison.json')
    nodal_rows = {r['id']: r for r in nodal_cmp['rows']}
    cases = []
    for row in modal_cmp['rows']:
        case, ref = row['id'], nodal_rows[row['id']]
        path = MODAL/'runs'/case/'result.json'
        if not path.exists():
            cases.append(dict(id=case, status='PENDING'))
            continue
        m, n = read(path), read(NODAL/'runs'/case/'result.json')
        receipt = m.get('physics', {})
        record = dict(id=case, panel=row['panel'], contrast=row['contrast'],
            status=row['status'], nodal_status=ref['status'], outcome=m.get('outcome'), nodal_outcome=n.get('outcome'),
            recovered=m.get('recovered'), nodal_recovered=n.get('recovered'),
            failed_gates=[k for k, v in row.get('gates', {}).items() if not v],
            nodal_failed_gates=[k for k, v in ref.get('gates', {}).items() if not v],
            rms_mm=row.get('rms_mm'), nodal_rms_mm=ref.get('rms_mm'),
            hausdorff_upper_mm=row.get('hausdorff_upper_mm'), nodal_hausdorff_upper_mm=ref.get('hausdorff_upper_mm'),
            maximum_residual=m.get('maximum_residual'), nodal_maximum_residual=n.get('maximum_residual'),
            units=m.get('total_units'), nodal_units=n.get('total_units'),
            seconds=m.get('total_seconds'), nodal_seconds=n.get('total_seconds'),
            fit_seconds=m.get('fit_and_localization_seconds'), nodal_fit_seconds=n.get('fit_and_localization_seconds'),
            frontier=frontier(m), nodal_frontier=frontier(n),
            localization_m=(m.get('localization') or {}).get('parameters_m'),
            nodal_localization_m=(n.get('localization') or {}).get('parameters_m'),
            stage_divergence=divergence(m, n), stages=len(stages(m)), nodal_stages=len(stages(n)),
            resolution_discrepancy=discrepancy(MODAL/'runs'/case), nodal_resolution_discrepancy=discrepancy(NODAL/'runs'/case),
            final_audit=m.get('final_audit_passed'), detail=(m.get('detail') or '')[-600:] or None,
            physics=dict(devices=receipt.get('devices'), fallbacks=receipt.get('fallback_reasons'),
                         failed_evaluations=receipt.get('counts', {}).get('failed_evaluations'),
                         failed_derivatives=receipt.get('counts', {}).get('failed_derivatives'),
                         stage_seconds=receipt.get('stage_seconds')))
        if record['localization_m'] and record['nodal_localization_m']:
            record['localization_difference_m'] = float(np.max(np.abs(np.subtract(record['localization_m'],
                                                                                  record['nodal_localization_m']))))
        if record['rms_mm'] is not None and record['nodal_rms_mm'] is not None:
            record['rms_difference_mm'] = record['rms_mm']-record['nodal_rms_mm']
        cases.append(record)
    done = [c for c in cases if c['status'] != 'PENDING']
    seconds = np.array([c['seconds'] for c in done])
    nodal_seconds = np.array([c['nodal_seconds'] for c in done])
    summary = dict(
        campaign=str(MODAL.relative_to(ROOT)), reference_campaign=str(NODAL.relative_to(ROOT)),
        completed=len(done), passed=sum(c['status'] == 'PASS' for c in done),
        nodal_passed=sum(nodal_rows[c['id']]['status'] == 'PASS' for c in done),
        recovered=sum(bool(c['recovered']) for c in done), nodal_recovered=sum(bool(c['nodal_recovered']) for c in done),
        same_status=sum(c['status'] == c['nodal_status'] for c in done),
        same_stage_decisions=sum(c['stage_divergence'] is None for c in done),
        same_units=sum(c['units'] == c['nodal_units'] for c in done),
        status_changes=[dict(id=c['id'], modal=c['status'], nodal=c['nodal_status'], failed_gates=c['failed_gates'],
                             nodal_failed_gates=c['nodal_failed_gates']) for c in done if c['status'] != c['nodal_status']],
        decision_divergences=[dict(id=c['id'], **c['stage_divergence']) for c in done if c['stage_divergence']],
        exceptions=[dict(id=c['id'], outcome=c['outcome'], detail=c['detail']) for c in done
                    if c['outcome'] in ('EXCEPTION', 'WORKER_EXCEPTION')],
        physics_problems=[dict(id=c['id'], **c['physics']) for c in done
                          if c['physics']['fallbacks'] or c['physics']['failed_evaluations'] or c['physics']['failed_derivatives']],
        summed_seconds=float(seconds.sum()), nodal_summed_seconds=float(nodal_seconds.sum()),
        median_case_speedup=float(np.median(nodal_seconds/seconds)),
        slowest_cases=sorted(({k: c[k] for k in ('id', 'seconds', 'nodal_seconds', 'units')} for c in done),
                             key=lambda c: -c['seconds'])[:5],
        maximum_rms_difference_mm=max((abs(c.get('rms_difference_mm', 0)) for c in done), default=None),
        runtime_note='Single unmatched runs on the same host; not the repeated matched-pair runtime gate.',
        cases=cases)
    OUT.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
