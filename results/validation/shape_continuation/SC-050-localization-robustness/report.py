"""Post-run reporting only; no optimization or policy selection."""
from pathlib import Path
import importlib.util
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sc050_report_common',HERE/'run.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
read=lambda p:json.loads(Path(p).read_text())
selection=read(HERE/'selection.json')
arm=selection['arm']
development=[read(HERE/'runs/development_c'/a/'result.json') for a in m.ARMS]
transfer=[read(HERE/'runs'/s/a/'result.json') for s in m.TRANSFER for a in ('baseline',arm)]
allrows=development+transfer
m.verify()

# Fresh fixtures remain listed even if input qualification or fitting failed.
fixture_rows=[]
for scene in m.SCENES:
    truth=m.ast.curve_from(read(HERE/'inputs'/scene/'truth.json'))
    initial=m.ast.curve_from(read(HERE/'inputs'/scene/'initial.json'))
    a,b=[x.values(8192)*m.sc.LENGTH+m.sc.CENTER for x in (initial,truth)]
    gap=np.min(cKDTree(np.c_[b.real,b.imag]).query(np.c_[a.real,a.imag])[0])
    direction=(np.mean(b)-np.mean(a))/abs(np.mean(b)-np.mean(a))
    axis_gap=float(np.min((b*np.conj(direction)).real)-np.max((a*np.conj(direction)).real))
    fixture_rows.append(dict(scene=scene,initial_boundary_gap_mm=float(1000*gap),initial_separating_axis_gap_mm=1000*axis_gap,
        input_qualified=read(HERE/'inputs'/scene/'qualification.json')['passed']))

# Check that the new baseline reproduces the historical full attempt exactly.
prior=read(HERE.parent/'SC-049-far-circle-to-c/accepted.json')['states']
current=read(HERE/'runs/development_c/baseline/accepted.json')['states']
keys=('stage','iteration','M','loss','units','curve')
replay= len(prior)==len(current) and all(all(a[k]==b[k] for k in keys) for a,b in zip(prior,current))

def brief(r):
    return {k:r[k] for k in ('scene','arm','outcome','recovered','noisy','metrics','final_audit_passed',
        'maximum_residual','fit_and_localization_units','total_units','fit_and_localization_seconds','seconds') if k in r}
summary=dict(selected_policy=selection,baseline_exact_accepted_replay=replay,fixtures=fixture_rows,
    development=[brief(r) for r in development],transfer=[brief(r) for r in transfer],
    transfer_success={a:sum(r['recovered'] for r in transfer if r['arm']==a) for a in ('baseline',arm)},
    total_recorded_units=234+sum(r.get('total_units',0) for r in allrows)+sum(read(p)['units'] for p in (HERE/'inputs').glob('*/qualification.json')),
    total_attempt_seconds=sum(r['seconds'] for r in allrows),
    scope='One attempt per arm and fixture; clean and one-noise-draw transfer are separate; no population success-rate or general speedup claim.')
m.write(HERE/'summary.json',summary)

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors=dict(truth='#17364b',initial='#92979d',baseline='#c65335',selected='#20866c')
def line(ax,curve,**kw):
    z=curve.values(4096)*m.sc.LENGTH+m.sc.CENTER
    z=np.r_[z,z[0]]*1000
    ax.plot(z.real,z.imag,**kw)
def curve(r):
    return m.ast.curve_from(r.get('final_curve',r.get('last_curve')))
def decorate(ax):
    ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.15);ax.set(xlabel='x (mm)',ylabel='y (mm)')

fig,axes=plt.subplots(2,3,figsize=(14,9.4),layout='constrained')
truth=m.ast.curve_from(read(HERE/'inputs/development_c/truth.json'))
initial=m.ast.curve_from(read(HERE/'inputs/development_c/initial.json'))
for ax,r in zip(axes.flat,development):
    line(ax,initial,color=colors['initial'],ls='--',label='Start')
    line(ax,truth,color=colors['truth'],lw=2,label='Target')
    line(ax,curve(r),color=colors['selected'] if r['recovered'] else colors['baseline'],lw=1.8,label='Returned')
    metric=r.get('metrics',{}).get('rms_mm',np.nan)
    ax.set_title(f"{r['arm']} · {'PASS' if r['recovered'] else 'FAIL'}\nRMS {metric:.3g} mm; {r.get('fit_and_localization_seconds',np.nan):.1f} s fit+loc")
    decorate(ax)
axes.flat[0].legend(frameon=False,fontsize=9)
fig.suptitle('Original far circle → C: six prespecified strategies',fontsize=17)
fig.savefig(HERE/'development.png',dpi=170);fig.savefig(HERE/'development.pdf');plt.close(fig)

