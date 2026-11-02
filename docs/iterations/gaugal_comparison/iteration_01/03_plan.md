# GauGal comparison, iteration 1: material recovery, forward check, GauGal on TG-002

Prepared 2026-11-01 from a design discussion with the user. Not yet run.
Experiment IDs: **MR-001** (BEM material recovery), **FW-001** (forward check,
MoM as the classic baseline), **GGB-002** (GauGal on TG-002). GGB-001 is the
earlier three-cylinder comparison kept in `~/Gau-Gal/docs/iterations/GGB-001/`.

## Questions

1. **MR-001.** Can the BEM fit recover the object's contrast together with its
   boundary on TG-002, starting from a contrast that does not use the truth?
2. **FW-001.** On TG-002 shapes, how accurate and how costly are MoM, GauGal's
   forward operator and the BEM forward solve, measured against the sealed
   reference fields? Which GauGal lattice is accurate enough to use?
3. **GGB-002.** On the same TG-002 data, how do GauGal and the BEM fit compare
   in boundary accuracy, image scores, field fit and time?

The report is a fair, two-sided note for Haibing that could later become a
comparison section of a paper. It states what information each method used.

## User decisions (2026-11-01)

- Report reader: Haibing; fair and two-sided. MoM is the forward baseline, not
  a third inverse method.
- Work and results live in this `organised` worktree. GauGal is imported
  read-only from `~/Gau-Gal`; nothing more is pushed to its repository.
