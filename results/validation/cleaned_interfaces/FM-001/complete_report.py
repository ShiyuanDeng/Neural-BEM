"""Add explicit acquisition scopes to the sealed campaign's generated reports.

Run after `python -m experiments.cleaned_interface.fm001 report`.
This is external scoring/reporting only; no fit, gate threshold or result is changed.
"""
from pathlib import Path
import os
import numpy as np
from experiments.cleaned_interface.fm001 import OUTPUT, rows_for, verify, C_STARTS
from experiments.cleaned_interface import benchmark as b
from experiments.cleaned_interface.io import read, write, digest, curve_from

verify(OUTPUT)
summary=read(OUTPUT/'summary.json')
contracts={}
results={}
for arm in ('F','FRr'):
    rows=[]
    for case in rows_for(arm):
        p=OUTPUT/arm/'runs'/case['id']/'result.json'
        if not p.exists():
            continue
        r=read(p)
        old=read(b.DEFAULT_OUTPUT/'runs'/case['id']/'result.json')
        rows.append(dict(case=case['id'],full_recovered=r['recovered'],paired_recovered=r.get('paired_recovered',False),
                         old_recovered=old['recovered'],result_sha256=digest(p)))
    lost=[r['case'] for r in rows if r['old_recovered'] and not r['paired_recovered']]
    contracts[arm]=dict(completed=len(rows),scheduled=len(rows_for(arm)),full_recovered=sum(r['full_recovered'] for r in rows),
        paired_recovered=sum(r['paired_recovered'] for r in rows),legacy_paired_losses=lost,
        G2_full_matrix=summary[arm]['G2'],G2_unchanged_paired=bool(len(rows)==len(rows_for(arm)) and not lost),
        hypothetical_paired_stop_after=lost[1] if len(lost)>=2 else None,rows=rows)
    results[arm]={r['case']:r for r in rows}
    summary[arm].update(G2_scope='full-matrix observations and recorded full-matrix noise',
                       G2_unchanged_paired=contracts[arm]['G2_unchanged_paired'],
                       unchanged_paired_recovered=contracts[arm]['paired_recovered'],legacy_paired_losses=lost)
summary['retention_scope_note']='The executed stop rule uses full-matrix recovery. Re-evaluation on the unchanged paired observations is reported separately and must not be called retained when it loses cases.'
write(OUTPUT/'recovery_contracts.json',contracts)
write(OUTPUT/'summary.json',summary)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
row=next(r for r in b.descriptors() if r['id']==C_STARTS[0])
truth=curve_from(read(b.ROOT/row['truth']))
archive=curve_from(read(b.DEFAULT_OUTPUT/'runs'/row['id']/'result.json')['final_curve'])
fig,axes=plt.subplots(1,2,figsize=(10,4.5),sharex=True,sharey=True)
for ax,arm in zip(axes,('F','FRr')):
    p=OUTPUT/arm/'runs'/row['id']/'result.json'
    curves=[('Truth',truth,'black','-'),('CI-001',archive,'#d87919','--')]
    r=read(p) if p.exists() else None
    if r and 'final_curve' in r:
        curves.append((arm,curve_from(r['final_curve']),'#1964aa' if arm=='F' else '#9747a4','-'))
    for name,curve,color,style in curves:
        z=50*curve.values(4096); z=np.r_[z,z[0]]
        ax.plot(z.real,z.imag,label=name,color=color,linestyle=style,linewidth=1.6)
    title=arm+' / contrast 13.3 C'
    if r and 'metrics' in r:
        title+=f' / RMS {r["metrics"]["rms_mm"]:.5g} mm'
    ax.set(title=title,xlabel='x offset from origin (mm)',ylabel='y offset from origin (mm)')
    ax.set_aspect('equal'); ax.legend(fontsize=8,loc='lower left'); ax.grid(alpha=.2)
fig.tight_layout()
plot=OUTPUT/'C_endpoints.png'
fig.savefig(plot,dpi=170)
plt.close(fig)

radius=read(OUTPUT/'phase2/radius.json')
points=[p for p in radius['points'] if 'losses' in p]
radii=np.array([p['radius_units']*50 for p in points])
series=[kind+'_'+objective for kind in ('paired','full') for objective in ('real','damped_0.25','relaxed_3.0')]
upper=10**np.ceil(np.log10(max(p['losses'][name] for p in points for name in series)))
fig,axes=plt.subplots(1,2,figsize=(10.5,4.2),sharex=True,sharey=True)
for ax,kind in zip(axes,('paired','full')):
    for objective,label,color in [('real','Real','#333333'),('damped_0.25','Damped, gamma=0.25','#1964aa'),('relaxed_3.0','Relaxed, tau=3','#d87919')]:
        ax.semilogy(radii,[max(p['losses'][kind+'_'+objective],1e-30) for p in points],label=label,color=color,linewidth=1.2)
    ax.axvline(53,color='gray',linestyle=':',linewidth=.8)
    ax.set(title='Paired acquisition' if kind=='paired' else 'Full 24 x 24 acquisition',xlabel='Radius (mm)',ylim=(1e-3,upper))
    ax.grid(alpha=.2);ax.legend(fontsize=8,loc='lower right')
