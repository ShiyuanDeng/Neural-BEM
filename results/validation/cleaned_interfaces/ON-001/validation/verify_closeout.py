import json,hashlib,tarfile
from pathlib import Path
from experiments.benchmark import campaign as c, scenes as S, on001 as O
from bem_inverse.io import read,digest
c.verify(require_inputs=True)
r=read(O.OUTPUT/'final_comparison.json')
assert r['complete'] and r['classification']=='useful partial result'
assert not r['historical_baseline_mismatch'] and not r['recovery_regressions'] and not r['recovery_additions']
assert r['by_contrast']=={'B':{'c0.5':9,'c4':9,'c13.3':8},'E':{'c0.5':9,'c4':9,'c13.3':8}}
assert r['all_pair_source_checks_passed'] and not r['cap_overshoots']
assert r['analysis_source_sha256']==digest(c.ROOT/'experiments/benchmark/reporting_on001.py')
assert all(x['paired_repetitions']==3 and x['minimum_speedup']>1 for x in r['repeated_case_stats'].values())
assert len(r['excluded_timing_samples'])==1
pairs=0;cases=0;archives={};fingerprints=set()
for prefix, selected in [('all',list(S.CASES)),('repeat1',['circle__c4','kite__c0.5','star__c13.3']),('repeat2',['circle__c4','kite__c0.5','star__c13.3']),('repeat_circle_uncontended',['circle__c4'])]:
 for arm in ('B','E'):
  folder=O.OUTPUT/f'{prefix}_{arm}';m=read(folder/'manifest.json')
  assert m['settings']==O.ARMS[arm] and m['inputs_sha256']==digest(c.INPUTS/'manifest.json')
  archive=c.ROOT/m['archive'];assert digest(archive)==m['archive_sha256'];archives[archive]=m['source_hashes']
  for case in selected:
   casefolder=folder/'runs'/case;v=read(casefolder/'result.json');fit=read(casefolder/'fit_result.json');pair=read(folder/'pairs'/(case+'.json'))
   assert v['arm']==arm and v['case']['id']==case and v['final_curve']==fit['final_curve']
   assert v['geometry_update']=='certified_spectral' and v['physics']['solver']=='modal_muller'
   assert v['fit_and_localization_seconds']<=120 and v['audit_seconds']<=30 and v['fit_work']['work_units']<=13412
   assert not v['localization'].get('grid_search',False)
   met=v['metrics'];expected=v['final_audit_passed'] and met['rms_mm']<=1 and met['hausdorff_upper_mm']<=2 and all(x<=y for x,y in zip(v['relative_residual'],v['residual_limits']))
   assert v['recovered']==bool(expected)
   assert pair['source_check_passed'];fingerprints.add(pair['source_fingerprint']);cases+=1
   if prefix!='all':assert v['recovered']
   if arm=='B':assert pair==read(O.OUTPUT/f'{prefix}_E'/'pairs'/(case+'.json'));pairs+=1
for archive, hashes in archives.items():
 with tarfile.open(archive,'r:gz') as tar:
  for name,expected in hashes.items():
   assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,(archive,name)
assert len(fingerprints)==1
print(json.dumps(dict(status='passed',confirmation_pairs=pairs,confirmation_case_receipts=cases,source_fingerprints=len(fingerprints),immutable_archives_verified=len(archives),eligible_repeats_per_selected_case=3,input_seal_verified=True,classification=r['classification']),indent=2))
