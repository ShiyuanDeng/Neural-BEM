"""Read-only end-of-run provenance and unchanged-normal replay audit."""
import hashlib,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'results/validation/shape_continuation'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

checks=[]
for name in ('SC-036-matched-finite-paths','SC-035-state-band','SC-037-later-state-release'):
    p=BASE/name/'manifest.json'
    if not p.exists():continue
    d=read(p)
    for section in ('sources','inputs'):
        mismatches=[path for path,h in d[section].items() if not (ROOT/path).exists() or sha(ROOT/path)!=h]
        checks.append(dict(bundle=name,kind=section,passed=not mismatches,mismatches=mismatches))
shared=read(BASE/'SC-036-logs/shared_environment.json')
mismatches=[p for p,h in shared['numerical_dependencies'].items() if sha(ROOT/p)!=h]
checks.append(dict(bundle='shared',kind='numerical_dependencies',passed=not mismatches,mismatches=mismatches))
for case in ('peanut','kite','circle_to_star','circle_to_c'):
    fresh=BASE/'SC-036-matched-finite-paths/inverse'/case/'normal/result.json'
    old=BASE/'SC-029-atlas-strategies/runs/baseline'/case/'none/result.json'
    if not fresh.exists():continue
    a,b=read(fresh),read(old)
    equal=a['final_curve']==b['final_curve']
    work=a['work']['work_units']==b['work']['work_units']
    changes=[]
    for i in range(1,5):
        pa=fresh.parent/f'stage_{i}_history.json';pb=old.parent/f'stage_{i}_history.json'
        if pa.exists() and pb.exists():
            ha,hb=read(pa)['history'],read(pb)['history']
            if [r['coefficients'] for r in ha]!=[r['coefficients'] for r in hb]:changes.append(i)
    checks.append(dict(bundle='SC-036',case=case,kind='normal_replay',passed=equal and work and not changes,
        identical_final_curve=equal,identical_work=work,changed_history_stages=changes))
output=BASE/'SC-036-logs/integrity_audit.json'
output.write_text(json.dumps(dict(passed=all(r['passed'] for r in checks),checks=checks),indent=2)+'\n')
for row in checks:print(row)
assert all(r['passed'] for r in checks),'integrity/replay mismatch'
