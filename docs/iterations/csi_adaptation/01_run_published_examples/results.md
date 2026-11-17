# Published CSI examples

17 November 2026. Activity 01 resumed with the coordinator's approval of the
legacy interpolation fix. The two initial failures below remain preserved.
No algorithm or data change was made. No threshold was selected.

## Runs and measurements

MATLAB R2026a, `maxNumCompThreads(8)` confirmed in both logs. BRG was allowed
to overlap, so these wall times must not enter the final comparison table.
Both attempts used the shipped `uTM_shaped` driver: 2:2:16 GHz, 36 sources,
1.5 mm spacing and 16 iterations per method, without changing its settings.
The built inversion grid was 94 by 94, not the 70 by 70 stated in the plan's
initial description: the driver's `xs=70` and `ys=70` are half-widths in mm,
rounded to the nearest cell by `Pre_InvFresnel_Conf`.

| Attempt (UTC) | Wall time | Outcome |
|---|---:|---|
| 19:23:22, original | 8.286 s | Input construction finished; removed GUI function `plottools` stopped the initial display |
| 19:24:37, display fix | 18.731 s | MF-CC-CSI completed 16 iterations; MR-CSI stopped before its first completed iteration |

Original evidence: [launch](../../../../results/csi/examples/2026-11-17_shipped_i/launch.json),
[log](../../../../results/csi/examples/2026-11-17_shipped_i/matlab.log),
[failure](../../../../results/csi/examples/2026-11-17_shipped_i/failure.txt).
Repeat evidence: [launch](../../../../results/csi/examples/2026-11-17_shipped_i_r2026a/launch.json),
[log](../../../../results/csi/examples/2026-11-17_shipped_i_r2026a/matlab.log),
[failure](../../../../results/csi/examples/2026-11-17_shipped_i_r2026a/failure.txt).
The repeat also retains a compressed snapshot of all upstream MATLAB sources.

MF-CC-CSI's printed `err` fell at every recorded iteration, from 2.6810 to
1.2202 (54.49% decrease). `FS` fell from 0.221 to 0.0812; `FD` from 0.166 to
0.108; `FC` from 0.434 to 0.172. The printed `ChiErr` compares against the
initial guess when no truth is supplied; it is not a recovery score.

In the initial two failures, no reconstruction arrays or figures were saved:
the first wrapper saved only
after all three methods, and the second method failed. Thus there is no
honest visual judgement yet of the computed U shape. The wrapper now saves
completed methods' reconstruction arrays on a future failure. No rerun was
started until the coordinator approved patch 0002.

## Step 1 completed after the compatibility fixes

17 November 2026, 19:30:22 UTC; 50.041 s total launch-to-exit wall time.
Eight MATLAB threads. The random-array refine/coarsen check returned true.
All three methods completed 16 iterations with finite raw contrast arrays;
each method's reported cost decreased at every recorded iteration.

| Method | Native seconds | Cost, first to last | Peak real contrast | Peak conductivity, mS/m |
|---|---:|---|---:|---:|
| MF-CC-CSI | 9.436 | 2.6810 to 1.2202 | 0.3690 | 130.74 |
| MF-MR-CSI | 9.621 | 2.6309 to 1.5710 | 0.1608 | 95.62 |
| CSI | 8.827 | 0.35441 to 0.041413 | 0.6852 | 320.89 |

Peaks use raw `chi` at the last frequency, 16 GHz. Costs have different
definitions across methods and must not be ranked against one another.
In the [native output](figures/shipped_i_figure_02.png), MF-CC-CSI and
MF-MR-CSI show the metal U's two arms and joining bar, with a stronger
conductivity image. CSI gives a rounded central blob at 16 iterations.
Thus successful execution and falling costs do not imply that every method
recovers the U in this short shipped test. No threshold or shape score.

Evidence: [launch](../../../../results/csi/examples/2026-11-17_shipped_i_legacy_interp2/launch.json),
[analysis](../../../../results/csi/examples/2026-11-17_shipped_i_legacy_interp2/analysis.json),
[raw contrast](../../../../results/csi/examples/2026-11-17_shipped_i_legacy_interp2/reconstruction.mat),
[cost history](../../../../results/csi/examples/2026-11-17_shipped_i_legacy_interp2/cost_history.csv).
All open figures and per-frequency initial/final fields are saved. This
run also saved dense forward operators, with every file below 50 MB.
Later runs omit deterministic dense operators to avoid needless large
files; they retain measured/incident data, all raw contrast outputs,
initial/final fields and exact upstream MATLAB sources.

## Failures and MATLAB compatibility fixes