axes[0].set_ylabel('Normalized loss')
fig.suptitle('Contrast 13.3 disk, five frequencies; display crops losses below 1e-3',fontsize=12)
fig.tight_layout()
radius_plot=OUTPUT/'radius_detail.png'
fig.savefig(radius_plot,dpi=170)
plt.close(fig)

for report in (b.ROOT/'docs/iterations/cleaned_interfaces/iteration_18/01_results.md',b.ROOT/'docs/reports/overnight_2026-10-03.md'):
    original=report.read_text().splitlines()
    intro=['','**Acquisition finding:** F recovers the contrast-13.3 C from both starts with the unchanged damped CI-001 policy. '
           'This establishes that full acquisition is sufficient for that case under this policy; it does not establish universal landscape smoothing.','',
           '**Retention scope:** the executed G2 and two-loss stop rule use each arm’s full-matrix observations and recorded noise. '
           'The unchanged paired-data contract is a stricter, separate check. Do not describe an arm as preserving the original paired contract if that check loses cases.','']
    for arm,c in contracts.items():
        intro += [f'- **{arm}:** {c["full_recovered"]}/{c["completed"]} full-matrix recoveries; '
                  f'{c["paired_recovered"]}/{c["completed"]} unchanged-paired recoveries. '
                  f'G2(full)={c["G2_full_matrix"]}; G2(unchanged paired)={c["G2_unchanged_paired"]}. '
                  f'Historical paired-residual retention passes: {summary[arm]["paired_residual_retention_pass"]}/{c["completed"]}. '
                  f'Coverage: {c["completed"]}/{c["scheduled"]}.']
        if c['legacy_paired_losses']:
            intro += ['  Previously recovered cases lost under the unchanged paired contract: '+', '.join('`'+case+'`' for case in c['legacy_paired_losses'])+'.']
    intro += ['', 'In F, the four legacy-paired recovery losses are noisy cases that reached the full-data discrepancy stop; '
              'their geometry errors remain below 0.281 mm RMS. The extra receivers and full-data normalization/discrepancy rule '
              'change which residuals control stopping. The original diagonal also retains its original noise variance, '
              'whereas the new off-diagonal noise uses the full-matrix scale. No weights, tolerances or budgets were tuned to remove these regressions.','',
              'The executed stop rule did not stop F on these legacy-paired losses because its full-data recovery predicate remained true. '
              'Under an unchanged-paired interpretation, F would have stopped at its second such loss; the counterfactual stop case is recorded '
              'in `recovery_contracts.json`. Thus an unqualified claim that the original no-loss contract was preserved is not supported.','',
              'FRr changes both the prefix from damped to real data and the residual weighting. Its outcome applies to that combined schedule and frozen-weight linearization; this experiment does not isolate which change causes its failures.','',
              'All four FRr runs stopped when a trial candidate left the frozen numerical-resolution regime: at M43 for both C starts and the star, and M37 for the asymmetric case. Their saved endpoints passed the final numerical audit but failed recovery. The arm then stopped on its second previously recovered case lost; the remaining 13 cases were not run.','',
              '![C endpoint comparison]('+os.path.relpath(plot,report.parent)+')','']
    out=[original[0],*intro]
    arm=None; table=False
    for line in original[1:]:
        if line.startswith('## Arm '): arm=line.split()[-1]
        if line.startswith('| Case | Outcome | Recovered |'):
            table=True
            line=line.replace('| Recovered | RMS mm |','| Full recovery | Paired recovery | RMS mm |')
        elif table and line.startswith('|'):
            cells=line.split('|')
            if cells[1].strip().startswith('---'):
                cells.insert(4,'---:')
            else:
                case=cells[1].strip()
                r=results.get(arm,{}).get(case)
                cells.insert(4,' '+str(r['paired_recovered'])+' ' if r else ' — ')
            line='|'.join(cells)
        elif not line.startswith('|'):
            table=False
        line=line.replace('; G2=', '; G2(full)=')
        line=line.replace('All parameters, budgets, recovery gates and stop rules follow the frozen plan.', 'Execution used the frozen numerical parameters and budgets. The acquisition scope of recovery and stopping is disclosed above.')
        line=line.replace('The archived 28/36 count is the combined historical retention contract, not a pure residual count. Archive recovery is 34/36.', 'CI-001 has 28/36 combined historical retention passes and 28/36 residual-only passes; its recovery count is 34/36.')
        out.append(line)
        if line=='## Attribution and stage distances':
            out += ['', 'Stage distances below use phase-aligned arclength correspondence RMS. The arm tables and endpoint figure use the frozen symmetric boundary-distance RMS recovery metric. These measure different quantities and should not be compared numerically as the same error.', '']
        if line=='## Disk scan':
            out += ['', '![Radius landscape]('+os.path.relpath(radius_plot,report.parent)+')', '']
        if line.startswith('Phase-1 validation:'):
            out += ['', 'An additional 11 shared CUDA compatibility tests passed after the campaigns, for 139 distinct pytest cases in total. Both injected CPU-fallback checks (forward and adjoint) also passed. See `validation_additional.json`.', '']
    report.write_text('\n'.join(out)+'\n')
print({arm:{k:v for k,v in value.items() if k!='rows'} for arm,value in contracts.items()})