- Scenes: TG-002 only for now. The 31 single-disk SingleTX cylinders are not run
  ("if the 31 scenes are just cylinders with different positions i think not
  now, we should stick with tg002 for now"). AU, Fresnel and MNIST are out of
  reach of a single-curve BEM fit; the report quotes GauGal's published numbers.
- Material recovery on TG-002 first, with GauGal run alongside ("if you can run
  them in parallel you could totally just run them together"). MR-001 has no
  pass mark that holds back GGB-002; if it fails, it is fixed until it works.
- Noiseless data for now ("noiseless for now"). Noise is decided later.
- GauGal uses one loss summed over all frequencies (option b), may take
  negative χ, and is tuned once on the three `circle` cases, then frozen.
- Terms follow `GLOSSARY.md`: contrast is ε_r against the background;
  susceptibility χ = ε_r − 1 is what GauGal and MoM call contrast.

## Shared data

TG-002 sealed inputs, unchanged: 10 scenes × contrasts 0.5/4/13.3, 24
source–receiver pairs on a 0.30 m ring (one receiver 0.06 m along the ring from
each source), 19 real frequencies 0.25–2.5 GHz and their damped copies, sand
background ε = 6, noiseless. Interior wavelength at 2.5 GHz: about 69, 25 and
13 mm at contrasts 0.5, 4 and 13.3.

## MR-001: BEM material recovery

**Code.** An optional contrast unknown in `solvers/bem_inverse/`, off by
default so known-contrast fits stay unchanged. The unknown is the log of the
contrast. Its Jacobian column comes from one extra matrix assembly per frequency
per iteration, reusing the existing factorization. It is active in every stage,
including the damped warm-up.

**Start.** Solve the centred 65 mm start circle once at a tiny contrast at the
lowest damped frequency, then scale that response to best fit the data. This is
one solve and one least-squares number, not a search. The estimate is recorded
before fitting.

**Runs.**

| Run | Cases | What | Expected |
|---|---|---|---|
| R1 control | all 30 | Known-contrast fit, current default (`modal_muller` + `spectral`) | About 26/30 recovered, as in PC-001 M1 (which used `certified_spectral`); aphex ×3 and hook 13.3 fail. About 17 min summed. |
| R2 material recovery | all 30 | Same fit plus the contrast unknown, weak-scatterer start | See below |
| R3 near-truth start | R2 failures only | Start at true contrast × 1.2 | Tells a bad start apart from a fit that cannot recover material |

**Expectations for R2.**
- The start estimate should land on the correct side of 1 in every case. Its
  size will be biased by the area mismatch between the start circle and the
  target. At contrast 13.3 the object already resonates at 0.25 GHz (interior
  size about 2.3 radians), so that estimate may be far off.
- Contrast 0.5 and 4: likely to recover the same cases as R1.
- Contrast 13.3: the main risk. Contrast and size can trade against each other,
  and resonances make the loss along the contrast direction bumpy.
- Time: likely 1.2–2× R1 per case, from the extra assembly and any extra
  iterations.

**Analysis.** Per case: recovered under the unchanged TG-002 limits, RMS,
Hausdorff upper bound, final contrast error, time against R1. Start estimate
against truth. The contrast path through the stages: when it settles, and
whether its error follows the area error.

**Checks before R2.** With the option off, `circle__c0.5` reproduces its R1
result. One finite-difference check of the new Jacobian column.

## FW-001: forward check (MoM baseline)

Rasterise each true shape and solve the forward problem with MoM (2D-MOM-ESI) and with GauGal's operator. Compare both with the sealed reference fields at all 19 real frequencies. The sand background is handled by rescaling frequency so the background wavenumber matches.

| Run | What | Expected |
|---|---|---|
| F1 MoM | Cell sizes 4, 2 and 1 mm, 30 cases × 19 frequencies | Error falls roughly in step with cell size; worst at contrast 13.3 and 2.5 GHz. Cost grows with the cube of the cell count; 1 mm is the largest dense size. |
| F2 GauGal operator | Two or three lattice spacings | Similar trend. The default 56 lattice (about 3.6 mm over a 0.2 m box, about 3–4 points per interior wavelength at 13.3) should be clearly too coarse at the top frequency. |
| F3 BEM | Reuse recorded TG-002 qualification and endpoint numbers | No new runs; the BEM solve is near round-off against the reference. |

**Analysis.** Error against unknowns and against time for the three forward
solvers, per contrast. GauGal's lattice: the smallest with at most 1% forward
error at every frequency it uses. If none fits the GPU, the top frequencies are
dropped for GauGal and the report says so.

## GGB-002: GauGal on TG-002

**Code** (in this worktree, GauGal untouched apart from the χ lower limit):
- A TG-002 data builder: positions, the 24-pair mask (`receiver_mask`), the
  background rescaling, and a field-scale check on `circle` against the
  sealed data.
- A multi-frequency loop (about 100–150 lines): it copies GauGal's update loop
  and sums the gradient over the 19 real frequencies, each frequency keeping its
  own field warm starts. Each frequency is weighted by its data energy, so every
  frequency's relative misfit counts equally, as in TG-002's residual limit.
- The χ lower limit moves from 0 to −0.9 at its three clip points.
- GauGal gets no damped data; BEM's damped warm-up is reported as extra
  information BEM used.

**Runs.**

| Run | What | Expected |
|---|---|---|
| G1 tuning | At most 12 settings (smoothing weight, step size, Gaussian width; one common χ upper limit) on `circle__c0.5/c4/c13.3`, one shared setting chosen by mean image RRMSE | A usable setting for 0.5 and 4; 13.3 may have none. |
| G2 all cases | The frozen setting on all 30 cases; the circle cases are marked as tuning cases | See below |

**Expectations for G2.**
- With 24 numbers per frequency (456 in all) against tens of thousands of
  unknowns, the smoothing penalty does most of the work.
- Contrast 0.5 and 4: blurred objects at about the right place and size.
  Thin and sharp features (aphex strokes, cog teeth, cross corners, the
  c-shape cavity) are lost. Boundary RMS of several mm, so TG-002's 1 mm
  limit fails.
- Contrast 13.3: likely to fail. The iterative forward solve may not converge
  within its 100-iteration cap at χ = 12.3, and strong multiple scattering
  makes the loss nonconvex.
- Field residual well above BEM's 0.003. Each iteration costs 19 forward and
  19 adjoint lattice solves, so minutes per case.

**Scores, both methods.** GauGal's image scores (SSIM, RRMSE, PSNR, contrast
SNR) on one shared grid, with the BEM curve filled in; field residual per
frequency; boundary RMS and Hausdorff with GauGal's image traced at half its
peak χ; TG-002 recovery limits; contrast estimate (GauGal: mean ε_r inside
the traced boundary); fit time. Timed runs have the machine to themselves.

## Order

1. Now, no new code: R1.
2. In parallel: the MR-001 contrast unknown; the GauGal TG-002 builder and
   multi-frequency loop; MoM rasterisation and rescaling.
3. F1 and F2, which set GauGal's lattice; then G1 and G2.
4. R2 once its code passes the two checks; R3 only on R2 failures.
5. Report `report.md` in this folder: forward figure, MR-001 table, method
   comparison table, gallery (truth / BEM / GauGal), and what each method used.

## Deferred

- A BEM arm without the damped warm-up, real data only, to match GauGal's data.
- Noise (5% complex Gaussian, seed 1000, was agreed for a noisy stage).
- The 31 single-disk cylinders and GauGal's own datasets.
- Material recovery stays a research option until R2 succeeds; the benchmark
  default is unchanged.
