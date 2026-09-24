# SC-020 plan — the clean hybrid under SPD's policy, against SPD

2026-09-23. Requested by the user after the
[pipeline draft](02_proposals/02_clean_pipeline_draft.md): "build it … the first
test should be using the same policy as in SPD then compare with SPD. stop until
test passes or you hit every wall." Existing branch and checkout; no new
branch or worktree.

## Question

Does the clean hybrid, running SPD's own continuation schedule, recover SPD's
single-object case as well as SPD does? The hybrid combines Borges' normal
move with an arclength refit on every trial, an SPD-style LM backend and the
package's nodal Müller physics. A pass qualifies the backend as a
fixed-schedule baseline on this case only. A failure must be located before
any policy work.

## Case and arms

SPD's frozen twelve-scene suite contains exactly one single-object target,
**merge** (one 92 × 39 mm ellipse). Its SPD-default run
([TOP-025 compiled](../../../../results/validation/topology/TOP-025-compiled-20260917-115641/))
hands a single K17 Cartesian component to the four-stage continuation. That
continuation is the comparison. Topology is outside it.

| Arm | What runs |
|---|---|
| `spd` | A fresh `experiments.top025.run.run_scheduled_continuation` from the saved handoff. It uses the default runtime, which routes one component to full Kress with reciprocal derivatives. This is SPD's code unchanged. |
| `hybrid` | `lm_backend.run_policy` with `BorgesUpdate` and the SPD-matching policy below. |

Both arms read the same handoff boundary, the same 24 × 4 training
observations and the same two evaluation frequencies. They are copied from the
SPD bundle and hash-checked. Both are scored by SPD's own endpoint scorer
(`experiments.top020.run.score_predictions`) using SPD's Kress predictor at
256/512 nodes. The hybrid curve is converted exactly to a Cartesian state for
scoring.

## Frozen hybrid settings

| Setting | SPD | Hybrid |
|---|---|---|
| Frequency sets, weights | 0.5; 0.5–0.75; 0.5–1; 0.5–1.25 GHz cumulative, equal weights, SPD normalization | Same, with the residual map shown bitwise equal in tests |
| Stage work quotas / LM iterations | 1000/1250/1750/4000 units; 22 | Same units and reservation rule; 22 |
| Total cap / wall | 8012 units / 7200 s, 12-unit endpoint reserve | Same |
| LM | λ₀=1e-3, ×10 on failure (5 trials), ×0.3 on success, 7 halvings, Marquardt scaling with floor 1, gradient 1e-7, loss 1e-14, relative step 1e-7, no loss-change stop | Same formulas |
| Acceptance | Strict production decrease, then refined 512-node margin rule; hard stop if production and refined predictions differ by more than 1e-5 at 0.5 GHz or 1e-7 at the other frequencies | Same, with the rule shown equal to SPD's in tests |
| Update space | 33 gauge-fixed directions: translation, radius, polar radial modes 2–16 of K17 | M=16: 33 arclength harmonics 0–16 of the normal distance h, one-to-one on a circle |
| Step bound per direction | Radius 12 mm, translation 18 mm, shape 6 mm (equivalent to its reduced-coordinate clip) | Order 0: 12 mm, order 1: 18 mm, order ≥2: 6 mm |
| Storage / gauge | K17, polar angle, fixed point per trial | K=96, arclength refit per trial, projection tolerance 1e-7 |
| Physics | Nodal Kress with reciprocal derivatives, N=256, refined 512 | Nodal Müller with Hadamard derivatives, N=256, refined 512 |
| Feasible set | Valid curve inside the 0.2–0.8 m box, 8-mm component-radius floor | Valid, simple curve inside the same box; no radius floor |

The following differences are declared:

- The **K=96 storage band** is a representation requirement, not extra shape
  freedom. The arclength refit of the handoff needs K≥64 at the unchanged
  tolerance, and so does the true ellipse.
- **Equal direction counts are not equal spaces.** Harmonics are taken in
  polar angle for SPD and in arclength for the hybrid.
- SPD's **radius floor** is a topology safeguard. Its certificate assumes the
  polar gauge; it is inactive for this ellipse, whose semi-minor axis is 39 mm.
- The hybrid **reuses the forward factorization** for its Jacobian. SPD
  re-solves the base system, so the work units differ by construction.

## Development evidence before freezing

These results come from development runs, not the comparison. The scripts
and outputs are saved in the SC-020 bundle's `development/` directory:

- **Physics bridge.** Package predictions on the handoff agree with SPD's
  saved 256/512-node predictions to ≤4.1e-13 at all six frequencies.
- **Scorer.** SPD's final state rescored through the harness reproduces its
  recorded Hausdorff (0.0478 mm), IoU, training and evaluation errors exactly.
- **Derivatives.** At the merge state, with ε=1e-6 m, the hybrid Jacobian
  agrees with central differences through the actual sample–move–refit trial
  to 5.7e-10 relative in a random direction and 1.3e-8 for harmonic 16.
- **Stage-1 dry run.** The loss falls 3.1e-9 → 2.2e-12 in three steps, then
  plateaus near 6.8e-13; SPD reaches 5.8e-15. At the plateau the undamped
  Gauss–Newton step is 1.04 mm along directions with singular values ~5e-5,
  and its actual loss (2.2e-7) is set by the second-order term (kδ)². The
  handoff's normal error beyond arclength harmonic 16 is 0.0496 mm and is
  unchanged after the stage (0.0497 mm), because a band-16 update cannot reach
  it. SPD's final state carries 0.018 mm there.

**Prediction.** With M=16 the hybrid keeps about 0.05 mm of error beyond the
update band throughout. Its training loss therefore plateaus above SPD's, at
extra trial cost. The 1-mm boundary gate is not threatened.

## Pass criteria (frozen)

1. The `spd` arm completes the schedule. Its final state hash equals the
   TOP-025 record, or any difference is explained, so the reference is
   reproduced.
2. The `hybrid` arm completes the schedule with no hard stop. Every stage
   endpoint is numerically qualified by SPD's scorer.
3. The hybrid's final SPD gates pass:
   - correct count;
   - matched Hausdorff ≤1 mm;
   - IoU ≥0.90;
   - 0.5 GHz training error ≤0.003;
   - worst evaluation error ≤0.05.

Reported but not gated: per-stage accepted steps, stop reasons, training
losses, final geometry and evaluation errors relative to SPD, trial outcomes,
work units and elapsed time. Both arms run sequentially with one BLAS thread;
their timings are descriptive observations on a shared host.

## Limits and next decision

This is one near-truth case: the handoff is 0.55 mm from the target. It
qualifies the backend and policy interface against SPD. It does not test
recovery from distant starts, a harder single-object target or a
policy-level claim.

- **If it passes:** the next test is the same comparison on harder
  single-object starts. The mapping of M to SPD's update space is a declared
  control for that test.
- **If it fails:** classify the failure under the implementation principles
  before changing anything.
