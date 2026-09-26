"""Rebuild fresh-case outcomes without loading truth into any fitting decision."""
import importlib.util
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc044_analysis',HERE/'run.py')
r=importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    r.verify()
    rows=[]
    checks=[]
    prefixes={}
    for p in sorted((HERE/'runs').glob('*/*/prefix/result.json')):
        d=r.c.sc.read(p)
        prefixes[d['case'],d['profile']]=d
    for p in sorted((HERE/'runs').glob('*/*/*/result.json')):
        d=r.c.sc.read(p)
        if d['arm']=='prefix':continue
        prefix=prefixes[d['case'],d['profile']]
        last=d.get('stages',[{}])[-1]
        row=dict(case=d['case'],profile=d['profile'],arm=d['arm'],outcome=d['outcome'],score=d.get('score'),
            suffix_units=d['total_units'],prefix_units=prefix['total_units'],
            complete_path_units=prefix['total_units']+d['total_units'],audit_passed=d.get('audit_passed',False),
            loss=last.get('final_loss'),discrepancy_target=last.get('discrepancy_target'))
        rows.append(row)
        if 'stages' in d:
            checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='work',passed=bool(
                d['total_units']==sum(s['units'] for s in d['stages']) and all(s['units']<=380 for s in d['stages']))))
            if d['outcome']=='DISCREPANCY_REACHED':
                checks.append(dict(case=d['case'],profile=d['profile'],arm=d['arm'],check='discrepancy',
                                   passed=last['final_loss']<=last['discrepancy_target']))
    index={(s['case'],s['profile'],s['arm']):s for s in rows}
    comparisons=[]
    for case in r.CASES:
        for profile in r.PROFILES:
            baseline=index.get((case,profile,'none'))
            if baseline is None:continue
            for arm in ('boundary','cap'):
                candidate=index.get((case,profile,arm))
                if candidate is None:continue
                valid=bool(baseline['score'] and candidate['score'])
                comparisons.append(dict(case=case,profile=profile,arm=arm,comparable=valid,
                    rms_ratio=max(candidate['score']['rms_mm'],.01)/max(baseline['score']['rms_mm'],.01) if valid else None,
                    hausdorff_ratio=max(candidate['score']['hausdorff_mm'],.01)/max(baseline['score']['hausdorff_mm'],.01) if valid else None,
                    baseline_outcome=baseline['outcome'],candidate_outcome=candidate['outcome'],candidate_audit=candidate['audit_passed']))
    unique_prefix=sum(d['total_units'] for d in prefixes.values())
    suffix=sum(s['suffix_units'] for s in rows)
    failures=[dict(path=str(p.relative_to(HERE)),**r.c.sc.read(p)) for p in sorted((HERE/'runs').glob('*/*/*/failure.json'))]
    r.c.write(HERE/'analysis.json',dict(rows=rows,prefixes=list(prefixes.values()),comparisons=comparisons,failures=failures,
        unique_prefix_units=unique_prefix,suffix_units=suffix,checks=checks,checks_passed=all(s['passed'] for s in checks),
        complete=len(rows)==18))
    lines=['# SC-044 — fresh shapes and measurement noise','','| Shape | Data | State strategy | RMS mm | Hausdorff mm | Complete path work | Outcome | Audit |',
           '|---|---|---|---:|---:|---:|---|---|']
    for s in rows:
        scores=s['score']
        rms='—' if not scores else f"{scores['rms_mm']:.5g}"
        hd='—' if not scores else f"{scores['hausdorff_mm']:.5g}"
        lines.append(f"| {s['case']} | {s['profile']} | {s['arm']} | {rms} | {hd} | {s['complete_path_units']} | {s['outcome']} | {s['audit_passed']} |")
    lines+=['',f'Unique prefix work: {unique_prefix}; suffix work: {suffix}.',
            'Each complete path is charged its shared prefix. Two noise draws are repeated measurements of the same two shapes, not additional independent targets.','']
    (HERE/'TABLES.md').write_text('\n'.join(lines))
    print({'completed':len(rows),'failures':len(failures),'unique_prefix_units':unique_prefix,'suffix_units':suffix})


if __name__=='__main__':main()