fig,axes=plt.subplots(2,3,figsize=(14,9.4),layout='constrained')
for ax,scene in zip(axes.flat,m.TRANSFER):
    target=m.ast.curve_from(read(HERE/'inputs'/scene/'truth.json'))
    initial=m.ast.curve_from(read(HERE/'inputs'/scene/'initial.json'))
    base,selected=[r for r in transfer if r['scene']==scene]
    line(ax,initial,color=colors['initial'],ls='--',lw=1,label='Start')
    line(ax,target,color=colors['truth'],lw=2,label='Target')
    line(ax,curve(base),color=colors['baseline'],lw=1.4,label='Baseline')
    line(ax,curve(selected),color=colors['selected'],lw=1.5,label=arm)
    ax.set_title(f"{scene.replace('_',' ')}\nBaseline / selected RMS: {base.get('metrics',{}).get('rms_mm',np.nan):.3g} / {selected.get('metrics',{}).get('rms_mm',np.nan):.3g} mm")
    decorate(ax)
axes.flat[0].legend(frameon=False,fontsize=9)
fig.suptitle(f'Frozen policy transfer: {arm} · all six added scenes',fontsize=17)
fig.savefig(HERE/'transfer.png',dpi=170);fig.savefig(HERE/'transfer.pdf');plt.close(fig)

locpath=HERE/'runs/development_c/localize/localization.json'
if locpath.exists():
    loc=read(locpath);grid=[r for r in loc['rows'] if r['nodes']==[128,256]]
    landscape=np.array([r['loss'] if r['qualified'] else np.inf for r in grid]).reshape(9,9,3).min(axis=2).T
    landscape[~np.isfinite(landscape)]=np.nan
    fig,ax=plt.subplots(figsize=(7,5.8),layout='constrained')
    im=ax.imshow(np.log10(np.maximum(landscape,1e-12)),origin='lower',extent=(252.5,747.5,252.5,747.5),cmap='viridis')
    ax.scatter([320],[620],marker='x',color='white',s=100,label='Original center')
    best=loc['parameters_m'];ax.scatter([best[0]*1000],[best[1]*1000],marker='*',color='#ffcd4b',s=180,label='Data-selected circle')
    z=truth.values(4096)*m.sc.LENGTH+m.sc.CENTER;ax.plot(z.real*1000,z.imag*1000,color='#ffcd4b',lw=1,label='Target (evaluation only)')
    ax.set(xlabel='Candidate center x (mm)',ylabel='Candidate center y (mm)',title='Low-frequency circle-search loss\nMinimum over three trial radii at each center')
    ax.text(.02,.02,'White: no qualified circle at these radii',transform=ax.transAxes,fontsize=8,color='white',bbox=dict(facecolor='#17364b',alpha=.8,pad=3))
    ax.legend(fontsize=9);fig.colorbar(im,ax=ax,label='log10 normalized loss')
    fig.savefig(HERE/'localization.png',dpi=170);fig.savefig(HERE/'localization.pdf');plt.close(fig)

def table(rows):
    lines=['| Scene / arm | RMS mm | Hausdorff upper mm | Max residual | Audit | Recovery | Fit+loc units | Fit+loc s |','|---|---:|---:|---:|---|---|---:|---:|']
    for r in rows:
        d=r.get('metrics',{})
        lines.append(f"| {r['scene']} / {r['arm']} | {d.get('rms_mm',np.nan):.4g} | {d.get('hausdorff_upper_mm',np.nan):.4g} | {r.get('maximum_residual',np.nan):.4g} | {'PASS' if r.get('final_audit_passed') else 'FAIL'} | {'PASS' if r['recovered'] else 'FAIL'} | {r.get('fit_and_localization_units','—')} | {r.get('fit_and_localization_seconds',np.nan):.2f} |")
    return '\n'.join(lines)
