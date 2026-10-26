# Overnight component studies, 2026-10-26: questions and answers

Three agents work in parallel overnight. Each answers one question from
[`directions.md`](../../directions.md) using saved TG-002 states, with no new
inverse fits. Each fills in **its own section below** before 07:00 on
2026-10-27, so this page is the morning report.

| Track | ID | Direction | Question in one line | Plan |
|---|---|---|---|---|
| A | FI-001 | D02 | Can a few exact frequencies predict the rest, cheaply enough to matter? | [plan](../frequency_interpolation/iteration_01/03_plan.md) |
| B | TA-001 | D08 | Are the four refusals near-cusps or near-touches, and does a positive-speed chart avoid them? | [plan](../geometry_charts/iteration_01/03_plan.md) |
| C | IS-001 | D04 | Where does solve time go now, and can an iterative solve beat LU at our sizes? | [plan](../linear_solves/iteration_01/03_plan.md) |

Chosen by the user on 2026-10-26 from the directions document. D01, D03, D05,
D07, D10 and D11 were crossed out; D06, D09, D12 and D13 stay as ideas but
were not chosen for tonight. D08's slider belongs to another agent.

## How each track connects to Haibing's review

[Haibing's literature review](../../../Haibing_directions.md) assessed the
proposed upgrades. Each track tests one of its claims with our numbers.

| Track | Haibing items | Claim the track tests |
|---|---|---|
| FI-001 | 2, 7, 9 | Frequency enters through scalar coefficients on shared geometry (item 2). A projected reduced model still needs the full matrix (item 7). |
| TA-001 | 3 and its prior-work list | The quantity behind every refusal is the `|W|` lower bound. The coefficient bound may often be inconclusive for non-convex shapes. |
| IS-001 | 5, recommendation 4 | Profile assembly against LU at the final size first. Anchored GMRES needs a contraction below one, which an LM step may break. |

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

**For Haibing items 2, 7, 9:** shared geometry remains useful, but smooth
scalar coefficients do not ensure a sufficiently low polynomial degree.
Skipping assembly/solves only helps after accuracy is established.

This does not test a projected reduced model or change recursive
linearization. Sampled neighboring field changes reach 1.86–1.87 for hook
and 1.58 for peanut; narrow resonances cannot be established from 19 samples.

**Limits:** one polynomial family, three saved curves, CPU timing only.
Shape and contrast differ together, so contrast causality is not isolated.
H3's actual final saved state is K136/Ku128, correcting the plan's K192.

**Evidence:** [results and interpretation](../frequency_interpolation/iteration_01/01_results.md),
[36-row table](../../../results/validation/cleaned_interfaces/FI-001/table.md),
[hook error plots](../../../results/validation/cleaned_interfaces/FI-001/fields_by_frequency.svg).

---

## Track B — TA-001: tangent-angle chart replay

**Status:** main replay complete; planned continuation being prepared.

**Answer:** Three of four chart trials pass physics and lower exact loss at
the original refused fraction. The exception, aphex c0.5, has a distant
near-touch. The failures are mixed, so positive speed alone is insufficient.

**Numbers:** Loss decreases: aphex c4 0.861%, aphex c13.3 11.245%, hook c13.3
1.462%. Original minimum speed / mean: 6.12e-8, 0.0443 and 0.1955. Aphex c0.5
has speed / mean 0.8242 but a distant gap of 0.481 mm. Maximum reconstruction
error is 3.03e-9 mm; maximum round-trip error is 6.48e-14 mm.

**For D08:** The finite map changes acceptance while keeping the same B6
derivative to first order. This justifies the four planned continuation fits.
It does not demonstrate recovery. The c0.5 near-touch needs another remedy.

**For Haibing item 3:** The simple coefficient bound is inconclusive on all
four accepted states, with lower bounds -3.186, -1.923, -6.073 and -6.187.
This confirms the review's warning for non-convex curves.

**Limits:** Torus minima are numerical estimates. Distant gaps exclude
parameter separation below pi/4. The chart retains log-speed density and
tangential gauge; positivity before cropping does not certify the stored
curve. One full step fails closure and one self-intersects. No main-study fits.

**Evidence:** [full results and figures](../../../results/validation/cleaned_interfaces/TA-001/README.md),
[iteration answer](../geometry_charts/iteration_01/01_results.md),
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

**For Haibing item 5 and recommendation 4:** cost profiling changes the
historical split, but lower iteration counts still lose at current sizes.
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

## Morning synthesis

Written in the morning, not by the overnight agents. IS-001's cost breakdown
bounds what FI-001 can save. TA-001's refusal types decide whether the next
geometry step is a chart or a self-touch barrier.
