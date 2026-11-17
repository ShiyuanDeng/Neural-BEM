# Rebuild the paper's single-component examples

## Status

Activity 02 was authorized by the coordinator on 17 November 2026. The
current target is all six saved k=15 endpoints, using concurrent paper cases
and at least 14 GB available memory. Keep all higher-frequency evidence;
k=30 resumes are low priority, only on an idle machine or coordinator request.
The later dated coordinator updates below supersede the original run order.

Activity 03 has reached its one-glider checkpoint and is stopped. Its report
contains the solver handover; further BEM work awaits the coordinator’s new
ownership arrangement. Shared comparison files remain unedited.

The first glider reached k=10 on 17 November: its RMS Figure 1 difference
is 0.904393 decades and its endpoint error ratio is 0.410220. Both exceed
the declared disagreement criterion. Finish its 117-frequency run, then
perform the single authorized no-limit alternative, reusing the same data.
The first candidate completed all 117 frequencies. Its terminal-launched
supervisor disappeared before its final receipt; completed outputs and
hashes were recovered, with a conservative wall-time budget debit. Later
runs use `--detach` so the supervisor and timeout survive terminal sessions.
The alternative gives bit-for-bit identical area errors at all 37 Figure 1
frequencies. Retain the shipped-driver values in this tie; neither option
reproduces Figure 1. This choice is frozen for all six cases. On 17 November the coordinator stopped the alternative after 48 saved
frequencies (k=12.75), because its question was answered. Keep that partial
record and do not resume it. Start glider eta=10 next; spend no further runs
on the paper gap. In results.md list at most three possible causes from
reading alone. The coordinator accepts the gap because the rebuilt BRG
errors are lower than the published curve and BRG is not handicapped.

## Coordinator decisions, 17 November

1. Six runs; seven was a legacy miscount. Order: glider 0.33, glider 10,
   star full, star limited, cavity 0.9, cavity 2.
2. Recover the star and cavity from vector true-curve paths in the obstacle
   panels of `limited_data_reconstruction.pdf` and `cavity_reconstruction.pdf`.
   Map figure coordinates using axis ticks and compare at least two panels.
   Fit the star's 35-mode Cartesian series and report fitting error. Label
   both shapes “recovered from the paper's figure files”, with measured
   accuracy. No pixel tracing or unapproved substitute. Stop if recovery
   cannot be done cleanly.
3. Use exterior-wavenumber resolution: 100 points per wavelength for data,
   70 for inversion. The corresponding interior counts are 100/sqrt(eta)
   and 70/sqrt(eta): for eta 10 about 31.62 and 22.14; for eta 2 about 70.71
   and 49.50. Once per eta>1 case, compare k=30 data against a finer grid.
4. Keep public frequency-start behavior: no extra inverse resampling.
5. Begin with `eps_curv=0.1`, `n_curv_min=20`, the shipped transmission
   driver's values. Compare glider 0.33 with Figure 1's vector error curve.
   If clearly different, allow exactly one rerun with the public default
   (no curvature limit). Retain both and freeze whichever matches better.
   This authorized comparison matches the paper; no further tuning/rerun.
6. Keep the public filter sequence and zero-gradient behavior, without guards.
7. A manufactured-solution diagnostic may use any verified interior point.
8. Use all 117 frequencies, k=1:0.25:30. Compare Figure 1 only through k=10.
9. Four hours per case, including data. The possible glider comparison shares
   that case's four-hour budget and reuses its saved data. Stop on a case
   limit, unrecoverable curve, or a crash needing more than a small patch.
10. Record other MATLAB processes at each case start/end; do not wait for an
    empty machine. Timings are indicative when another process overlaps.

## Settings and checks fixed before running

Use the pinned public source and approved patches 03/04. Equal density,
known contrast, unit-amplitude plane waves and scattered fields at radius
10. Full counts are floor(10k) directions and receivers; limited star uses
10 directions and 200 receivers. No noise, localization or extra starts.

`optim_type='min(gn,sd)'`, `maxit=50`, `eps_res=eps_upd=1e-5`, Gaussian
filter with the public ten-trial default. Shape-update band is
floor(3*max(k,k_inside)); length-scaled modes are disabled. The curvature
cutoff is the public max(20,update_band) for the shipped-limit candidate.
The default candidate omits `eps_curv` and `n_curv_min` entirely.

