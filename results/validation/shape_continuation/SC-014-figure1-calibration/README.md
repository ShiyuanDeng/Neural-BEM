# SC-014 — Which settings reproduce Figure 1

Run on 2026-09-22 at source `49f4128` plus the `scaled` profile added in the
same working tree. All five arms audit with **no source hash mismatches** and
completed their ladder with every stage committed after its N/2N field and
full-Jacobian check.

SC-013 asked why our reconstructions came out far *better* than the published
curve. This answers it: we were running neither the authors' configuration nor
their error measure.

![Published Figure 1 against each profile](comparison.png)

## Result

Agreement is the ratio published/ours per frequency, summarised as the RMS of
its base-10 logarithm — 0 means the curves coincide, 0.3 means a typical factor
of two in either direction. Both readings of the published y axis are reported;
see [the audit](../../../../experiments/shape_continuation/PAPER.md#area-scoring).

| Contrast | Profile | Ladder | Forwards | raw reading | as printed |
|---|---|---|---:|---:|---:|
| 0.33 | **driver** | k=1→5 | 206 | **0.117** | 0.459 |
| 0.33 | paper (§4 prose) | k=1→5 | 272 | 0.424 | 0.796 |
| 10 | **scaled** | k=1→3 | 126 | **0.246** | 0.376 |
| 10 | driver | k=1→3 | 167 | 0.629 | 0.276 |
| 10 | paper (§4 prose) | k=1→3 | 1334 | 0.675 | 1.052 |

**Contrast 0.33 replicates over k ∈ [1,5]** with the authors' driver
configuration: median ratio 1.04, and the staircase structure of the published
curve — flat runs broken by drops where the update band increments — appears in
the same places. §4's prose profile does not: it is uniformly better than
published, by up to 7.75x at k=4.75.

**Contrast 10 does not replicate.** The published curve falls by a factor of 9
over k=1→3; the prose profile falls by 33 (ending ~6x *below* published), the
driver profile by 1.7 (ending ~5x above). The published curve sits between them
throughout, so the band rule that produced it is bracketed but not identified.

## Two things this settles

### The published axis is the raw area difference, not §4's normalized `εΓ`

§4 defines `εΓ = δA/A` and the figure's axis is labelled `εΓ`, but every driver
in the reference repository computes `area(pdiff1) + area(pdiff2)` and nothing
there divides by the true area (2.6215 for this glider). Three lines of
evidence agree on the raw reading:

- It is the only reading under which the published k=1 points, 0.298 and 0.273,
  are **better than the unit circle the run starts from** (0.361). Read as
  printed they are 0.781 and 0.716 — worse than never moving, after a stage
  that runs to its iteration cap under an enforced residual decrease.
- It gives the better agreement wherever a profile matches at all: 0.117
  against 0.459 at contrast 0.33.
- Under it the best single interpretation across both contrasts scores about
  0.19; as printed, about 0.38.

### The update band is `⌊2 k L / 2π⌋` at k=1, with no contrast scaling

The first stage is the cleanest discriminator: every profile starts from the
same unit circle, and the reachable error is set by the band rather than by the
optimizer. Published against each profile's first stage:

| Contrast | Published / A | M=2 (driver) | M=3 or 9 (prose) | M=6 (scaled) |
|---|---:|---:|---:|---:|
| 0.33 | 0.2979 | **0.2984** | 0.1595 | — |
| 10 | 0.2730 | **0.2929** | 0.0962 | 0.1313 |

`M=2` matches at both contrasts — 0.15% apart at contrast 0.33, inside the
~0.75%-per-pixel digitization noise. That is `use_lscaled_modes`, and it
carries **no interior wavenumber**: §4's `⌊3 max(k,ki)⌋` would give 9 modes at
contrast 10, k=1, and a first-stage error 2.8x too small.

## Profiles

| Control | `paper` (§4 prose) | `driver` | `scaled` |
|---|---|---|---|
| Optimizer | GN and SD compared | steepest descent only | steepest descent only |
| Update band M | `floor(3 max(k,ki))` | `floor(2 k L / 2π)` | `floor(2 max(k,ki) L / 2π)` |
| Points/wavelength | 70 | 30 | 30 |
| Update tolerance | `1e-5` | `1e-3` | `1e-3` |
| Iteration cap | 50 | 100 | 100 |

`driver` is `tests/driver_charlie_transmission.m`, the reference's penetrable
configuration. `scaled` restores the prose's interior wavenumber inside the
code's arclength scaling; it is identical to `driver` whenever `ki <= k`, which
`compare.py` asserts, so the contrast-0.33 agreement is not a fit to it.

## Limits

- **`scaled` was chosen after seeing `driver` fail at contrast 10.** That is one
  degree of freedom fitted against the digitized plot. Its only independent
  support is that it is forced to equal `driver` at contrast 0.33. It is a
  proposed reconciliation, not a recovered author setting.
- The published curves run to k=10; ours stop at k=5 and k=3. The contrast-0.33
  agreement is demonstrated over half the published range, covering the k=1 and
  k=5 snapshots but not k=10.
- Figure 1's values are digitized from a printed log plot, at roughly 0.75% per
  pixel, with 35 and 36 of 37 points recoverable. Agreement below a few percent
  is not meaningful.
- Nodal Müller/Kress still replaces Alpert quadrature, and the other declared
  differences in the audit stand. Matching `εΓ` is not a claim of identical
  trajectories.
- Cost is not the same question as accuracy: the prose profile at contrast 10
  spent 1334 forwards and 639 s to land *further* from the published curve than
  `scaled` did with 126 forwards and 108 s. Its wide band makes Gauss-Newton
  proposals fail geometry and curvature checks repeatedly.
- Timings come from single-threaded processes sharing a 24-core host with up to
  four other arms, so they are not controlled wall-clock measurements. Forward
  counts are exact.

## Reproduce

Comparison of the saved bundles against the digitized figure, no solves:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/shape-continuation-mpl \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/SC-014-figure1-calibration/compare.py
```

It asserts each arm's qualification records, writes [comparison.json](comparison.json)
and the figure above. The published values come from
[SC-013's digitizer](../SC-013-paper-glider-recovery/digitize_figure1.py). The
five inverse commands were `paper.py --mode run` with
`--profile {paper,driver,scaled}`, `--contrast {0.33,10}` and
`--k-stop {5,3}`, under budgets that none of them reached.
