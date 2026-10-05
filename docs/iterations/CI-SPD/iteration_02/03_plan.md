# GP-001 — Adapted GauGal on TG-002: adapter repair, feasibility and parity

Prepared 2026-10-05 by Claude as the successor to the interrupted ON-002.
Basis: the [outside review](../../cleaned_interfaces/iteration_31/02_claude_review.md)
(finding R8). User request: "draft plans for all three tracks".

**Status: PROPOSED.** Nothing has run. Running it needs the user's explicit
approval of the ID GP-001. Approval covers Stages 0–6 below, their declared
repairs and the closeout. It does not cover RG-001, EW-001, a new branch or
worktree, unknown-material fitting, or new scenes.

## Why a successor plan

- ON-002 launched at 01:39:26 UTC on 2026-10-05. Its Codex turn was
  interrupted on purpose at 01:48:40 UTC.
- Its only batch was the 128-grid adapter check. BiCGSTAB converged in
  **0/12** configurations, with a true relative residual of 0.91–1.00 after
  200 iterations. That includes contrast 0.5 at 0.25 GHz, a weak scatterer
  that should converge in a few iterations. This is an adapter defect; no
  physics comparison evidence exists.
- Its plan, adapter contract, drivers, test and results were preserved
  unchanged in commit `7d50e3f8` (the `.npz` arrays are gitignored and remain
  local). Its four focused tests pass: disk cell area, kernel cell integral
  and sensor mask. The defect therefore most likely lies in the Galerkin
  operator scale or layout, or in the solver setup, which are rungs 2–4 below.

GP-001 keeps the scientific contract of the
[ON-002 plan](../iteration_01/03_plan.md) and its
[adapter contract](00_adapter_contract.md), both committed unchanged in
`7d50e3f8`, with the amendments below. Where this plan is silent, the ON-002 plan governs.

## Question

With the same TG-002 information, how does an adapted, known-material,
multi-frequency GauGal compare with the maintained modal BEM inverse? The
comparison covers recovery and audited time. A second question is whether a
charged volume-to-boundary hybrid adds recovery or speed.

## Amendments to ON-002

1. **B** is frozen at launch: the best qualified TG-002 recipe at that time.
   That is the ON-001 E recipe, unless RG-001 has closed with a qualified
   recipe. Record the choice, sources and hashes at launch.
2. A failed physics target does not end the comparison at a contrast. It
   **bars timing-parity claims** at that contrast. G still runs from the same
   centred start there. Its extracted contours are scored by the unchanged BEM
   audit, so recovery can be compared and no unmatched-physics speed ratio is
   ever published.
3. Grid choice comes from a truth-free start-disk convergence test (Stage 2a).
   Truth-shape representation floors (Stage 2b) are reported only to interpret
   the outcome. They are never used to select anything.
4. Adapter defect fixes found by the Stage 1 ladder are code corrections, each
   with a regression test. They are not the scientific repairs. The ON-002
   repairs remain: one grid escalation to 512, one precision change, and one
   inversion-phase repair.
5. A stage that fails qualification before any fit does not use up a later
   stage's budget or eligibility. It is closed with its evidence, and the
   decision table below applies.

## A-priori resolution table (registered before running)

Assumptions:

- Domain is 0.6 m square: (0.2, 0.2)–(0.8, 0.8) m.
- Background ε_r = 6, so the background wavelength at 2.5 GHz is 49.0 mm.
- Gaussian width σ = 0.8 × centre spacing.

| Grid / centres | Pixel | σ | Pixels per interior λ at 2.5 GHz: c0.5 / c4 / c13.3 | k_int σ at c13.3 |
|---|---:|---:|---|---:|
| 128 / 112 | 4.69 mm | 4.3 mm | 14.8 / 5.2 / 2.9 | 2.0 |
| 256 / 224 | 2.34 mm | 2.1 mm | 29.6 / 10.5 / 5.7 | 1.0 |
| 512 / 448 | 1.17 mm | 1.1 mm | 59.1 / 20.9 / 11.5 | 0.5 |

Predictions:

- The ON-002 target of 1e-3 relative field agreement with the sharp disk is
  reachable at contrast 0.5 on 256.
- At contrast 4 it is reachable on 512 at best.
- It is not reachable at contrast 13.3 on any grid up to 512. Edge blur of
  k_int σ ≥ 0.5 rad at the boundary dominates there.
- So timing parity is most likely testable only at contrasts 0.5 and 4.

## Stages

### Stage 0 — complete the ON-002 record (≤ 15 min)

1. Done before approval: the unchanged ON-002 files are committed in
   `7d50e3f8`. Verify that they are still unchanged at launch.
2. Add `CI-SPD/iteration_02/01_results.md`. It records the interruption time,
   the 0/12 batch and its receipts, with the status **INTERRUPTED,
   adapter-unqualified**.
3. Correct the ON-002 plan's status line in a separate commit.

### Stage 1 — adapter verification ladder (≤ 120 min)

Each rung must pass before the next starts. A failing rung localizes the defect.

1. **Physical kernel.** Run a dense pixel-collocation solve, with no Gaussians,
   on 32² and 64² grids for the TG-002 start disk at contrast 0.5 and 0.25 GHz.
   Compare against Mie. Expected: monotone convergence of roughly first order.
   This checks the units, sign and self-cell term of `physical_kernel`.
2. **Operator scale.** Estimate ‖M⁻¹K diag(χ)‖ by power iteration for the
   Galerkin operator at the same configuration. Prediction: well below 1,
   since this is the Born regime with |χ|(ka)² ≈ 0.35. A value at or above 1
   means a scale or cell-area defect.