selected_development=next(r for r in development if r['arm']==arm)
text=f'''# SC-050: far-start strategies and six-scene transfer

Completed 2026-09-28 under the [frozen plan](plan.md) and documented
[search-domain amendment](amendment_01.md) and [initial-domain correction](amendment_02.md). Sources and inputs verify;
SC-049 accepted baseline trajectory replay: **{'exact' if replay else 'NOT exact'}**.
Claude's SPD-014 [review amendment](../../speedup/SPD-014-amendment-20260928/README.md)
preceded this campaign. No solver or optimizer default changed.

**Result:** localization before shape fitting recovered the original failed C.
The selected policy reduced RMS error from {development[0]['metrics']['rms_mm']:.2f}
to {selected_development['metrics']['rms_mm']:.5f} mm in
{selected_development['fit_and_localization_seconds']:.2f} s of localization plus
fitting ({selected_development['seconds']:.2f} s including independent audits and
post-fit scoring; process startup and provenance hashing excluded).
Both localization arms succeeded; lower frequency alone, smaller steps alone,
and doubled quadrature alone failed. The selected policy then recovered all
five clean transfer cases and the one fixed noise case; every transfer baseline
failed. This supports the localization-first strategy within this synthetic panel.

## Development ablation

{table(development)}

![All development endpoints](development.png)

The data-only rule selected **{arm}** before any transfer fit. It ranks completed,
audited schedules first, then audited endpoints, then remaining endpoints, using
maximum catalog residual and charged work; truth error is excluded. Selection
record: [selection.json](selection.json). Every attempt uses the same 13412-unit
fit+localization cap. Actual work differs because of stopping and stage quotas.
Reported fit+localization time excludes independent audits and post-fit scoring;
result.json retains total times and diagnostic work. Refined uses larger systems,
so equal work units are not equal wall cost.

## Transfer without retuning

Selected policy: {summary['transfer_success'][arm]}/6 total recovery successes;
baseline: {summary['transfer_success']['baseline']}/6. This includes one prespecified
1% noise draw, reported separately below; it is a small deterministic panel,
not an estimated probability of success on unseen scenes.

{table(transfer)}

![All transfer endpoints](transfer.png)

Clean recovery requires RMS<=1 mm, Hausdorff upper bound<=2 mm, max catalog
relative residual<=0.003, and independent field/Jacobian/FD audit. The noisy
case uses the same geometry/audit thresholds and a per-frequency residual ceiling
of max(0.003, 3 times realized noise). It does not establish broad noise robustness.
Five infeasible requested starts were corrected before any transfer fit by one
acquisition-only radial-contraction rule; original input files are retained.
The targets and observations did not change. See [initial_domain_amendment.json](initial_domain_amendment.json).
Every endpoint is the last accepted state. Numerical or quota stops remain in
`runs/*/*/result.json` and complete stage histories.

## Evidence for the strategies and limits

At the displaced initial circle, the saved qualified atlas predicts shrinkage
and translation away from the target in both the 0.25 and 0.5 GHz local linear
models. The radius/translation subspace projects 75.9% versus 4.83% of the squared
residual at those frequencies. These are local, unconstrained derivatives; the
large predicted 0.25 GHz radius reduction is not a valid finite-step prediction.
The local M3 Jacobian has condition number about 2.8 at 0.5 GHz, yet its
least-squares direction points away from the target. A well-conditioned local
linear solve can therefore reduce data loss while worsening distant-shape error.
See [atlas_diagnosis.json](atlas_diagnosis.json). Sensitivity magnitude alone does
not certify correct localization or global identifiability.

![Circle localization landscape](localization.png)

Localization evaluates the nonlinear full-wave objective over center/radius,
then permits flexible shape changes. It uses measured data only. Every usable grid and
refinement candidate passes a paired-resolution check. Known source/receiver
intersections and unqualified candidates are recorded and excluded. The finite grid and bounded
circle family do not establish global optimality. Its cost is included in each
localization arm, with no cross-arm reuse of the search receipt.

The scientific basis and acquisition/physics differences are documented in the
[plan](plan.md): [Bao–Hou–Li (2007)](https://doi.org/10.1016/j.jcp.2007.08.020)
support localization before continuation; [Borges–Rachh–Greengard (2022)](https://arxiv.org/html/2210.11607v1#S2.SS1)
explain low-frequency continuation and increasing shape complexity for penetrable
objects; [Borges–Greengard (2014)](https://arxiv.org/html/1408.5436v1#S3)
discuss damping and initialization in obstacle reconstruction. None guarantees
this paired near-field implementation will recover arbitrary cavities.

Four fresh clean observation sets passed 1024/2048 refinement and independent
Kress checks at three frequencies; original-C observations retain their oracle
receipt. One fixed noise draw reuses the fresh asymmetric target. Shared model
assumptions, fixed contrast, one connected component, known inspection box,
finite scene count and single noise draw limit generalization. All target definitions and observations, including the opposite-side C and noisy
scene, were fixed before development. The disclosed acquisition-only initial
position correction occurred after development and before all transfer fitting.

Provenance: [manifest](manifest.json), [source archive](sources.tar.gz),
[summary](summary.json), [driver](run.py). Total recorded physical work including
input generation and audits: {summary['total_recorded_units']} units. All
{len(allrows)} intended comparisons and two pre-ranking setup failures are retained.
The setup failures cost an additional conservatively counted 234 units, included
in the total. Four unaffected development controls were reused after the domain
amendment; the source chain records their hashes. This is a reconstruction-strategy
study; it does not measure a new general execution-speedup factor.
'''
(HERE/'README.md').write_text(text)
print(json.dumps({k:summary[k] for k in ('baseline_exact_accepted_replay','transfer_success','total_recorded_units')},indent=2))