`show_InitGuess.m` used `plottools('on')`, removed in R2026a. A display-only
fix comments out that command:
[patch](../../../../external/patches/cc-csi/0001-r2026a-remove-obsolete-plottools.patch).
The original failed attempt was committed and pushed as `262ba5528`.

`functions/MR_CSI_Brent.m:217` then calls `interp2(vgTVq,-intrao)`, where
`intrao=1`. R2026a rejects negative refinement factors. The same call occurs
at lines 315 and 319 for the regularization line-search terms. Current
[MathWorks documentation](https://www.mathworks.com/help/matlab/ref/interp2.html)
requires a nonnegative refinement factor. I have not established the
historical behavior independently of the coordinator's source reading below.

The coordinator approved and I applied
[patch 0002](../../../../external/patches/cc-csi/0002-restore-legacy-interp2-coarsening.patch),
replacing only those three calls with sampling every `2^intrao` entries in
each dimension from index 1. **Coordinator's reading of the legacy function:**
`interp2(V,n)` built query coordinates `1:1/2^n:ncols` (and the same for
rows), without checking the sign. For `n=-1`, it queried `1:2:end`; linear
interpolation at the existing nodes returns their exact values. Refinement
at line 209 changes N to 2N-1, and this sampling restores N entries, as the
later arithmetic requires. This restores legacy behavior rather than
changing the regularization mathematics. Further compatibility fixes may
proceed when the old behavior is clear, as authorized by the coordinator.

The wrapper checks a seeded random 17-by-17 array V, sets `Vq=interp2(V,1)`,
and asserts `isequal(V,Vq(1:2:end,1:2:end))`. It restores the random-number
state before executing their driver. The check result is recorded in each
resumed run's MATLAB log.

## Step 2 completed and step 3 budget

17 November 2026, 19:33:04 UTC; 190.376 s total wall time. Eight threads,
134-by-134 grid, 1.5 mm spacing, 8 sources, 2:2:10 GHz, 32 iterations.
The refine/coarsen equality check passed. All three methods completed with
finite contrast arrays, and costs decreased at every recorded iteration.

| Method | Native seconds | Seconds/iteration | Cost, first to last | Peak real contrast | Peak conductivity, mS/m |
|---|---:|---:|---|---:|---:|
| MF-CC-CSI | 67.703 | 2.115727 | 3.5697 to 0.86534 | 0.8860 | 5.528 |
| MF-MR-CSI | 53.386 | 1.668301 | 4.0190 to 1.0281 | 0.6997 | 7.167 |
| CSI | 52.614 | 1.644203 | 0.77925 to 0.26174 | 0.4310 | 2.887 |

Peaks are from raw `chi` at 10 GHz. In the
[native output](figures/shipped_ii_figure_02.png), MF-CC-CSI shows a compact
high-contrast cylinder above a broader low-contrast foam region. MR-CSI
splits the upper feature into two lobes and adds diagonal streaks. CSI
smooths the two regions together. Conductivity artifacts sit near the top
border. This is a useful execution check, not a quantitative recovery claim.

Evidence: [launch](../../../../results/csi/examples/2026-11-17_shipped_ii/launch.json),
[analysis](../../../../results/csi/examples/2026-11-17_shipped_ii/analysis.json),
[raw contrast](../../../../results/csi/examples/2026-11-17_shipped_ii/reconstruction.mat),
[cost history](../../../../results/csi/examples/2026-11-17_shipped_ii/cost_history.csv).

**Estimate recorded before step 3:** multiplying each of the two required
methods' native step-2 times by 2048/32 gives 7749.688 s in total, or
2 h 09 min 10 s. Adding 20% and 120 s for setup/export gives 9419.626 s,
or 2 h 36 min 59 s, below the four-hour limit. This uses the observed TE
rates directly, with no discount for the smaller TM grid or fewer
frequencies; the source count changes from 8 to 18, so it remains an
estimate, not a bound. The launcher enforces a four-hour total wall limit.
Step 3 may now start with the authorized paper frequencies, domain and
2048 iterations for MF-CC-CSI and MF-MR-CSI only.

The analyzer exports per-source/frequency factors to `source_calibration.csv`
for both completed steps, using the exact midpoint receiver and line-source
formulas from `ReadFreData`. For step 1 at 2 GHz, all 36 calibrated incident
fields at the first grid point match the saved MATLAB fields to relative
error 5.47e-15; [check](../../../../results/csi/examples/2026-11-17_shipped_i_legacy_interp2/calibration_check.json).
No calibration is fitted to scattered fields.

## Figure 5 checked against the paper

The [paper PDF](https://arxiv.org/pdf/1906.10814), page 11, Figure 5 was
downloaded to temporary storage and rendered with Poppler after the web
screenshot failed. The measured-data rows show two distinct hot spots with
MF-CC-CSI, around horizontal position zero and vertical positions -60 and
-5 mm, with peak contrast a little above 2. The broad lower foam region is
also visible. MR-CSI instead has a small speckled feature near the upper
cylinder and a much larger peak, about 35. Comparison with computed images
is pending. The reference is available; lack of an image is not the blocker.

The case geometry is one small cylinder embedded in foam and another beside
it. The plan's original phrase "two cylinders inside" is inaccurate. The
figure's permittivity panels have a zero background and display contrast;
do not add a background of one when comparing the plotted color levels.

## What the later BEM adapter needs

These are source and input-file observations, not a solver change. See
`functions/ReadFreData.m`, `functions/Pre_InvFresnel_Conf.m`, both drivers,
`show_InitGuess.m`, and `show_output.m` in the saved upstream snapshot.
The [data layout](../../../../results/csi/examples/data_layout.json) records
counts from the actual upstream input tables, including `dielTM_dec8f`.

- Raw columns: source index, receiver index/angle, frequency in GHz, real
  and imaginary total field, real and imaginary incident field. The code
  subtracts incident from total before reshaping each frequency. Original
  row order matters: receivers are contiguous within each source.
- `dielTM_dec8f` has 8 frequencies, 1 through 8 GHz. Each frequency contains
  49 measured receivers for each of 36 sources: 1764 complex data. The full
  receiver ring has 72 positions. `uTM_shaped` has the same table shape.
- For these first-opus inputs, the driver changes source index to
  `10*(index-1)-2.5` degrees and receiver index to `5*(index-1)` degrees.
  Source radius is 0.72 m and receiver radius 0.76 m.
- The second-opus examples have 241 receiver measurements per source on
  a 360-position ring. The twin case has 18 sources, and the shipped TE case
  has 8. Their source angles are `360/NTX*(index-1)+0.5` degrees; receiver
  entries are already angles. Keep the measured table rather than filling
  an aperture from an assumed continuous angular interval.
- `Emea` is the full receiver-union by source table, with absent entries
  zero-filled. `pars.Rindex` maps measured rows, and `pars.rmea` holds
  MATLAB column-major linear indices. These indices, not field values of
  zero, define the data mask. TE expands each receiver to two interleaved
  Cartesian components using its tangential direction.
- Calibration is complex, per source and frequency. `calind=floor(NRX/2)+1`
  picks one receiver in each source's measured ordering. The code divides
  that measured incident value by its analytic line-source field at the
  same receiver, then multiplies the whole incident field by this factor.
  TE uses the tangential analytic field; TM uses the scalar field. The
  factors are local to `ReadFreData`; a later adapter must compute or export
  them with the same branch and normalization, never fit them to scattering.
- Their normalized frequency uses the MaxwellFDFD length unit (1.5 mm here).
  `ReadFreData` divides `Phi` once and the stiffness matrix twice by that
  normalized frequency. The driver multiplies `Phi` back once before the
  methods are called; back-propagated `vJ` is divided once. Keep measured
  field scaling and source calibration together when checking our forward.
- Their convention is positive time sign, with Hankel functions evaluated
  at negative real arguments, and nonpositive imaginary contrast. Our
  negative-time convention requires conjugating exchanged complex fields
  and contrast consistently. Conductivity in the display is minus imaginary
  contrast times physical angular frequency and vacuum permittivity, then
  multiplied by 1000 for mS/m. Real contrast is shared across frequencies;
  imaginary contrast scales inversely with frequency.
- The inversion grid has x as its first matrix dimension and y as its
  second. `myshow2D` sends matrices to `imagesc` without a transpose and uses
  confusingly named `xinv`/`yinv`; preserve numerical coordinates separately
  and check orientation before comparing an asymmetric truth.
- The outer five cells are fixed at zero. `pars.rchiTV` marks an even wider
  border for the TV terms. `show_output` also sets that wider border to zero
  in the final stored `mchi` image. The `chi1/2/3` arrays retain the solver
  values; score or recount from these raw arrays, not a display-masked PNG.
- The shipped second-opus radius includes a correction: it is
  `1.67 + (0.20066/0.6964)/2`, about 1.81407 m. The paper text says 1.67 m.
  Keep this difference visible for the coordinator; do not silently switch
  either the baseline or our matched forward check to another radius.

The radius mismatch is: the shipped second-opus code uses 1.81406950 m for both antennas.
The paper says 1.67 m; this activity keeps their shipped correction unchanged.

Full forward and inverse timings, thread-isolated timings, calibration
values and computed image levels remain pending. No support threshold,
area score, contrast score or final-table claim is made here.
