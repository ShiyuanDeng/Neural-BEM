# TG-002: the ten-scene benchmark (inputs)

The canonical inputs for new inverse experiments. Code, commands and the default method are in
[`experiments/benchmark`](../../../../experiments/benchmark/README.md). Retired scene sets are
listed in [LEGACY.md](../../../../experiments/benchmark/LEGACY.md). This folder holds inputs
only. **No inverse fit has been run.** The first experiment,
[NL-001](../../../../docs/iterations/cleaned_interfaces/iteration_26/03_plan.md), is
pre-registered and awaiting approval.

![TG-002 gallery](gallery.png)

- **Start:** one 65 mm circle at (0.5, 0.5) m for all 30 cases (`inputs/start.json`).
- **Truths:** `inputs/<scene>/truth.json`, in package units (origin at the scene centre,
  unit 5 cm). Each scene's centroid is 22–38 mm off centre.
- **Data:** `inputs/<scene>/c<contrast>/{observations,damped}.json` hold noiseless N2048
  predictions at the 19 real and 19 damped (k(1 + 0.25i)) frequencies, on the frozen
  CI-001 24-pair ring.
- **Qualification:** `{qualification,damped_qualification}.json` hold the N1024/N2048
  per-frequency relative differences (gate 1e-8), from CPU reference `nodal_kress`.
- **Seal:** `manifest.json` hashes every input; `sources.tar.gz` and the recorded source
  digests give generation provenance.

**Shape fidelity.** The seven historical shapes were checked against their recorded truths
after removing placement and rotation. All matched within 0.25 mm, which is the resolution
of that check. A first draft resampled the formula shapes by arclength before band
truncation, which distorted them by up to 1.9 mm. It was found from the gallery and fixed
before any data were generated. Formula shapes now keep their historical uniform-parameter
sampling. Only polygons and thick arcs are resampled by arclength. `cross`, `cog` and
`aphex_twin` are intentionally rounded by a Gaussian taper; they lie 1.8–3.6 mm from their
sharp outlines.

## Qualification

All 60 catalogs qualified; there were no failures. The worst difference is 1.6e-13 (`hook` at contrast 4). Generation took 77 min of wall time on the CPU reference path; see `generate.log`.

| Scene | Contrast | Real: max relative N1024 vs N2048 | Damped | Seconds (real + damped) |
|---|---:|---:|---:|---:|
| `circle` | 0.5 | 1.4e-14 | 3.6e-15 | 148 |
| `circle` | 4 | 5.5e-15 | 1.5e-15 | 165 |
| `circle` | 13.3 | 1.1e-14 | 3.1e-15 | 158 |
| `kite` | 0.5 | 3.7e-15 | 4.0e-15 | 132 |
| `kite` | 4 | 3.1e-15 | 2.1e-15 | 151 |
| `kite` | 13.3 | 1.2e-14 | 2.3e-15 | 152 |
| `peanut` | 0.5 | 6.5e-15 | 3.8e-15 | 140 |
| `peanut` | 4 | 5.6e-15 | 2.7e-15 | 157 |
| `peanut` | 13.3 | 2.0e-14 | 1.8e-15 | 155 |
| `star` | 0.5 | 5.7e-14 | 4.5e-15 | 151 |
| `star` | 4 | 5.2e-15 | 2.6e-15 | 165 |
| `star` | 13.3 | 1.8e-14 | 2.8e-14 | 157 |
| `asymmetric` | 0.5 | 6.5e-14 | 4.4e-15 | 147 |
| `asymmetric` | 4 | 3.7e-15 | 2.5e-15 | 163 |
| `asymmetric` | 13.3 | 2.5e-14 | 4.0e-15 | 157 |
| `c_shape` | 0.5 | 7.4e-15 | 4.0e-15 | 150 |
| `c_shape` | 4 | 1.0e-14 | 2.6e-15 | 164 |
| `c_shape` | 13.3 | 5.1e-14 | 6.0e-14 | 161 |
| `hook` | 0.5 | 8.0e-14 | 4.5e-15 | 144 |
| `hook` | 4 | 1.6e-13 | 2.4e-15 | 162 |
| `hook` | 13.3 | 4.7e-14 | 6.4e-15 | 158 |
| `cross` | 0.5 | 5.6e-15 | 3.0e-15 | 144 |
| `cross` | 4 | 5.7e-15 | 1.8e-15 | 161 |
| `cross` | 13.3 | 8.4e-14 | 2.9e-15 | 156 |
| `cog` | 0.5 | 8.0e-15 | 3.5e-15 | 146 |
| `cog` | 4 | 6.3e-15 | 2.3e-15 | 163 |
| `cog` | 13.3 | 3.8e-14 | 4.6e-15 | 158 |
| `aphex_twin` | 0.5 | 5.5e-15 | 6.3e-15 | 130 |
| `aphex_twin` | 4 | 6.3e-15 | 2.4e-15 | 152 |
| `aphex_twin` | 13.3 | 8.1e-14 | 1.4e-14 | 154 |
