# GU-001: three gauge-keeping geometry updates on one hard scene

Pre-registered 2026-10-25, before any code for it exists. Approval: the user
agreed this plan in discussion ("finalise the plan"). Branch: the existing
`organised`. No new branch or worktree. Owner: Claude.

Method background: [Geometry update methods for the Fourier
boundary](../../../../Geometry%20update%20methods%20for%20the%20Fourier%20boundary.md).
Terms (gauge, speed unevenness, centred update, uncentred refit, N-update,
level penalty, slider) are defined in [the glossary](../../../../GLOSSARY.md).

## Questions

1. Do the uncentred refit, the N-update with level penalty and the slider
   stop speed unevenness from drifting on a hard scene?
2. Does any of them avoid the spectral update's near-touch failure on
   hook c13.3?
3. What does each cost in fit time?

## Decisions made while planning

- **Default stays `spectral`.** Certified spectral was considered as the
  default and rejected. When its certificate is undecided it falls back to the
  same sampled check, so it accepts at least every curve spectral accepts.
  It would not stop the four NR-001 failures, where the modal A1 `|W|^2`
  bound refuses a sampled-accepted trial curve. It also still checks the pushed
  curve, which D1 removed from spectral. PC-001 M1 (certified) and NR-001
  (spectral) recover the same 26 cases.
- **The `fit_stage` seam.** A geometry update is one file in
  `geometry_update_methods/`, one branch in `make_update` and one CLI choice.
  `fit_stage` needs no edit for a new geometry update. The level penalty is a
  loss term, not a geometry map, so it is the one addition to `fit_stage`.
- **The A1 refusal still ends the stage.** Turning it into a rejected length
  is a possible separate change, not part of GU-001.

## What changes

### `uncentred_spectral` (new geometry update)

- The trial returns the arclength refit R(w_a), cropped to the storage band,
  instead of c + R(w_a) − R(0).
- Its slope in `a` equals spectral's; the two differ only by the fixed
  c − R(0). It reuses spectral's `prepare` and derivatives unchanged, with no
  extra finite differences.
- Logged per accepted step: the zero-step jump ‖c − R(0)‖, the direct test
  of staying in the arclength gauge, and the crop size.

### `n_update` (new geometry update)

- z_new = Π_K[z + η N + τ z′], with N = −i z′ the unnormalised outward normal.
  η and τ are real series of the update band.
- The unknowns are metres: h = η J̄ and s = τ J̄, with J̄ = L/2π. The default
  coefficient clip (`step_bounds_m`) then applies to both unchanged.
  - The clip bounds h, but the actual normal move is h J_Γ/J̄. Where the speed
    is above its mean, the boundary moves more than the bound. `measure`
    reports the actual move, so this shows in the log if the arm drifts.
  - Bounds on s are arbitrary, since tangential moves do not change the
    boundary, but harmless.
- The map is linear in the unknowns, so `.derivatives` is exact coefficient
  arrays (index shifts and convolutions). It reuses the direction
  construction of the NU-001 `n_update.py` deleted in `105af6380`, extended
  with the τ columns.
- In this round `n_update` always runs with the level penalty. Without it, the
  τ unknowns are seen by the data only through the crop. A plain N-update
  baseline would drop τ; that is not run here.

### Level penalty (new optional input to `fit_stage`)

- `fit_stage` gains `penalty=None`. When given, it supplies extra residual
  rows and their derivative in `a`. They are stacked under the data residual,
  so the loss, J, g, the damping and the accept test all include them. Without
  it, every number is unchanged.
- E = Σ_{m≠0} |ρ_m|²/ρ_0², where ρ are the Fourier coefficients of J_Γ².
  This coefficient form is exact. A mean over uniform nodes would alias unless
  it used at least 4K+1 nodes, because J_Γ² has band 2K and its square band 4K.
  The residual rows are √λ_J ρ_m/ρ_0 (m ≠ 0). Their Jacobian follows from
  d(J_Γ²) = 2 Re(conj(z′) dz′).
- λ_J = 0.01 × the data loss at stage entry, set once per stage and recorded.
  No other value is tried.
- Expected strength: at 10% speed variation E ≈ 0.02, so at stage entry the
  penalty is about 2×10⁻⁴ of the data loss. It matters only once the speed has
  drifted a lot or the data loss has fallen about 100-fold. That suffices for
  question 1 ("does it stop runaway drift"). E is logged per accepted step.
- Selected with `--level-penalty`, separate from `--geometry-update`. This
  round allows it only with `n_update`, so no untested combination runs.

### `slider` (new geometry update)

- dc = A a with A = (BᵀB + ξ UᵀU)⁻¹ BᵀH. B maps dc to the normal velocity,
  U to the uneven part of the relative speed change, H maps a to the requested
  push h. Rows are scaled by the square root of the arclength weights.
- ξ = 10. Q = 32K sample points (the tested ratio was Q = 1024 at K = 32).
  B and U have 4K+2 columns, so Q below that leaves BᵀB + ξ UᵀU rank-deficient.
  The entries contain 1/J_Γ, so no finite grid makes them exact.
- No resampling, no refit, no crop. No occasional refit during this test,
  so the slider is not mixed with the uncentred refit.

### Common to the three new arms

- The final trial curve gets spectral's checks: area, sampled speed and
  self-intersection. Nothing else differs between arms but the method.

## Run

- Scene: hook c13.3 from TG-002. Spectral fails on it in NR-001 when the A1
  `|W|^2` bound refuses a nearly self-touching trial curve. The doc's plain
  N-update also failed on hook.
- Four arms in parallel, one run each: `spectral` (rerun, so times compare
  under the same load), `uncentred_spectral`, `n_update --level-penalty`,
  `slider`.
- `--pipeline modal_fixed --localization none`, default `CumulativePolicy`,
  the benchmark's endpoint audit. Worst case about 35 min wall time
  (1,800 s fit limit per arm, plus the audit).
- No reruns and no setting changes after the run starts.

## Output

One table, one row per arm:

| Column | Meaning |
|---|---|
| Outcome | outcome and stop reason |
| Data loss | final data loss; for the penalty arm the penalty is shown separately |
| RMS error | boundary RMS error vs truth (mm) |
| Max error | Hausdorff distance vs truth, point-to-polyline (mm); the failure is a local near-touch that RMS averages away |
| Fit time | fit seconds and work units |
| Speed ratio | final max/min speed |

Per accepted step, in the saved history: zero-step jump (uncentred arm), E,
actual maximum normal move.

Videos, made only if the result is interesting or an arm fails: one per arm,
every accepted curve over the iterations with the truth overlaid and labels for
loss, stage and speed ratio. If the arm ends on a refused or failed trial
curve, the last frame shows it. Frames come from the saved history; nothing is
rerun.

## After the run

Commit and push code, this plan, results and any failure evidence to
`organised`. The next scene is chosen from what hook c13.3 shows.
