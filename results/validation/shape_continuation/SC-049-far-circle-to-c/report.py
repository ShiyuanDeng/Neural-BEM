"""Saved-data-only report and figures for the one SC-049 attempt."""
from pathlib import Path
import json
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance

HERE=Path(__file__).resolve().parent
read=lambda name: json.loads((HERE/name).read_text())
result,config=read('result.json'),read('configuration.json')
initial_audit,final_audit=read('initial_audit.json'),read('final_audit.json')
initial_atlas,final_atlas=read('initial_atlas.json'),read('final_atlas.json')
checks=read('postrun_checks.json')
accepted=read('accepted.json')['states']
truth=ast.curve_from(sc.read(ast.source_folder('circle_to_c')/'truth.json'))
target_points=truth.values(16384)
started=time.perf_counter()
progress=[]
for row in accepted:
    curve=ast.curve_from(row['curve'])
    progress.append(dict(stage=row['stage'],iteration=row['iteration'],units=row['units'],loss=row['loss'],
        rms_mm=1000*symmetric_rms_distance(curve,target_points,sc.LENGTH),
        center_m=[float(curve.coefficients[curve.band].real*sc.LENGTH+sc.CENTER.real),
                  float(curve.coefficients[curve.band].imag*sc.LENGTH+sc.CENTER.imag)]))
sc.write(HERE/'evaluation_progress.json',dict(states=progress,seconds=time.perf_counter()-started,
    scope='Truth-based evaluation after the complete recorded trajectory; never used for fitting'))

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.facecolor':'white'})
fig=plt.figure(figsize=(12,6.2),layout='constrained')
grid=fig.add_gridspec(2,2,width_ratios=(1.4,1))
geometry=fig.add_subplot(grid[:,0])
loss=fig.add_subplot(grid[0,1])
error=fig.add_subplot(grid[1,1])
def line(axis,curve,**style):
    z=curve.values(4096)*sc.LENGTH+sc.CENTER
    z=np.r_[z,z[0]]*1000
    axis.plot(z.real,z.imag,**style)
initial=ast.curve_from(config['initial'])
final=ast.curve_from(result['curve'])
for row in accepted[1:-1]:
    line(geometry,ast.curve_from(row['curve']),color='#df9c69',alpha=.32,lw=.8)
line(geometry,initial,color='#717982',ls='--',lw=1.7,label='Initial circle')
line(geometry,truth,color='#142d40',lw=2.2,label='Target C')
line(geometry,final,color='#c44c2d',lw=2.2,label='Returned shape (failed)')
geometry.set(xlabel='x (mm)',ylabel='y (mm)',title='The shape stays near the wrong location')
geometry.set_aspect('equal',adjustable='box')
geometry.grid(alpha=.15)
geometry.legend(loc='upper right',frameon=False)
iterations=[r['iteration'] for r in progress]
loss.plot(iterations,[r['loss'] for r in progress],'-o',color='#246c85',ms=4)
stage=read('stage_1.json')
rejected=stage['acceptance_checks'][-1]
loss.plot([8],[stage['trials'][-1]['loss']],'x',color='#c44c2d',ms=8,mew=2)
loss.annotate('Next candidate rejected\nN/2N field mismatch',(8,stage['trials'][-1]['loss']),
              xytext=(3.4,1.7),arrowprops=dict(arrowstyle='->',color='#c44c2d'),fontsize=9,color='#963920')
loss.set(xlabel='Stage-1 iteration',ylabel='Normalized fitting loss',yscale='log',
         title='Data fit improves at the active 0.5 GHz')
loss.grid(alpha=.15)
error.plot(iterations,[r['rms_mm'] for r in progress],'-o',color='#c44c2d',ms=4)
error.set(xlabel='Stage-1 iteration',ylabel='Symmetric boundary RMS (mm)',
          title='Geometric error worsens (evaluation only)')
error.grid(alpha=.15)
fig.suptitle('Far circle → C: not recovered',fontsize=17,fontweight='bold')
fig.savefig(HERE/'reconstruction.png',dpi=180)
fig.savefig(HERE/'reconstruction.pdf')
plt.close(fig)

maps=[]
for label in ('initial','final'):
    with np.load(HERE/f'{label}_atlas.npz') as data:
        maps.append(np.log10(np.maximum(data['harmonic_sensitivity_per_m'].T,1e-4)))
fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
high=max(0,float(np.ceil(max(m.max() for m in maps))))
for ax,data,title in zip(axes,maps,('Initial circle · refinement PASS',
                                   'Returned shape · field refinement FAIL')):
    im=ax.imshow(data,origin='lower',aspect='auto',extent=(.1875,2.5625,-.5,48.5),
                 vmin=-4,vmax=high,cmap='viridis',interpolation='nearest')
    ax.set(xlabel='Frequency (GHz)',ylabel='Normal-harmonic order',title=title,
           xticks=(.25,.5,1,1.5,2,2.5),yticks=(0,8,16,24,32,40,48))
fig.colorbar(im,ax=axes,label='log10 sensitivity (1/m), display floor 10⁻⁴')
fig.suptitle('Initial and returned-state sensitivity atlases',fontsize=15,fontweight='bold')
fig.savefig(HERE/'atlases.png',dpi=180)
fig.savefig(HERE/'atlases.pdf')
plt.close(fig)

physical_units=result['total_units']+checks['work']['attempted']+checks['work']['jacobians']
relative=max(r['cpu_gpu_relative'] for r in checks['cpu_fields'])
summary=dict(status='COMPLETE / NOT RECOVERED',recovered=False,outcome=result['outcome'],
    fit_seconds=result['fit_seconds'],run_seconds=result['seconds'],
    postrun_control_seconds=checks['seconds'],total_physical_units=physical_units,
    initial_rms_mm=result['initial_score']['rms_mm'],final_rms_mm=result['score']['rms_mm'],
    cpu_gpu_max_relative=relative,source_integrity=True)
sc.write(HERE/'summary.json',summary)

