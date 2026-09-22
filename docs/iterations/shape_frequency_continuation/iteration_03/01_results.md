# Iteration 03 — what actually reproduces Figure 1

Opened 2026-09-22 by [SC-014](../../../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md),
which closes the calibration question [iteration 02](../iteration_02/01_results.md)
left open and supersedes its headline. [Track handoff](../README.md).

## What opened this cycle

Iteration 02 recovered the glider but scored 2.5x-26x *below* the published
curve, and named calibration as the next decision. Codex then reviewed the work
and left [executable probes](../iteration_02/02_proposals/01_codex_review_resolution.md);
two of its findings were real defects, and its source manifest listed the
transmission drivers the earlier reading had missed.

## Result

Both halves of the gap are now explained, and neither was a numerical error.

**We were reading the wrong axis.** §4 defines `εΓ = δA/A`, but every driver in
the reference repository computes the raw symmetric-difference area and nothing
there divides by the true area. Read raw, the published k=1 points become
better than the unit circle the run starts from; read as printed they are
worse, after a stage that runs to its iteration cap under an enforced residual
decrease. The raw reading also gives the better agreement wherever any profile
matches, and the better combined score across both contrasts.

**We were running the wrong settings.** §4's prose and the authors'
transmission driver disagree on the optimizer, the update band, the resolution
and both tolerances. Running the driver configuration:

| Contrast | Profile | Agreement (log10 RMS of ratio) |
|---|---|---:|
| 0.33 | **driver** | **0.117** |
| 0.33 | paper (§4 prose) | 0.424 |
| 10 | **scaled** | **0.246** |
| 10 | driver | 0.629 |
| 10 | paper (§4 prose) | 0.675 |

**Contrast 0.33 replicates over k ∈ [1,5]**: median ratio 1.04, with the
published staircase appearing at the same frequencies. **Contrast 10 does not**
— the published curve sits between the prose profile (too strong) and the
driver profile (too weak) across the whole window, so its band rule is
bracketed but unidentified.

The first stage is the cleanest discriminator, because every profile starts
from the same circle and the reachable error is set by the band, not the
optimizer. The published k=1 points match an update band of **2 at both
contrasts** — `use_lscaled_modes` with no interior wavenumber — against 9 modes
at contrast 10 under §4's rule.

## What this costs and what it means for the track

The prose profile is not merely inaccurate as a reproduction, it is expensive:
at contrast 10 it spent 1334 forwards and 639 s to land further from the
published curve than the scaled profile reached with 126 forwards and 108 s.
Its wide band makes Gauss-Newton proposals fail geometry and curvature checks
repeatedly, and the search pays a full filter sweep for each failure.

For the track's actual question — whether adapting the shape-harmonic band and
frequency steps beats a fixed ladder — this changes the baseline. The honest
fixed-ladder baseline is now the **driver profile at contrast 0.33**, which is
calibrated against a published result, rather than the prose profile, which is
not. An adaptive policy should be compared against the configuration the
authors actually ran.

## Limits

- `scaled` was proposed after seeing `driver` fail at contrast 10: one degree
  of freedom fitted against a digitized plot. Its only independent support is
  that it is forced to equal `driver` whenever `ki <= k`, so the contrast-0.33
  agreement is not a fit to it. It is not a recovered author setting.
- The published curves run to k=10; ours stop at k=5 and k=3.
- Digitization is worth about 0.75% per pixel, so agreement below a few percent
  is not meaningful.
- Nodal Müller/Kress still replaces Alpert quadrature; the remaining declared
  differences in the [audit](../../../../experiments/shape_continuation/PAPER.md)
  stand. Matching `εΓ` is not a claim of identical trajectories.

## Candidate next steps

None is proposed as an experiment or approved.

1. **Extend contrast 0.33 to k=10** on the driver profile, where the published
   curve drops another 25x. It is the only arm with a calibrated match, and
   whether the agreement survives the drop is the strongest single test of the
   replication. Cost grows as dense `N³`, but the driver profile's 30
   points/wavelength keeps it far cheaper than the prose profile.
2. **Identify the contrast-10 band rule** inside the bracket, rather than
   testing further guesses against the digitized plot. Any rule fitted to that
   plot needs a second, independent case before it is worth believing.
3. **Leave both alone and start the adaptive comparison** on the calibrated
   contrast-0.33 baseline, accepting that contrast 10 is uncalibrated.