The initial unit disk follows the public RLA default: 100 nodes at k=1
with `opts.nppw=70`. Subsequent node growth is public behavior. True-data
sampling uses the public zero-update arclength resampling operation,
100 exterior points per wavelength and the data-script minimum of 300.
This resampling is for true-data generation, not an inverse frequency start.

At eta>1 and k=30, compare with twice as many boundary nodes for glider eta=10
and 25% more for cavity eta=2; record relative complex-field difference and
both grids. The coordinator required a finer grid, without fixing its ratio.
The cavity ratio was set before its run: recovered length 12.989 requires
6,202 data nodes at k=30, so doubling would require a 24,808-row complex
transmission system plus many dense auxiliary matrices and risks exceeding
the 62 GiB machine. The 25% check uses 7,754 nodes. This changes only the
accuracy diagnostic; no prescribed observation is replaced. Do not silently
change the case's prescribed data grid. Verify each diagnostic source by
point-in-polygon on the true boundary. All original field definitions,
transmission ratios and flattened receiver/direction order are retained.

For the authorized curvature comparison, extract the 37 Figure 1 points
at k=1:0.25:10. Compare relative area errors in log10 space, recording RMS,
median absolute difference, and endpoint ratio. Treat RMS above 0.30 decades
or endpoint disagreement above a factor of two as clear disagreement for
this predeclared comparison. If triggered, run the one allowed default
candidate and choose the smaller RMS log10 difference; report both scores.
No case is rerun because its shape recovery is poor.

## Cases

| Name | Shape | eta | Receivers / directions |
|---|---|---:|---|
| glider_033 | Exact paper glider | 0.33 | floor(10k) / floor(10k) |
| glider_10 | Exact paper glider | 10 | floor(10k) / floor(10k) |
| star_full | Recovered vector star, Cartesian band 35 | 0.9 | floor(10k) / floor(10k) |
| star_limited | Same recovered star | 0.9 | 200 / 10 |
| cavity_09 | Recovered vector cavity | 0.9 | floor(10k) / floor(10k) |
| cavity_2 | Same recovered cavity | 2 | floor(10k) / floor(10k) |

## Commands, outputs and budget

`python experiments/baselines/brg/run_paper.py --case glider_033 --curvature shipped --detach`
starts the first case. Later cases use the frozen curvature choice recorded
in `results/brg/paper_examples/2026-11-17/curvature_choice.json`. The only
permitted alternative is `--case glider_033 --curvature default --detach` if the
predeclared Figure 1 comparison clearly fails.

Each case shares a four-hour process-wall budget across attempts and the
allowed alternative. Save every data frequency and inverse endpoint
atomically; resume from the last completed curve. Keep one BRG MATLAB
process at a time. No extra process is started for source checks while a
case is active.

Raw outputs: `results/brg/paper_examples/2026-11-17/<case>/`; compact records
and figures at most about 5 MB per run. Bulk data, dense continuation states
and full logs remain in ignored `local/` with commands and SHA-256 values.
Figures go in this activity's `figures/`; extracted vector paths, calibration
and shape-fit evidence go in its owned results directory. Commit and push
code, docs and evidence after every case or failed attempt, by explicit
paths only. Preserve everything previously pushed.

Success means a reproducible outcome for every case, not recovery of every
shape. Record residual histories, iterations, exit flags, raw and normalized
area errors, all timings, and the source of every recovered true shape.
Stop only under the coordinator's listed conditions; otherwise complete
all six and report. No BEM inversion is run in this activity.

## True shape definitions and measured recovery accuracy

The glider is exact: `geometries.starn(coefs,8,n)` with coefficients
`[0.9,0,0,0.18,0.018,0,0.09,0,0.09,0,0,0,0,0,0,0,0]`, ordered constant,
eight cosines and eight sines. Multiply its radial series by cosine and sine
of the parameter; no rotation, translation or scaling.