3. **Operator layout.** Apply GauGal `collocation_a_forward` to random
   coefficient vectors on a small grid. Compare with a dense M − K diag(χ)
   built from the same basis and the dense kernel; require agreement
   ≤ 1e-6 in complex128. This checks the zero-padded FFT layout and the source
   and testing cell-area factors.
4. **Solver.** Compare a dense direct solve with GauGal's Jacobi BiCGSTAB on the
   small system, then on the full 128 grid. Require true residual ≤ 1e-6 with
   the iteration count recorded.
5. **Adjoint and finite differences.** Paired-sensor adjoint, algebraic adjoint
   and occupancy FD checks, as specified in ON-002.

Stop rule: if rungs 1–4 have not all passed at 120 minutes, close as
`ADAPTER_INCOMPLETE` with the failing rung identified. Publish no comparison.

### Stage 2 — physics feasibility (≤ 60 min)

**2a. Disk convergence (truth-free; selects the grid).** Compare the start disk
against Mie on 128, 256 and 512. Cover contrasts 0.5/4/13.3 at 0.25 and
2.5 GHz, both real and damped. Report the error and the observed convergence
order.

For each contrast, the comparison grid is the smallest one meeting 1e-3 at
every tested frequency. If none does, use 512 and label that contrast
**below physics target**: recovery comparison only, no timing parity.

**2b. Representation floor (interpretation only).** For all 30 truths, compute
G's forward prediction at the cell-integrated truth occupancy on the selected
grid. Record the maximum relative data residual over the 19 real frequencies,
against the frozen observations. This is the best data fit G's model can
reach, and it explains outcomes. Truth enters only here and selects nothing.

### Stage 3 — B/G screen (≤ 60 min)

Use the ON-002 eight cases: circle at all three contrasts, kite 0.5, star 13.3,
c_shape 13.3, hook 13.3 and aphex 13.3.

- B and G start from the matched centred object, with one case worker, the
  same hardware and the ON-002 timing boundary.
- G uses the ON-002 objective, TV schedule, step calibration, solver limits and
  contour rule, with the fixed 0.5 threshold.
- Its common output is the extracted contour, projected and passed through the
  unchanged BEM audit.

### Stage 4 — conditional hybrid H (≤ 50 min)

This is the ON-002 hybrid, unchanged:

- A charged volume phase starts from the same centred occupancy.
- The fixed-rule contour handoff enters BEM at `release_M11`.
- The ON-002 schedule and caps apply.

It is released by the ON-002 screen table: G is faster with comparable
recovery, or G recovers a B failure. Otherwise H is closed unrun, with the
reason recorded.

### Stage 5 — all-30 confirmation and repeats (≤ 150 min)

Run the frozen comparison (B/G, plus H if released) on all 30 cases. Add two
repeated timing pairs on circle 4, kite 0.5 and star 13.3 where both arms
qualify. Report recovery sets, paired times on common successes, failures and
suite totals. Mark timing parity per contrast only where Stage 2a met the target.

### Stage 6 — closeout (≤ 40 min)

Write `CI-SPD/iteration_02/05_results.md` with a 30-case
boundary/occupancy gallery. Commit and push the evidence and verify the push.

## Success criteria (from ON-002, scoped by the amendments)

- **BEM parity:** at contrasts meeting the physics target, B's recovery set
  contains G's. The median paired B/G total-time ratio on common successes is
  ≤ 1.25, and its 90th percentile is ≤ 2.
- **Hybrid:** H retains the union of the B and G recovery sets. It either adds
  two recoveries beyond B, or is ≥ 2x faster than the faster constituent on
  common successes.
- **Completed feasibility result**, if no comparison is possible: a qualified
  adapter with measured convergence orders, physics-target coverage per
  contrast and representation floors. A Stage 1 stop with the defect located
  is reported as incomplete, not negative.

## Decision table

| Observation | Action |
|---|---|
| A Stage 1 rung fails and the fix passes its test | Continue the ladder |
| Rungs 1–4 still failing at 120 min | Close `ADAPTER_INCOMPLETE` |
| 2a misses the target at a contrast | Continue; label it below physics target; no parity claims there |
| G fails at high contrast because inner solves do not converge | Apply the ON-002 inversion-phase repair once |
| G has low native residual but its contour fails the BEM audit | Apply the one grid escalation if unused; otherwise record it |
| B matches or exceeds G at ≤ 1.25x time | Run all 30 and close parity |
| G is ≥ 2x faster with comparable recovery, or recovers a B failure | Release H |

## Budget and stops

Eight hours overall, including Stage 0, implementation, queue waiting and
reporting. Stop opening new stages at hour six and keep the last 40 minutes for
closeout. Use the existing compute, source and Git locks. Run no concurrent
benchmark jobs. The pinned GauGal checkout (`3ec2627d`) stays read-only.

## Implementation map

| Area | Location |
|---|---|
| Preserved ON-002 record | Committed unchanged in Stage 0 |
| Adapter fixes and ladder tests | New `experiments/benchmark/gp001_adapter.py` and `test_gp001.py`. They may import ON-002 modules; they never edit them. |
| Campaign and report | New `experiments/benchmark/gp001.py` |
| Evidence | `results/validation/cleaned_interfaces/GP-001/` |
| Report | `docs/iterations/CI-SPD/iteration_02/05_results.md` |

The maintained BEM package never imports GauGal.
