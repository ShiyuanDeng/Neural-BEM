# TOP-023 — a larger damping gives a better validated terminal step

**COMPLETED_DIAGNOSTIC; operational gate PASS.** Completed 2026-09-15 under the
[approved plan](approved_plan.md) and the user's remaining-work authorization.
This is a training-only diagnosis at TOP-022's frozen failed endpoint. No inverse
was run and no fresh recovery or full-suite candidate is qualified.

The full 256-node h=1e-4 Jacobian reproduces the saved terminal gradient. Both
selected directions pass the inherited two-scale/two-resolution checks. Their
relative derivative changes are 9.78e-6 and 1.21e-5, below the 0.25 limit, with
signals well above measured numerical floors. The dominant reduced gradient
coordinate is -0.0142759872 at 256/h=1e-4 and -0.0142760990 at 512/h=5e-5.
This selected-direction evidence supports the non-small measured gradient; it
does not qualify every Jacobian column or an entire nonlinear basin.

The measured Jacobian singular values range from 62.2656 to 0.278971, ratio
223.20, in the stated orthonormal gauge coordinates. All 34 coarse stencils are
central. **No coordinate bound is active in any of the four raw LM proposals**;
clipping is not the cause of their difference at this terminal state.

| Damping | First accepted backtrack | Candidate calls | Production gain | Endpoint objective | Normal RMS step (mm) |
|---|---:|---:|---:|---:|---:|
| 3.1381e-15, next baseline value | 2 | 24 | 1.51177e-7 | 2.175614e-5 | 0.115879 |
| 1e-6 | 2 | 24 | 1.51681e-7 | 2.175563e-5 | 0.115681 |
| 1e-4 | 1 | 16 | 1.27401e-7 | 2.177991e-5 | 0.197921 |
| **1e-2** | **0** | **8** | **6.01388e-7** | **2.130593e-5** | **0.036313** |

Every accepted candidate passes the existing 256/512 numerical and gain-margin
checks. The 1e-2 arm gives **3.978× the baseline production gain with one third
of its candidate calls** and a smaller physical step. It alone passes the
predeclared >=2× gain/no-more-candidate-calls gate. These are step measurements,
not complete-inverse speedups or reconstruction results.

## Work and decision

396 new charged/completed frequency systems, zero failures: 272 for the full
model, 48 for the remaining directional probes, 4 for repeatability, and 72 for
the four candidate searches. Eight historical training prediction systems are
reused. Active time is **274.108536 seconds**; the 600-call/1200-second caps hold.
85 pre-dispatch tests pass. All 202 measured sources and inputs remain unchanged,
including the inherited TOP-022 implementation. Raw complex predictions, model
algebra, stencils, gradients, damping/step calculations, acceptance, numerical
checks and counters replay with zero new solves. See [verification](verification.json),
[scorecard](scorecard.json), [model](model.json), [arms](arms.json) and
[owner review](closeout_review.md).

The result supports a separately bounded continuation comparison from the same
frozen failed endpoint: baseline next damping versus an initial damping reset
to 1e-2, using the existing optimizer. That comparison must measure reconstruction
and cost, not merely another training decrease. No candidate from this diagnostic
replaces the frozen state. TOP-020/022 negatives and TOP-018's different successful
entry remain preserved. TOP-021 is still undispatched; no production promotion.
