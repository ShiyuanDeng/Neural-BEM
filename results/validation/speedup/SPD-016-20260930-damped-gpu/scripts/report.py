"""Build all available primary and field-arm comparisons from retained results."""
import datetime
import hashlib
import json
from pathlib import Path
import compare as C

BUNDLE=Path(__file__).resolve().parents[1]
rows=[]
for tag,scene in [('c0.5','shifted_star'),('c13.3','new_asymmetric')]:
    reference=BUNDLE/'runs/baseline/D'/tag/scene
    for mode in ['accelerated','fields']:
        candidate=BUNDLE/'runs'/mode/'D'/tag/scene
        if not (candidate/'result.json').exists() or not (reference/'result.json').exists():
            continue
        row=C.compare(candidate,reference)
        row.update(mode=mode,contrast=tag,scene=scene)
        if mode=='fields':
            row['vs_assembly_only']=C.compare(candidate,BUNDLE/'runs/accelerated/D'/tag/scene)
        rows.append(row)

commands=[]
for name in ['campaign.json','fields_campaign.json']:
    p=BUNDLE/name
    if p.exists():
        commands.extend(json.loads(p.read_text())['commands'])
for c in commands:
    if 'end_utc' in c:
        c['process_wall_seconds']=(datetime.datetime.fromisoformat(c['end_utc'])-datetime.datetime.fromisoformat(c['start_utc'])).total_seconds()
reference=json.loads((BUNDLE/'reference_manifest.json').read_text())
reference_failures=[p for p,h in reference['sources_and_inputs'].items() if hashlib.sha256((C.ROOT/p).read_bytes()).hexdigest()!=h]
script_checks={}
for name in ['scripts_manifest.json','fields_scripts_manifest.json']:
    p=BUNDLE/name
    if p.exists():
        manifest=json.loads(p.read_text())
        script_checks[name]=dict(count=len(manifest),failures=[s for s,h in manifest.items() if hashlib.sha256((BUNDLE/s).read_bytes()).hexdigest()!=h])
out=dict(pairs=rows,commands=commands,reference_files=len(reference['sources_and_inputs']),
         reference_failures=reference_failures,script_checks=script_checks)
(BUNDLE/'report.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
    print(r['mode'],r['contrast'],r['scene'],'quality',r['quality_pass'],'cost',r['cost_pass'],
          'seconds',round(r['reference_seconds']['total'],3),'->',round(r['candidate_seconds']['total'],3),
          'speedup',round(r['speedup'],3),'failed',[k for k,v in r['gates'].items() if not v])
print('REFERENCE_HASHES',len(reference['sources_and_inputs']),'FAILURES',reference_failures)
print('SCRIPT_HASHES',script_checks)
