# Published CSI examples: stopped for the coordinator

17 November 2026. Activity 01 remains incomplete. Two attempts of step 1
ran; neither reached the end of all three methods. Steps 2 and 3 did not run.
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

No reconstruction arrays or figures were saved: the first wrapper saved only
after all three methods, and the second method failed. Thus there is no
honest visual judgement yet of the computed U shape. The wrapper now saves
completed methods' reconstruction arrays on a future failure. No rerun was
started after discovering the MR-CSI issue.

## Failures and the decision needed

`show_InitGuess.m` used `plottools('on')`, removed in R2026a. A display-only
fix comments out that command. It is the only applied upstream change:
[patch](../../../../external/patches/cc-csi/0001-r2026a-remove-obsolete-plottools.patch).
The original failed attempt was committed and pushed as `262ba5528`.

`functions/MR_CSI_Brent.m:217` then calls `interp2(vgTVq,-intrao)`, where
`intrao=1`. R2026a rejects negative refinement factors. The same call occurs
at lines 315 and 319 for the regularization line-search terms. Current
[MathWorks documentation](https://www.mathworks.com/help/matlab/ref/interp2.html)
requires a nonnegative refinement factor. I have not established the
historical behavior of the authors' MATLAB release.

Proposed change, **not applied**: replace those three negative-refinement
calls with sampling every `2^intrao` entries in each dimension, beginning at
index 1. Each array was made on the grid refined by `interp2(...,intrao)`,
so this selects the original grid nodes. This is a plausible intended
coarsening, but it lies inside MR-CSI's regularization and needs the
coordinator's decision under the no-algorithm-change rule.

Step 3 has no time estimate yet: step 2 has not run. Do not start it until
step 2 supplies per-iteration times and the total estimate is below four
hours, or the coordinator has obtained permission to exceed that limit.

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

Full forward and inverse timings, thread-isolated timings, calibration
values and computed image levels remain pending. No support threshold,
area score, contrast score or final-table claim is made here.
