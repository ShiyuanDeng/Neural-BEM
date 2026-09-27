# Latest six scenes versus the original hybrid

Requested 27 September 2026. The user selected **fixed release with initial
cleanup** from the latest complete six-scene campaign, SC-043. Each video
uses the established boundary, residual heatmap and shape-harmonic format,
with original hybrid above and the selected latest trajectory below.

[Download all six videos and final-frame previews](latest_six_vs_original_hybrid.zip).

| Scene | Comparison video | Final frame | Original RMS (mm) | Latest RMS (mm) |
|---|---|---|---:|---:|
| Circle | [1_circle.mp4](1_circle.mp4) | [PNG](frames/1_circle_final.png) | 0.00259433 | 0.000244674 |
| Star | [2_star.mp4](2_star.mp4) | [PNG](frames/2_star_final.png) | 0.522234 | 0.0110285 |
| C | [3_c.mp4](3_c.mp4) | [PNG](frames/3_c_final.png) | 3.20199 | 0.00409290 |
| Kite | [4_kite.mp4](4_kite.mp4) | [PNG](frames/4_kite_final.png) | 2.98258 | 0.0346059 |
| Peanut | [5_peanut.mp4](5_peanut.mp4) | [PNG](frames/5_peanut_final.png) | 2.94427 | 0.00242780 |
| Hook | [6_hook.mp4](6_hook.mp4) | [PNG](frames/6_hook_final.png) | 0.525391 | 0.00205331 |

All six share a **498-frame, 41.5-second timeline at 12 fps**, 1800 × 1100.
Every saved state is shown, including stage starts and the explicit cleanup
intervention. There is no shape interpolation. Original hybrid holds its
endpoint through the later continuation stages. Playback time is not solve
time, and this full-history display is not a matched-work comparison.

## Which histories are shown

- **Original:** SC-029 baseline, K192, four stages with M3/5/7/9. The stored
  SC-039 traces supply the diagnostic fields.
- **Latest prefix:** the declared SC-040 six-scene trajectories, including
  SC-035 state-band stages and SC-038 all-frequency M11/15/19 releases.
- **Further continuation:** the recorded SC-041 M25 star and M22 kite paths,
  followed by SC-043's one-off K64 cleanup and fixed-release policy on all six
  cases. No case-specific choice of the best policy or intermediate state is
  made. The final frames are the actual SC-043 fixed endpoints.

These are the existing six single-object development scenes. SC-047/048's
two-object local screens are separate experiments, not substituted into this
comparison. The latest paths use more frequencies, continuation stages and
work than the original hybrid. For the matched policy assessment, see
[SC-043](../../SC-043-prospective-band/README.md).

## Reading the established display

The dashed boundary and dashed spectrum are the target, used only for
evaluation. Both methods use common boundary limits and heatmap colour scales.
The amber box marks the active frequencies and nominal normal-update band M.
The first heatmap column combines the active frequencies. Orders 0–48 are
shown so the new bands through M43 are visible; upper bars cover 49–192.

The historical heatmap is a **capped QR residual score in ideal normal
ripples**, not a prediction of achievable finite-step improvement. Its basis
differs from the projected solver's complete finite-update derivative. The
white line is the first sensitivity crossing of an assumed 0.01% display
level; it is not a measured noise floor or a recovery limit. Individual
frequencies have only 48 real data values, so their sequential QR spaces
saturate by order 24; the combined-frequency column can extend higher.

The harmonic strip uses the established Cartesian coefficient convention,
combining coefficients c(1+m) and c(1-m). It is an exact ripple amplitude on a
circle and a parameter-dependent shape descriptor on general curves. K is
the storage band, not a guaranteed geometric resolution.

## Verification and reproduction

**Faster preparation, 27 September:** prefixing the command below with `SC_FORWARD_BACKEND=cuda` runs the same diagnostics on the GPU, 5.1–7.0× faster per case. Frontier indices are identical, and displayed heat agrees within 1.6e-8 in log10. See [SPD-011](../../../speedup/SPD-011-20260927-cuda-assembly/README.md#gate-4-video-preparation). The committed records above were prepared on the CPU.

The renderer checks the common start, exact linkage between saved prefixes,
the explicit K64 intervention, final geometry and recorded RMS. Each heatmap's
active-frequency residual must reproduce the saved objective. Every state is
also recomputed at twice its recorded node count for a display refinement
check. Input hashes, state counts, work receipts and video hashes are retained
in `manifest.json`, `receipts/` and the portable `prepared/` records.

All **743 verification checks passed** (`verification.json`), covering all
531 saved states, source hashes, endpoints and full MP4 decoding. The largest
saved-objective discrepancy was 2.23e-16; final RMS discrepancies were zero.
Doubling the sampling grid changed the displayed heatmap by at most 0.00253
dex, with no frontier shifts. The existing atlas-video regression suite also
passed (four tests). Decoded frames were inspected for layout and legibility.

No inverse fitting is performed. Existing SC-039/040 traces are reused;
missing diagnostic fields for the newer saved states require fresh forward
and reciprocal evaluations, which are counted separately. The prepared JSON
contains everything needed to render again without those raw NPZ files.

The main preparation receipts record 1,824 forward and 1,824 reciprocal
frequency batches. A parallel three-state preparation added 114 of each:
these additional counts are reconstructed from completed caches because its
first receipt export failed. The receipt-only recovery required no new solves;
`prefill_accounting.json` records the limitation and retained failure log.
Total fresh diagnostic work was therefore 1,938 forward and 1,938 reciprocal
batches, separate from the original inverse work. An algebraic joint-column
cache experiment was not used by the final prepared records and earns no
work reduction. The exact numerical preparation source is preserved in
`sources/preparation_renderer.py`.

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/videos/latest_vs_hybrid/render.py \
  --render-only
```

Omit `--render-only` to reconstruct the diagnostics from the original stored
traces and saved geometries. `--workers` controls independent scene preparation.
Use a fresh output directory to preserve the delivered evidence. Older video
bundles remain unchanged.
