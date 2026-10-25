"""NR-001 readings R1-R4 and predictions P1-P3 against PC-001 M1 (pre-registered plan).

Usage (repository root): python3 results/validation/cleaned_interfaces/NR-001/compare_pc001.py
Writes comparison.json and prints a Markdown table.
"""
import json
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
PC001 = HERE.parent/'PC-001'/'M1'
GATE_FAILURES = ('aphex_twin__c0.5', 'aphex_twin__c4', 'aphex_twin__c13.3', 'hook__c13.3')


def results(folder):
    return {p.parent.name: json.loads(p.read_text()) for p in sorted((folder/'runs').glob('*/result.json'))}


def row(r):
    m = r.get('metrics') or {}
    return dict(outcome=r.get('outcome'), recovered=r.get('recovered'), audit=r.get('final_audit_passed'),
                last_stage=(r.get('stages') or [{}])[-1].get('stage'), rms_mm=m.get('rms_mm'),
                hausdorff_upper_mm=m.get('hausdorff_upper_mm'), maximum_residual=r.get('maximum_residual'),
                fit_units=r.get('fit_and_localization_units'), total_units=r.get('total_units'),
                seconds=r.get('audited_output_seconds'))


def main():
    old, new = results(PC001), results(HERE/'M1')
    cases = [c for c in old if c in new]
    kept = [c for c in cases if old[c]['recovered'] and new[c]['recovered']]
    lost = [c for c in cases if old[c]['recovered'] and not new[c]['recovered']]
    gained = [c for c in cases if not old[c]['recovered'] and new[c]['recovered']]
    audit_failures = [c for c in cases if not new[c].get('final_audit_passed')]
    fit_old = [old[c]['fit_and_localization_units'] for c in kept]
    fit_new = [new[c]['fit_and_localization_units'] for c in kept]
    contrasts = sorted({new[c]['case']['contrast'] for c in cases})
    by_contrast = {str(k): sum(new[c]['recovered'] for c in cases if new[c]['case']['contrast'] == k) for k in contrasts}
    summary = dict(
        completed=len(new), compared=len(cases), recovered=sum(new[c]['recovered'] for c in cases),
        recovered_by_contrast=by_contrast,
        R1=dict(pc001_recovered=sum(old[c]['recovered'] for c in cases), kept=len(kept), lost=lost, gained=gained),
        R2={c: row(new[c]) for c in GATE_FAILURES if c in new},
        R3=dict(final_audit_failures=audit_failures),
        R4=dict(median_fit_units_pc001=median(fit_old) if fit_old else None,
                median_fit_units_nr001=median(fit_new) if fit_new else None,
                per_case={c: (old[c]['fit_and_localization_units'], new[c]['fit_and_localization_units'])
                          for c in cases}),
        P1=len(kept) >= 25 if len(cases) == 30 else 'pending',
        P2=(all(new[c]['outcome'] != 'NUMERICAL_FAILURE' or 'numerical-resolution' not in str(new[c].get('detail'))
                for c in GATE_FAILURES if c in new) and any(not new[c].get('final_audit_passed')
                                                            for c in GATE_FAILURES if c in new)),
        P3=bool(fit_new and median(fit_new) < median(fit_old)),
        rows={c: dict(pc001=row(old[c]), nr001=row(new[c])) for c in cases})
    (HERE/'comparison.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('| Case | PC-001 M1 | NR-001 | NR-001 last stage | audit | RMS mm | fit units (PC-001 → NR-001) |')
    print('|---|---|---|---|---|---:|---:|')
    for c in cases:
        a, b = row(old[c]), row(new[c])
        print(f"| {c} | {'rec' if a['recovered'] else a['outcome']} | {'rec' if b['recovered'] else b['outcome']} | "
              f"{b['last_stage']} | {b['audit']} | {b['rms_mm'] if b['rms_mm'] is None else round(b['rms_mm'], 4)} | "
              f"{a['fit_units']} → {b['fit_units']} |")
    print(json.dumps({k: v for k, v in summary.items() if k not in ('rows', 'R2', 'R4')}, indent=2))
    print(json.dumps(summary['R4'] | dict(per_case=None), indent=2))


if __name__ == '__main__':
    main()
