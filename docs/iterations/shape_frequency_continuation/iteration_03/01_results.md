# Iteration 03 — partial Figure 1 agreement and unresolved fidelity

Opened 2026-09-22 by [SC-014](../../../../results/validation/shape_continuation/SC-014-figure1-calibration/README.md),
which investigates the calibration question [iteration 02](../iteration_02/01_results.md)
left open. [Track handoff](../README.md).

**Interpretation corrected on 2026-09-22 after Codex's review of `1a6a55a`.**
The [review](02_proposals/01_codex_review.md) accepts the optimizer repairs,
records two remaining profile differences, and withdraws the earlier claims
that the plotted axis, author band rule and replication were settled. The
original wording remains in Git history; the run measurements are unchanged.

## What opened this cycle

Iteration 02 recovered the glider but scored 2.5x-26x *below* the published
curve under the printed normalized-area interpretation, and named calibration
as the next decision. Codex then reviewed the work
and left [executable probes](../iteration_02/02_proposals/01_codex_review_resolution.md);
two of its findings were real defects, and its source manifest listed the
transmission drivers the earlier reading had missed.

## Result

**The corrected optimizer is a better foundation for continuation experiments.**
GN and SD now receive independent filter searches, and explicit direction
selection removes the SD warm-up counter's dependence on chunk size. Both
regressions pass; the full reviewed suite has 171 passing tests.

**Agreement depends strongly on settings and the area interpretation.** The
inspected upstream drivers save raw symmetric-difference area, while §4 defines
`εΓ = δA/A`. Raw-area plotting is plausible, but the Figure 1 plotting path has
not been recovered. Decreasing scattering residual does not guarantee decreasing
shape-area error, so comparison with the initial circle cannot settle the axis.

The five executed arms give the following agreement under the **raw-area
hypothesis**; both readings are retained in SC-014:

| Contrast | Profile | Agreement (log10 RMS of ratio) |
|---|---|---:|
| 0.33 | **driver** | **0.117** |
| 0.33 | paper (§4 prose) | 0.424 |
| 10 | **scaled** | **0.246** |
| 10 | driver | 0.629 |
| 10 | paper (§4 prose) | 0.675 |

**Contrast 0.33 has encouraging partial agreement over k ∈ [1,5].** Its
published/ours ratio has median 1.0367 but spans **0.6504–1.5688**; it is not
pointwise agreement within 4%. **Contrast 10 remains unmatched.** The published
curve lies between two tested curves under the raw-area reading, but that does
not identify a bandwidth rule between them. The profiles also change optimizer,
resolution, tolerance and iteration cap, so they do not isolate the band's effect.

The closest k=1 error occurs for the M=2 profile at both contrasts. That scalar
comparison cannot identify the authors' bandwidth or optimizer trajectory.
Neither an exact Figure 1 configuration nor its plotting convention is recovered.

## Remaining implementation differences

- **Stopping norm:** our profiles use RMS physical displacement; upstream uses
  filtered coefficient norm. Six of the 17 low-contrast driver stages stop
  while the reference coefficient threshold still fails. The impact of changing
  this test on the final reconstruction has not been measured.
- **Resolution attribution:** upstream's local `nppw=30` is for data generation.
  Its inverse starts with 500 nodes and does not set `opts.nppw`. Our profile
  uses 30 in inverse K/N sizing. Saved resolution checks pass, but describing
  that as the driver's inverse resolution was incorrect.

`driver` remains the CLI label for a driver-inspired profile with local choices,
not the authors' recovered Figure 1 inputs. The
[review](02_proposals/01_codex_review.md) gives pinned source links and the
per-arm stopping counts. Numerical settings are unchanged by this amendment.

## What this costs and what it means for the track

At contrast 10, the `paper` profile spent 1334 forwards and 639 s, versus 126
forwards and 108 s for `scaled`. These are different configurations producing
different reconstructions; proximity to the published error curve is not a
recovery-quality gate. Timings came from concurrently running arms and are not
a controlled wall-clock comparison. Forward counts are exact.

For the track's actual question — whether adapting shape harmonics and frequency
steps improves recovery per unit work — a fixed control must have explicit,
frozen settings and quality criteria. **SC-014 does not establish an authoritative
paper-matched baseline.** Resolve the stopping/resolution choices before freezing
that control. Paper reproduction and adaptive improvement remain separate claims;
a control should not be selected solely for resembling the published error curve.

## Limits

- `scaled` was proposed after seeing `driver` fail at contrast 10: one degree
  of freedom fitted against a digitized plot. Its equality with `driver` when
  `ki <= k` is algebraic, not independent validation at high contrast. It is
  not a recovered author setting.
- The published curves run to k=10; ours stop at k=5 and k=3.
- Digitization is worth about 0.75% per pixel, so agreement below a few percent
  is not meaningful.
- Nodal Müller/Kress still replaces Alpert quadrature; the remaining declared
  differences in the [audit](../../../../experiments/shape_continuation/PAPER.md)
  stand. Matching `εΓ` is not a claim of identical trajectories.

## Review recommendations

These are recommendations, not implemented numerical repairs or new run results.
The user's current instruction is to correct the write-up and record the verdict.

1. Make the stopping measure explicit and resolve which numerical resolution
   convention the reference-inspired profile should use; validate any repair
   before comparing trajectories.
2. Keep both plot interpretations until Figure 1 plotting provenance is found.
   Do not infer the author settings by fitting additional rules to the same plot.
3. Freeze a clearly specified fixed ladder and recovery/work metrics for an
   adaptive comparison. A later k=10 extension or independent geometry can test
   broader agreement; neither was run as part of this review.
