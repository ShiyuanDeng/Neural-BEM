# Automatic Fourier topology inversions

The same controller receives data and initial geometry, with no target count or event policy.

| Inversion video | Component counts | Relative data error | Sampled Hausdorff (mm) | Stop |
|---|---|---:|---:|---|
| [repeated-birth](repeated-birth/inversion.mp4) | 0 → 1 → 2 → 3 | 1.01e-09 | 4.99e-08 | recovered |
| [split](split/inversion.mp4) | 1 → 2 | 1.03e-06 | 4.047e-05 | recovered |

[Watch all 2 inversions](topology_changes.mp4).

The visible-refinement demonstrations use a fixed 16/24/36/48-mm birth ladder and zero candidate-refinement steps. Normal LM updates begin after the raw topology seed is accepted and every update appears in the video. Dotted curves retain the accepted seeds. See each case’s `radius_audit.json` for the exact searched radii and target offsets. The split starts with a 100-mm-radius circle and tests smaller circular seeds from its cut regions.

Each case contains `manifest.json`, `metrics.json`, `trajectory.json`, `topology_passes.json`, observations and sensitivity rasters. Videos contain actual accepted states; topology transitions are discrete. Both production and refined objectives must improve.

These are noiseless, same-material, 0.5-GHz demonstrations. Nested holes and touching boundaries are unsupported. This named evidence bundle includes its videos, figures, observations and sensitivity rasters in Git.