The star and cavity are **recovered from the paper's figure files**. Their
executable definitions are the complex Cartesian coefficient arrays in
`results/brg/paper_examples/2026-11-17/shapes/star_fourier.mat` and
`cavity_fourier.mat`: sum `coefficients[j]*exp(i*modes[j]*t)` for a full
parameter turn; real and imaginary parts are x and y. Star modes are -35:35,
as required by equation 27; cavity modes are -100:100. The latter is a
representation chosen to reproduce the vector path, not a paper setting.

`recover_paper_vectors.py` selects the solid true-curve paths from both
obstacle-solver panels, verifies connected closed paths, and calibrates each
panel independently with its -pi/2, 0 and pi/2 axis ticks. It does not trace
pixels. In each panel all selected paths and ticks share the same affine
transform, which cancels when mapping their native coordinates. The legends
identify solid as the true boundary; dashed lines are reconstructions.

| Shape | Points in two vector panels | Cross-panel maximum / RMS | Cartesian fit point maximum / RMS | Fit to vector polyline maximum |
|---|---:|---:|---:|---:|
| Star | 923 / 921 | 1.060e-4 / 5.657e-5 | 5.105e-4 / 1.751e-4 | 5.594e-4 |
| Cavity | 995 / 997 | 9.154e-5 / 3.862e-5 | 4.625e-5 / 1.596e-5 | 1.424e-4 |

All errors are in figure data-coordinate units. Report conservative geometric
accuracy of about 6e-4 for the star and 2e-4 for the cavity, against the vector
centerline, not against unknown original coefficients. Both fits retain the
visible geometry and positive parameter orientation. The paper archive has
no original coefficient table. Path indices, tick calibration, source hashes,
vector samples and detailed errors are saved under `shapes/`; overlay figures
are in this activity's `figures/`. The shipped activity 01 cavity is different
and is not used as the paper cavity.

Command: `OPENBLAS_NUM_THREADS=1 python experiments/baselines/brg/recover_paper_vectors.py`.
Inputs are Cairo SVG exports of the original vector PDFs in the ignored
`results/brg/paper_sources/local/`; PDF hashes are in the recovery JSONs.

## Paper settings and public-code reach

Paper requirements below come from sections 2, 2.1 and 4; the reach column
comes from the pinned source. These are the activity 02 settings; they do not change activity 01.

| Requirement | Public option or wrapper operation | Reach / gap |
|---|---|---|
| k=1:0.25:30, 117 frequencies | `measurement.kh`, one-frequency RLA calls in order | Reachable; save and resume each frequency |
| Known, real material; equal density | `bc.q=sqrt(eta)`, `transa=transb=[1;1]` | Reachable with patches 03/04 |
| Unit-amplitude plane waves | `sensor_info.t_dir`, `compute_fields` | Reachable; preserve positive spatial phase |
| Radius-10 receivers, equally spaced full aperture | Explicit `tgt` and direction pairs | Reachable; floor counts, not the shipped ceiling |
| Limited star: 200 receivers, 10 directions | Same paired data API | Reachable; full aperture with sparse angles |
| Clean scattered field | `fields.uscat_tgt` | Reachable; no total-field or far-field-amplitude conversion |
| Data: 100 points per wavelength | Wrapper geometry sampling before `get_fw_mats` | Reachable; exterior convention and frozen recovered curves above |
| Inverse: 70 points per wavelength | `opts.nppw`; public starting behavior | Reachable, but see resolution ambiguity below |
| Alpert order 16 | Hard-coded `norder=16` in `get_fw_mats` | Already used |
| Dense direct solve | Public transmission path stores `inv(Fw_mat)` | Algorithmically direct; explicit inverse differs from paper's LU description; retain public code |
| Unit-disk start | Empty `src_init`; public unit-disk default | Reachable; 100 nodes initially, no localization or extra starts |
| floor(3*max(k,k_inside)) update band | Set `opts.ncoeff_boundary` per frequency; disable length scaling | Reachable; omit `ncoeff_boundary_mult` so it cannot overwrite the exact band |
| Better of GN and SD | `optim_opts.optim_type='min(gn,sd)'` | Reachable; ties choose SD in public code |
| Gaussian filtering, ten attempts | `filter_type='gauss-conv'`, `maxit_filter=10` | Available, but sequence differs from the printed formula; see below |
| Curvature-energy restriction | `optim_opts.n_curv`, `optim_opts.eps_curv` | Controls exist; paper's numerical tolerance and exact cutoff choice are missing |
| Residual and update stops 1e-5 | `eps_res=1e-5`, `eps_upd=1e-5` | Reachable; public update test uses coefficient-vector norm |
| At most 50 iterations per frequency | `optim_opts.maxit=50` | Reachable |
| Relative symmetric-difference area | Wrapper polygon areas divided by truth area | Reachable; also retain unnormalized area |