(HERE/'README.md').write_text(f'''# SC-049: far circle to C

**COMPLETE / NOT RECOVERED.** One full reconstruction was attempted from the
user-requested distant circle. It stops in the first frequency stage with
`NUMERICAL_FAILURE`; later stages do not run. The result is retained without
restart, a more favorable initial position or relaxed tolerances.

![Initial, target, returned shape and progress](reconstruction.png)

## Fixed scene and outcome

The circle starts at (0.32, 0.62) m with radius 65 mm. Its sampled boundary
is {config['initial_sampled_boundary_gap_mm']:.2f} mm from the C boundary, and
their x extents have a {config['initial_x_separation_mm']:.2f}-mm gap, proving
initial nonoverlap. Target and all 19 noiseless observations are the original,
qualified SC-022 C. This is a new initialization stress test, not a new target
shape. The [contract](approved_plan.md) and [configuration](configuration.json)
freeze the full M3/5/7/9 prefix, M11/15/19 release and M25/31/37 fixed suffix.

| Quantity | Initial | Returned |
|---|---:|---:|
| Symmetric boundary RMS | {result['initial_score']['rms_mm']:.3f} mm | {result['score']['rms_mm']:.3f} mm |
| Sampled Hausdorff estimate | {result['initial_score']['hausdorff_mm']:.3f} mm | {result['score']['hausdorff_mm']:.3f} mm |
| Stage-1 loss, 0.5 GHz | {stage['initial_loss']:.6f} | {stage['final_loss']:.6f} |
| Full-catalog numerical audit | PASS | FAIL |

Seven updates are accepted with strictly decreasing loss at the active
frequency. The object shrinks/deforms near its incorrect starting position
while geometric error increases. The next candidate's N512/N1024 prediction
discrepancy is **{rejected['prediction_discrepancy'][0]:.3g}**, exceeding the
unchanged **1e-5** limit. It is rejected, and the original backend stops rather
than continuing outside its frozen numerical regime. The stop is neither a
timeout nor exhaustion of work. See [stage and trial evidence](stage_1.json).

All four declared recovery checks fail: RMS <=1 mm, sampled Hausdorff <=2 mm,
maximum catalog relative residual <=0.003, and endpoint numerical audit.
The returned maximum catalog relative residual is
{result['final_maximum_catalog_relative_residual']:.3f}. The endpoint is the
last accepted state, not the rejected candidate or a truth-selected iterate.

## Independent qualification and diagnostic controls

The initial full-catalog audit passes: fields agree to
{max(initial_audit['field_relative']):.2g}, full Jacobian columns to
{max(initial_audit['jacobian_relative']):.2g}, and the full-trial directional
finite difference to {initial_audit['full_trial_fd_relative']:.2g}.

At the returned endpoint, the complete derivative checks still pass
(worst column {max(final_audit['jacobian_relative']):.2g}, full-trial FD
{final_audit['full_trial_fd_relative']:.2g}), but field refinement fails at
the higher frequencies: the worst discrepancy is
{max(final_audit['field_relative']):.3g}, against 1e-7 above 0.5 GHz.
The accepted point still met its active 0.5-GHz field limit; the final audit
adds the entire catalog. This is retained as a failed audit.

After the stop, a bounded verification adds four CPU forward solves at 0.5
and 2.5 GHz, N512/1024, with the original dense geometry checker. CPU and CUDA
predictions agree within **{relative:.2g}** and the CPU reproduces both endpoint
refinement discrepancies. All 24 comparisons of dense/spatial intersection
counts on the eight saved states at N512/1024/2048 agree. These checks support
the recorded endpoint obstruction on both execution paths; they are not a
second full inverse or a speedup measurement. [Checks](postrun_checks.json),
[pre-dispatch scope and script hash](postrun_check_manifest.json).

## Atlas and runtime

![Initial and final sensitivity maps](atlases.png)

Initial and returned-state atlases use ideal normal harmonics P48, all 19
frequencies and N512/1024. Each costs 76 physical units. The initial atlas
qualifies. The returned atlas fails its field-refinement gate and is displayed
as exploratory evidence, not a qualified observability or recovery claim.
The color is a relative-data Jacobian column-pair norm per metre of normal
amplitude; the floor is a display choice. The atlas never chooses a fitting
step. Raw fields and Jacobians are saved in the two NPZ files.

| Work | Time | Physical units |
|---|---:|---:|
| Fitting, stopped in stage 1 | {result['fit_seconds']:.3f} s | {result['fit_work']['work_units']} |
| Initial independent audit | {initial_audit['seconds']:.3f} s | {initial_audit['work']['work_units']} |
| Final independent audit | {final_audit['seconds']:.3f} s | {final_audit['work']['work_units']} |
| Initial atlas | {initial_atlas['seconds']:.3f} s | {initial_atlas['units']} |
| Returned-state atlas | {final_atlas['seconds']:.3f} s | {final_atlas['units']} |
| Complete main run, including scoring/verification overhead | {result['seconds']:.3f} s | {result['total_units']} |
| Separate post-stop CPU/geometry checks | {checks['seconds']:.3f} s | {checks['work']['attempted']} |

The complete failed attempt takes **{result['seconds']:.2f} seconds**; this is
not a successful reconstruction time. Total charged work including post-stop
controls is **{physical_units} units**, below the 13824-unit ceiling. No timing
factor against an unaccelerated full reconstruction was measured.

Explicit CUDA, four frequency threads, one BLAS thread and SPD-014 geometry
acceleration ran on the RTX 5090. Source and input hashes match before/after;
the numerical [source archive](sources.tar.gz), [manifest](manifest.json),
[raw result](result.json) and [summary](summary.json) preserve provenance.
Historical observations and source bundles remain unchanged. No default,
optimizer policy, branch or worktree changed; no independent review is claimed.

## Interpretation and timing correction

The accelerated solver runs this attempt quickly, but the existing local
shape continuation does not localize the C from this distant initialization.
Its lower data loss does not imply better geometry. The numerical stop prevents
a conclusion about eventual convergence with another grid or policy; neither
was tried. A follow-up would have to distinguish global localization from
quadrature/finite-shape feasibility while keeping the failed case intact.

The earlier SPD-010–014 timing tables replay **SC-043 continuation suffixes
from saved intermediate shapes**, not complete reconstructions from the
original circles. Their 6485 s versus 281 s historical comparison must not be
presented as a full circle-to-target runtime or a guaranteed new-scene factor.
This SC-049 attempt starts from the actual circle and includes every executed
stage from that start.

Reproduce only in a separate evidence folder: `run.py prepare`, then
`run.py run`, using `PYTHONPATH=solvers:.`, `SC_FORWARD_BACKEND=cuda`,
`SC_FREQUENCY_THREADS=4` and all BLAS/OpenMP thread counts set to 1.
The runner refuses to overwrite a saved trajectory. `report.py` uses saved
data only and may regenerate these figures.
''')
print(summary)
