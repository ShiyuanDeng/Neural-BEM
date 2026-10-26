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

**Status:** not started.

**Answer:** _pending_

**Numbers:** _pending_

**For D02:** _pending_

**For Haibing items 2, 7, 9:** _pending_

**Limits:** _pending_

**Evidence:** _pending_

---

## Track B — TA-001: tangent-angle chart replay

**Status:** not started.

**Answer:** _pending_

**Numbers:** _pending_

**For D08:** _pending_

**For Haibing item 3:** _pending_

**Limits:** _pending_

**Evidence:** _pending_

---

## Track C — IS-001: iterative solves against LU

**Status:** not started.

**Answer:** _pending_

**Numbers:** _pending_

**For D04:** _pending_

**For Haibing item 5 and recommendation 4:** _pending_

**Limits:** _pending_

**Evidence:** _pending_

---

## Morning synthesis

Written in the morning, not by the overnight agents. IS-001's cost breakdown
bounds what FI-001 can save. TA-001's refusal types decide whether the next
geometry step is a chart or a self-touch barrier.
