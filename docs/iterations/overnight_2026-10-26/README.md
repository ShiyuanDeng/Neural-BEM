# Overnight component studies, 2026-10-26: questions and answers

**Complete:** three GPT-6.1 agents with high reasoning implemented the tracks
in parallel, followed by coordinator review and corrections. The user removed
the original time limit. Main studies used saved TG-002 states; the positive
chart replay triggered exactly four planned continuation fits.

The results support research decisions, but no production speed-up or new
recovery. See the [coordinator assessment](coordinator_review.md) for what
is answered, what remains uncertain, and what a supervisor can reasonably claim.

| Track | ID | Direction | Question in one line | Plan |
|---|---|---|---|---|
| A | FI-001 | D02 | Can a few exact frequencies predict the rest, cheaply enough to matter? | [plan](../frequency_interpolation/iteration_01/03_plan.md) |
| B | TA-001 | D08 | Are the four refusals near-cusps or near-touches, and does a positive-speed chart avoid them? | [plan](../geometry_charts/iteration_01/03_plan.md) |
| C | IS-001 | D04 | Where does solve time go now, and can an iterative solve beat LU at our sizes? | [plan](../linear_solves/iteration_01/03_plan.md) |

Chosen by the user on 2026-10-26 from the directions document. D01, D03, D05,
D07, D10 and D11 were crossed out; D06, D09, D12 and D13 stay as ideas but
were not chosen for tonight. D08's slider belongs to another agent.

## Status of Haibing's items after tonight

