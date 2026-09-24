# SC-022 plan — atlas along fixed-schedule trajectories

2026-09-24. Agreed with the user after SC-021: "our focus atp should be
investigating atlas … record both [gradient and step] … run expensive dense
runs only on later cases". The user chose the cases: circle to star, wrong
circle, and a new non-polar shape. The merge-ellipse handoff is used only to
verify the build. Existing branch; no new branch or worktree.

## Purpose

Record the full frequency × shape-harmonic picture along real inversion
trajectories before choosing any adaptive strategy. This experiment is
descriptive. It makes no controller or policy claim; summaries are
measurements, and interpretation comes afterwards.

## What is recorded, per state and per frequency k

The coordinates are the backend's update coordinates: real Fourier
coefficients, in metres, of the normal distance h in the current arclength.
The atlas band is P=48, above the trajectories' M=32.

Each frequency uses its own objective normalization with weight 1, as the
backend would for a single-frequency stage.

| Layer | Meaning |
|---|---|
| Sensitivity | Column norms: what harmonic p *could* change in the data at k |
| Signed gradient | What the current misfit at k asks of harmonic p |
| Gauss–Newton block (P×P) and eigenvalues | Coupling between harmonics and the observed combinations |
| LM step | `−(G_k + λD)⁻¹ g_k` at the trajectory's live damping λ, with D = max(diag G, 1): what the backend would do with k alone |
| Truncated GN step | Undamped, with relative eigenvalue cutoff 1e-10 |
| Evaluation only: true error | The normal distance to the truth, decomposed on the same harmonics. It is kept in a separate file and never read by any fitting or step code. |

The stage objective's own step (weighted sum over the active frequencies)
is also recorded, so per-frequency steps can be compared with what the
schedule actually did.

## Build verification (merge, no dense runs)

1. **Consistency.** The stage LM proposal assembled from the per-frequency
   layers must equal the backend's own proposal at the same state and damping
   (a unit test).
2. **Diagnostic.** At SC-020's stage-1 stall state (M=16), the 0.5 GHz step
   layer with P=48 must request harmonics above 16, where SC-021 showed the
   missing correction was. It must also agree in sign and order of magnitude
   with the true-error layer in well-determined harmonics.

If either check fails, the atlas does not measure what the M decision
needs. Stop and diagnose before any dense run.

## Cases

The acquisition is SPD's: a 24-pair ring at 0.30 m around (0.5, 0.5), with
sand/plastic contrast 0.5. All three cases start from the legacy default
circle: radius 65 mm at (0.48, 0.52).

| Case | Truth | Source |
|---|---|---|
| Wrong circle | Circle of radius 50 mm at (0.50, 0.50) | Legacy wrong-circle control |
| Circle to star | r = 0.05(1 + 0.25 cos 5θ) at (0.50, 0.50) | Legacy star target (also SC-018) |
| Circle to C | Smooth thick arc: centreline 40 mm, half-thickness 18 mm, ±110°, smoothed to natural band 10, rotated 0.3 rad | New. No interior point sees the whole boundary (LP margin −21.8 mm), so a polar chart cannot represent it |

**Observations.** The catalog is 19 frequencies, 0.25–2.5 GHz in 0.125 GHz
steps.
- The circle uses the analytic multi-cylinder series.
- The star and C use SPD's Kress predictor at 1024 nodes. They must agree
  with 2048 nodes to ≤1e-9 relative, and with the package's Müller solver
  to ≤1e-8, at every frequency.

The fixed schedule sees only its four training frequencies; the atlas uses
the whole catalog.

## Trajectories

The trajectories use the hybrid with the SPD-matching schedule and M=32, as
in SC-021. The frequencies are 0.5, 0.75, 1.0 and 1.25 GHz, with the SPD LM,
acceptance, quotas and caps.

**Uniform numerics.** Every case uses K=192 storage, N=512 production and
1024 refined nodes, and the unchanged 1e-7 projection tolerance. K is the
smallest value on the ladder at which the star truth is representable in
arclength at that tolerance; the C needs 64. The same K for every case keeps
the setting free of case-specific information.

Every accepted state and its step coefficients are recorded. The atlas is
evaluated at every accepted state. The trajectories' recovery is scored with
package metrics (sampled Hausdorff, area error and per-frequency relative
errors) for context, not as a pass/fail claim.

## Budget and storage

- **Trajectories:** SPD caps of 8012 units / 7200 s each; the three run in
  parallel on one thread each.
- **Atlas:** about 1 s per cell (one 512-node solve plus one reciprocal
  Jacobian), so roughly 19 × states × 3 cases.
- **Storage:** dense layers go in `.npz` (not tracked by git). Per-state
  summaries and hashes go in JSON (tracked).

## Limits

- The atlas describes states the fixed schedule visits. An adaptive policy
  will visit others; `atlas.transport_overlap` can quantify how comparable
  harmonics are between states.
- The dense catalog is diagnostic data beyond SPD's acquisition. Any
  strategy derived from it must be re-checked with the data a real policy
  would have.
- The data are noiseless, in 2-D, for single objects at one contrast.

## Amendment, 2026-09-24: a second band rule for the trajectory generator

**Observed.** With the fixed M=32 band, every case stalls early:

| Case | Final Hausdorff | Wall time |
|---|---:|---:|
| Wrong circle | 26 mm | 88 s |
| Circle to star | 34 mm | 41 s |
| Circle to C | 48 mm by stage 3 | — |

Every rejected trial is geometric: it fails the arclength refit or
self-intersects. None is rejected by the data.

**Mechanism.** From a distant start, SPD's LM puts large steps into weakly
determined high harmonics, each clipped at the 6 mm bound. The first
accepted star step carries 3–4 mm at harmonics 6–9. Later proposals are
invalid until halved six or seven times. By then every harmonic moves by the
same clipped ~0.1 mm, and progress stops. M=32 was validated only near the
truth (SC-021).

**Change.** A second trajectory arm uses the manuscript's §4 band rule,
M = floor(3·max(k, kᵢ)), in package units at each stage's highest
frequency. That gives M = 3, 5, 7 and 9, close to SC-015's measured 2.5k
detectability line. Everything else is unchanged.

The fixed M=32 runs are kept as arm `fixed32`. Their few states are also
surveyed, since they are exactly the far-start situation an adaptive M rule
must handle. The source change is recorded as a manifest amendment, and the
`fixed32` runs were verified against the original hashes.
