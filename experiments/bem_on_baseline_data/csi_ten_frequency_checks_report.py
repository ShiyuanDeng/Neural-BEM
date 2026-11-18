"""Summarize the saved ten-frequency data and pre-fit checks; no solves."""
import hashlib,json
from pathlib import Path
root=Path('results/bem/baseline_data/csi_ten_frequency/2026-11-18')
data=Path('results/csi/tg002/2026-11-18_ten_frequency_data')
act=Path('docs/iterations/adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies')
shapes=['circle','star','kite','hook','peanut','asymmetric','c_shape','cross','cog','aphex_twin']
freq=[i/4 for i in range(1,11)]
rows=[]
for s in shapes:
    c=json.loads((root/f'adapter_checks/{s}__c4.json').read_text())
    assert c['summary']['adapter_checks_pass'] and c['summary']['one_percent_rule']
    values=[max(x['relative_mismatch'] for x in c['mismatch']['per_frequency'] if x['frequency_ghz']==f) for f in freq]
    rows.append(dict(shape=s,per_frequency=dict(zip(map(str,freq),values)),worst=max(values)))
record=dict(frequencies_ghz=freq,shapes=rows,worst_by_frequency={str(f):max(r['per_frequency'][str(f)] for r in rows) for f in freq},worst=max(r['worst'] for r in rows),all_pass=True)
(root/'check_summary.json').write_text(json.dumps(record,indent=2)+'\n')
files=[]
for p in sorted((root/'adapter_checks').glob('*.npz')):
    files.append(dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(root/'adapter_checks/bulk_manifest.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
lines=['| Shape | '+ ' | '.join(f'{f:g}' for f in freq)+' | Worst (%) |','|---|'+'---:|'*11]
for r in rows:
    lines.append('| '+r['shape']+' | '+' | '.join(f"{100*r['per_frequency'][str(f)]:.4f}" for f in freq)+f" | {100*r['worst']:.4f} |")
lines.append('| Worst per GHz | '+' | '.join(f"{100*record['worst_by_frequency'][str(f)]:.4f}" for f in freq)+f" | {100*record['worst']:.4f} |")
table='\n'.join(lines)
plan=json.loads((root/'policy_dry_check.json').read_text())
stages=['| Stage | GHz | Shape band | Quota |','|---|---|---:|---:|']
for s in plan['stages']:
    if 'M' in s:
        fs='0.25' if len(s['ghz'])==1 else f"0.25–{s['ghz'][-1]:g}, step 0.25"
        stages.append(f"| {s['label']} | {fs} | {s['M']} | {s['quota']} |")
stage_table='\n'.join(stages)
summary=json.loads((data/'summary.json').read_text())
text=f'''# Ten-frequency CSI tables and fits: results

18 November 2026. Runner: `bem-ten`. Plan: [plan.md](plan.md).
State: tables and checks complete; no fit started. Waiting for the coordinator's go.
The dry policy accepts band 0 at 0.25 GHz. No policy change was made.

## Data

Ten unchanged-CSI-forward tables at contrast 4, 0.25 to 2.5 GHz in 0.25 GHz steps.
Each has 17640 finite rows and the frozen 36-source, 49-receiver mask.
Order: circle, star, kite, hook, peanut, asymmetric, c_shape, cross, cog, aphex_twin.

Data runs: {summary['shapes'][0]['started_utc']} to {summary['shapes'][-1]['finished_utc']}.
Summed MATLAB wall time: {summary['summed_matlab_wall_seconds']:.3f} s.
Peak family RSS {summary['peak_family_gib']:.3f} GiB; minimum available {summary['minimum_available_gib']:.3f} GiB.

All 50 old-frequency blocks equal the frozen five-frequency tables byte for byte.
This holds in the raw generated tables and the final frozen tables; field differences are zero.
Each block has its own matching SHA-256 in the per-shape checks.

Maximum native residual: {summary['maximum_native_residual']:.6g}.
All runs record HEAD and a clean `solvers/bem_inverse/`.
Table and material bulk files remain local and ignored, with SHA-256 in each bulk manifest.

Circle exact-series errors at all ten frequencies and byte proofs: [data_note.md](data_note.md).
All circle errors pass 1%; worst is 0.44397601% at 0.5 GHz using the exact norm.
Data evidence: [summary](../../../../{data}/summary.json).

## BEM true-shape checks

Every entry is a percentage, worst over the two checked resolutions.
All ten shapes pass the adapter checks and the 1% rule at every frequency.
The largest mismatch is {100*record['worst']:.6f}% (Aphex Twin, 2.5 GHz).

{table}

Evidence: [check summary](../../../../{root}/check_summary.json).
Each `adapter_checks/<shape>__c4.json` retains both resolutions and provenance.
No CPU fit or tuning run was made.

## Dry plan

Same default wrapper and solver. Fixed work limit 13412; no elapsed-time stop.
The ten ladder quotas total 8000. All frequencies in each range advance by 0.25 GHz.
The first stage's band 0 is accepted by the unchanged policy.

{stage_table}

Before `full_4_M25`, the default cleanup runs; it has no fit quota.
After `full_6_M37`, the default frontier check uses two work units.
It may append bands 43, 49, 55, 61, 67, 73, 79, 85 or 91,
all ten frequencies, quota 304 each, within the same global work limit.

Evidence: [dry plan](../../../../{root}/policy_dry_check.json).
The plan is a dry construction, not proof that the optimizer completes band 0.
Any fit refusal stays a failure; there is no workaround or rerun.

## Fits

Not started. The coordinator must give the go after this check table and stage list.
Four planned GPU fits: circle, star, kite and hook, one pass each, sequentially.
Stage scores, final residuals and outline comparison remain pending.

Five-frequency references: circle 0.97%, star 2.34%, kite 3.80%, hook 3.59% area error.
The frequency-count question is unanswered until the ten-frequency fits finish.

## Failures kept

The first batch check was launched before star was frozen. Circle completed successfully;
then the command stopped on the missing star SHA-256 file, before a star check began.
The same command resumed after all tables were frozen and skipped the saved circle result.

No check was repeated. No forward table or fit was rerun.
Receipt: [launch failure](../../../../{root}/check_launch_failure.json).
There were no numerical data failures and no 1% failures.

```text
Activity: adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies
Runs: 10 data runs; 10 BEM true-shape checks; 1 dry plan; 0/4 fits
Result: all tables frozen; all old-frequency bytes equal; all checks pass; dry policy accepts band 0
Failures: one early batch launch stopped on pending star input; kept; no check repeated
Upstream patches: none
Changes to our code: two new data drivers, a thin BEM runner and a saved-check report script; existing code unchanged
New unknowns: ten-frequency outline quality and whether the optimizer completes the band-0 stage
Proposed next activity: coordinator go for the four planned GPU fits in this activity
```
'''
(act/'results.md').write_text(text)
print(table)
print(stage_table)