[Haibing's literature review](../../../Haibing_directions.md) assessed the
proposed upgrades. Tonight's tracks came from the directions document, not
from the items, so they test only item 5 and recommendation 4 directly.

**Closed** below means the evidence is strong enough that the proposer
would likely accept closing the item. Every other label leaves it open.

| Item | Label | Tonight's evidence, and what is still missing |
|---|---|---|
| 1 Maue form of T | Already in the solver | [A2](../../../solvers/bem_inverse/a2_muller.py) uses it. Not retested tonight. |
| 2 Müller cancellation, Ψ_j weights, bands | Partly in the solver; rest not tested | A2 already cancels the leading singularity and uses the exact log coefficients. FI-001 tested frequency interpolation (D02), not the Ψ_j closed form or bands. |
| 3 Coefficient step region | Checked, still open | The simple bound is negative on all four refusal starting curves, so it cannot certify any step from them. Missing: the sharper `|W|` bound already certified in [A1](../../../solvers/bem_inverse/a1_geometry.py), and steps along whole fits, not only refusals. |
| 4 Incremental Chebyshev update | Not tested | No evidence either way. |
| 5 Anchored GMRES, residual correction | Closed as a speed-up through Ku256; error-bound use still open | Even 3–4 iterations from an anchor 0.0005 mm away cost more than a fresh LU. One accepted 1.139 mm step has spectral radius 1.203, so the stationary error bound fails there. That is one step only. |
| 6 Schur elimination | Not tested | No evidence either way. |
| 7 Forward–adjoint reduced model | Not tested | FI-001 skipped held-out assembly; it built no reduced model. |
| 8 Error control for the LM step | Not tested | No evidence either way. |
| 9 Separate bands and frequencies | Not tested | No fit or continuation change was made. |
| 10 Circle closed forms | Not tested | No evidence either way. |
| 11 Riccati/ItI flow | Not tested | No evidence either way. |
| Recommendation 4: profile LU | Done | LU is 13–14% of cached Ku64 and 36–38% of cached Ku128 forward+Jacobian time at 2.5 GHz; 0.8–8.8% at first use. |

## Policy and saved states for all three tracks

The latest policy evidence is [PS-003](../policy_speed/iteration_03/01_results.md).
`compact_release` with GPU slider (H3) recovered hook in 16.3 s against
30.3 s, mostly through cheaper physics per iteration: K24/K32 and Ku 64 in
M11/M15. It lost circle recovery, so it is not a default.

Decisions for tonight:

- **No track runs a fit for its main question**, so the policy does not
  change tonight's run time. It decides which sizes matter.
- **FI-001 and IS-001 use H3's saved hook states** at Ku 64 and Ku 128. Those
  are the sizes where the fastest recovering trajectory spends its time.
- **TA-001 uses NR-001's saved failures.** The refusals belong to the
  default TG-002 pipeline.
- **Any continuation fit uses the default `CumulativePolicy`.** Its controls
  already exist for the four failures (NR-001), so no control reruns are
  needed. `compact_release` would require new controls and lost circle.

## Shared rules for the three agents

- Work in this `organised` checkout. Do not create a branch or worktree.
- No new inverse fit for the main question. Continuation work is listed in
  each plan and runs only if the user's updated `AGENTS.md` allows it.
- Pin each track to its own CPU cores with `taskset`; use single-thread BLAS.
  Keep each track below 6 GB; check `free -g` before large steps.
- Timing comparisons hold only within a track. Record machine load and GPU
  use with every timing table.
- Prototype code goes under `experiments/<track folder>/`. Move code into
  `solvers/bem_inverse/` only after success, and not tonight.
- Results go under `results/validation/cleaned_interfaces/<ID>/`.
- Stage only your own paths: never `git add -A`, never `git stash`. Before
  pushing, `git pull --rebase`. If this README conflicts, keep both sections.
- Do not edit `directions.md`, `GLOSSARY.md`, `AGENTS.md` or other tracks.
- Write your section's answer **before** starting any continuation work.
  Commit and push after each completed step, including failures.

Each section uses the same fields: answer, numbers, meaning for the
direction, meaning for Haibing's items, limits and evidence. Write numbers,
not adjectives. A negative answer is a full result.

---

## Track A — FI-001: frequency interpolation

**Status:** complete; all 36 planned curve/arm/node comparisons finished.
No inverse fits or extra frequency evaluations were run.

**Answer:** neither matrix nor solved-result polynomial interpolation passes
with 4, 6, 8, 10, 12 or 14 exact frequencies. A smallest passing node count
was not found. No accurate 25% saving is demonstrated.

**Numbers:** at 14 nodes, worst field / stacked-J errors are 2.345 / 4.431
(hook Ku64, matrix), 4.596 / 45.426 (hook Ku128, matrix), and 0.139 / 0.127
(peanut c4, matrix). Field/J limits are 1e-7 above 0.5 GHz / 1e-3.

The result arm's corresponding field / J errors are 3.147 / 1.387,
3.123 / 1.668 and 2.668 / 0.691. Exact CPU physics takes 1.047, 5.872
and 5.661 s; 14-node raw savings span 6.9–21.0%, below the 25% target.

Timings use cores 0–5 and single-thread BLAS; observed load was 0.06–1.27.
GPU snapshots were idle at 900–1606 MiB. CPU-only timings and omitted node
array packing make the raw savings an optimistic, non-CUDA comparison.

**For D02:** do not use this full-band polynomial to replace exact catalog
evaluations. All five held-out frequencies still fail at 14 nodes, including
peanut; the failure is not confined to a single high-contrast frequency.

**Haibing items 2, 7, 9 (not tested):** this track tests a D02 idea. It
builds no Ψ_j bands, no reduced model and no new continuation. It only
shows that scalar frequency coefficients are not smooth enough to interpolate.

Sampled neighboring field changes reach 1.86–1.87 for hook
and 1.58 for peanut; narrow resonances cannot be established from 19 samples.

**Limits:** one polynomial family, three saved curves, CPU timing only.
Shape and contrast differ together, so contrast causality is not isolated.
H3's actual final saved state is K136/Ku128, correcting the plan's K192.

**Evidence:** [results and interpretation](../frequency_interpolation/iteration_01/01_results.md),
[36-row table](../../../results/validation/cleaned_interfaces/FI-001/table.md),
[hook error plots](../../../results/validation/cleaned_interfaces/FI-001/fields_by_frequency.svg).

---

## Track B — TA-001: tangent-angle chart replay

**Status:** main replay and exactly four continuation fits complete.

**Answer:** Three of four chart trials pass physics and lower exact loss at
the original refused fraction. The exception, aphex c0.5, has a distant
near-touch. The failures are mixed, so positive speed alone is insufficient.
The four fresh default-policy chart fits recover 0/4, as in NR-001.

**Numbers:** Loss decreases: aphex c4 0.861%, aphex c13.3 11.245%, hook c13.3
1.462%. Original minimum speed / mean: 6.12e-8, 0.0443 and 0.1955. Aphex c0.5
has speed / mean 0.8242 but a distant gap of 0.481 mm. Maximum reconstruction
error is 3.03e-9 mm; maximum round-trip error is 6.48e-14 mm.

**For D08:** The finite map changes local acceptance with the same B6
derivative, but the full trajectories still fail. All four new failed
candidates have off-diagonal minima, speed / mean 0.231–0.726 and distant
gaps 0.118/0.245/1.127/6.799 mm. Keep the chart experimental.

**Haibing item 3 (checked, still open):** The simple coefficient bound is
inconclusive on all four accepted states, with lower bounds -3.186, -1.923,
-6.073 and -6.187. This confirms the review's warning for non-convex curves.
It does not test the sharper A1 bound or steps along whole fits.

**Limits:** Torus minima are numerical estimates. Distant gaps exclude
parameter separation below pi/4. The chart retains log-speed density and
tangential gauge; positivity before cropping does not certify the stored
curve. One full step fails closure and one self-intersects. No fits for replay.
Continuation RMS errors are 7.874/5.940/5.975/6.193 mm. Hook improves RMS
but fails the final field/full-trial check; no quality claim follows from
its later stopping stage. No extra fits or maintained-solver changes.

**Evidence:** [full results and figures](../../../results/validation/cleaned_interfaces/TA-001/README.md),
[iteration answer](../geometry_charts/iteration_01/01_results.md),
[continuation answer](../geometry_charts/iteration_02/01_results.md),
[prototype](../../../experiments/geometry_charts/replay.py).

---

## Track C — IS-001: iterative solves against LU

**Status:** complete. No inverse fits or production changes.

**Answer:** retain LU at Ku64/128. At matched field accuracy, cold and
anchored global/full-block GMRES both cost more than LU. The first measured
solve-only win is Ku512, outside the replayed working sizes.

**Numbers:** all 48 RHS, real/damped 2.5 GHz. LU costs 2.73/2.74 ms at Ku64 and
14.57/14.45 ms at Ku128; anchored global costs 10.37/8.65 and 35.17/29.26 ms;
full block 25.01/25.46 and 49.61/49.50 ms. Successful field errors ≤ 5.20e-12.

Cached forward+Jacobian duration is 12.07/12.60 ms at Ku64 and 30.80/31.24 ms
at Ku128. LU factorization takes 13–14%/36–38%; with both trace solves,
21–22%/47–49%. First-use forward calls cost 64–296 ms, including preparation.

At Ku512, 2050 unknowns: LU 618 ms; fastest anchored method 455 ms real/block
or 436 ms damped/global, excluding 570 ms anchor setup. Repayment needs four
hypothetical equal-cost targets; only one target per anchor was measured.

**For D04:** close the current-workload speed claim for these dense
implementations. There is no win through Ku256. A matrix-free action or
actual repeated large targets would require separate evidence.

**Haibing item 5 (closed as a speed-up through Ku256) and recommendation 4
(done):** cost profiling changes the historical split, but lower iteration
counts still lose at current sizes.
A 1.139 mm accepted stress step gives right-residual operator norm 274.18 and
spectral radius 1.203 at real frequency, breaking stationary contraction.
GMRES still converges, at 56.2 ms versus LU 2.62 ms; contraction below one is
sufficient for stationary correction, not necessary for GMRES convergence.

**Limits:** one hook state pair per working size, contrast 13.3, highest
real/damped frequency; dense assembled matrices. First-use timings have
one observation each. Cached 2.5 GHz shares are not full-catalog or fit timings.
Cold global real-frequency failures and unbalanced-RHS accuracy failure
are retained. The stress step was accepted, not refused or halved.

**Evidence:** [results](../linear_solves/iteration_01/01_results.md),
[execution notes](../linear_solves/iteration_01/04_execution.md),
[structured summary](../../../results/validation/cleaned_interfaces/IS-001/summary.json),
[solver table](../../../results/validation/cleaned_interfaces/IS-001/solver_table.csv),
[crossover plot](../../../results/validation/cleaned_interfaces/IS-001/crossover_real.svg).

---

## Coordinator synthesis

**Keep exact frequency evaluation and LU. Keep the chart experimental.**

- FI-001 rejects the tested full-band polynomial: 0/36 settings pass.
  It does not reject other approximation families or identify a causal
  high-contrast effect.
- IS-001 shows why fewer linear iterations do not automatically save time.
  Both tested iterative implementations lose at Ku64/128. The Ku512 crossover
  needs four hypothetical equal-cost reuses to repay the fastest anchor.
- TA-001 corrects the blanket near-touch explanation and proves a local
  finite-map benefit in 3/4 refusals. Four fresh fits still recover 0/4.
  Hook improves RMS but uses 2,152 versus 695 work units and fails its final check.

IS-001 bounds an ideal solve-only saving at about 21–22% of cached Ku64
and 47–49% of cached Ku128 forward-plus-Jacobian work at 2.5 GHz. These are
not whole-fit bounds. FI-001 also skips assembly or waves, but every tested
approximation fails accuracy. Its CPU timings cannot be combined directly
with IS-001's CUDA/CPU profile to claim production speed-up.

Positive speed addresses one local pathology; the new failed chart trials
still have nonlocal divided-difference minima. A separation barrier and
investigation of hook's high-frequency geometry are future proposals,
not demonstrated remedies. No further fit was run to seek a favorable result.

**Supervisor assessment:** satisfactory evidence for focused research progress,
not yet a solver breakthrough. The contribution is quantified rejection of
two current acceleration choices, a corrected failure mechanism, and a clear
limit on chart-only improvements. The [full review](coordinator_review.md)
records the implementation checks, iterations and unresolved questions.