### Remaining differences from a fully specified paper experiment

1. The analytic star/cavity coefficients are absent. The coordinator chose
   vector recovery, whose finite accuracy is stated above. The count is six.
2. The paper's wavelength statements disagree. The coordinator chose the
   public exterior-k convention and required a finer-grid data check at
   k=30 for eta>1. Public frequency-start sampling is retained.
3. The paper omits the curvature tolerance/cutoff. Start with the public
   shipped-driver values and apply only the authorized Figure 1 comparison.
   The implementation compares square-root tail energy; 0.1 is used as the
   code's tolerance, with no reinterpretation as an energy fraction.
4. The printed Gaussian exponent divides by sigma squared; the code divides
   by sigma and includes the unfiltered trial in its ten-attempt limit. It
   filters each candidate before comparing them. Retain public behavior.
5. The public exact-fit zero-gradient SD division can cause NaNs and a MEX
   crash. No guard is authorized; record any recurrence.
6. The shipped analytic diagnostic source is outside its cavity. These runs
   use a point verified inside each actual true shape; it changes only the
   manufactured-solution check, never the plane-wave observations.
7. The star paragraph's unsquared-wavenumber notation is inconsistent.
   Interpret eta=0.9 as the squared ratio, consistently with section 4.1.
8. No paper drivers are public, so unspecified controls cannot be recovered
   from them. All choices above are the coordinator's declared choices.
9. Figure 1 displays k<=10, while section 4 states M=117. The coordinator
   chose all 117 frequencies and a comparison only on the plotted range.

## Parallel drafting work

Read `solvers/bem_inverse/README.md` and
`docs/reference/inverse_information_chain.md`, then draft
`../03_adapt_bem_to_brg_data/plan.md`. Use A1–C12 terms and list minimal file
changes for plane waves, unpaired data, fixed contrast, units and eta below
one. Specify per-shape forward checks before any inversion, a data-contained
frequency schedule and high-k risks. Do not edit `solvers/` or
`experiments/comparison/`; the coordinator reviews that plan first.

## Coordinator update: concurrent paper cases, 17 November 2026

Two paper cases may run together, each at eight MATLAB threads, with a
lock per case. CSI uses the third heavy-worker slot. Do not run a heavy
BEM check or fit while all three MATLAB slots are occupied. Start/end
overlap records remain required; clean timings will be measured later.

The six paper cases check BRG on its own examples. The main BRG table
will use the 20 TG-002 shape/contrast cases with BRG-style data, following
the user's new direction. Activity 04 will be planned after activity 03(c).

## Coordinator update: k=15 endpoints first, 17 November 2026

All six cases now stop at k=15 (57 frequencies). Keep every saved state
and all already-generated higher-frequency data. Resume to k=30 only when
the machine is otherwise idle or the coordinator requests it. The completed
glider eta 0.33 needs no rerun: report its saved k=15 endpoint.

Launch remaining cases concurrently with eight MATLAB threads each, watching
MemAvailable and retaining at least 14 GB. This replaces the three-worker
limit: the coordinator measured mostly single-threaded Fortran assembly.
Use `run_paper.py --case NAME --curvature shipped --max-k 15 --detach`.
Per-case locks and cumulative four-hour budgets remain. Activity 03 follows
with priority, and its ladder stops at k=15 or an earlier solver refusal.

The already-running eta 10 job is allowed to reach its saved k=15 state,
then an external wrapper watcher ends that pre-option MATLAB invocation.
The star data-generation invocation is redirected by restarting its wrapper
at k=15, reusing all existing data. No upstream solver change is required.
The cavity eta 2 k=30 finer-grid check waits for the later k=30 resume.
