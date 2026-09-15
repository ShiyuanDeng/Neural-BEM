# TOP-018: two-star S/F comparison video

[Watch the video](two_star_S_vs_F.mp4) · 50 seconds · 1600 × 900 · 24 fps · H.264 MP4

The two panels follow the saved TOP-018 accepted states from their identical
common low-frequency start through the prescribed stage-4 endpoints. The
single-frequency S arm keeps fitting 0.5 GHz; F adds 0.75, 1.0 and 1.25 GHz
across stages 2–4. Solid curves are reconstructed boundaries; dashed curves are
the target. Both components remain at Cartesian K=9 throughout.

| Playback | Content |
|---|---|
| 0–5 s | Identical saved common start |
| 5–17 s | Stage 2 accepted states |
| 17–20 s | Stage 2 endpoint scores |
| 20–32 s | Stage 3 accepted states |
| 32–35 s | Stage 3 endpoint scores |
| 35–43 s | Stage 4 accepted states |
| 43–50 s | Prescribed final comparison |

## Measured outcome

| Arm | Final boundary error (mm) | Sampled IoU | Worst development-evaluation error | Recovery gates |
|---|---:|---:|---:|---|
| S | 11.793168 | 0.738281 | 1.306218 | Fail |
| F | 0.00167644 | 1.0 | 3.323707e-6 | Pass |

Both endpoints pass the numerical checks at 256/512 nodes. Evaluation uses
1.5 and 2.5 GHz; those frequencies were excluded from fitting. The video shows
the bounded fixed-count comparison from saved COMMON. The
[numerical report](../TOP-018-20260915-resolution-qualified-pair/README.md) and
[iteration-12 results](../../../../docs/iterations/topology/iteration_12/01_results.md)
define the experiment and its scope.

## Playback and provenance

- All 83 catalog records appear, including accepted endpoints absent from the
  last trajectory line. Stage transitions and endpoint scores are checked
  against saved state hashes.
- Playback aligns the stages and uniformly spaces each arm's saved records.
  Repeated frames provide readable timing; coefficients are never interpolated.
  Playback timing does not represent computational time or equal work.
- Scores appear only when the displayed state is an exact saved common-start
  or stage-endpoint state. No intermediate score is inferred.
- Rendering samples the saved curves geometrically and makes no physical
  forward calls. All 119 files covered by the numerical bundle's artifact
  manifest are verified before and after rendering.

[Video manifest](video_manifest.json) records the complete state catalog,
frame timeline, input hashes, renderer hash and output hashes.
[Final comparison](final_comparison.svg) is an exportable still.
[Validation](validation.json) records media decoding and provenance checks.

## Reproduce

From the repository root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/topology/TOP-018-20260915-two-star-video/render_video.py
```

Use `--preview-only` to write four chapter previews under `/tmp` without
encoding the MP4. The renderer requires Matplotlib and FFmpeg. It does not
modify the source numerical bundle.
