# Codex review of the iteration-02 work, and its resolution

**Dated correction, 2026-09-22:** the later
[Codex review of `1a6a55a`](../../iteration_03/02_proposals/01_codex_review.md)
confirms the two optimizer fixes but supersedes this record's resolution
attribution and initial-circle argument. Upstream `nppw=30` is for data
generation, its inverse starts with 500 nodes, and our RMS stopping test differs
from its filtered coefficient norm. Residual decrease does not imply area-error
decrease; Figure 1's plotting convention remains unverified. The original
resolution narrative below is retained as the historical record.

Codex reviewed commit `8e5c152` on 2026-09-22 and left executable reproducers
rather than prose, in
[`results/validation/shape_continuation/review-20260922/`](../../../../../results/validation/shape_continuation/review-20260922/):
`checks.py` with its `checks.json` output, and `reference_sources.json` pinning
the twelve reference files it read with their SHA-256 digests.

This document states what those checks establish and resolves each material
finding. Reviewer: Codex. Resolving owner: Claude. The reproducers are Codex's
work and are preserved unmodified; `checks.py` no longer runs against current
source because finding 2 removed the mechanism it probed, which is the intended
outcome rather than a regression.

## Confirmations (no action)

| Check | Result |
|---|---|
| Gaussian filter against `update_inverse_iterate.m` lines 324-332 | 9 cases, max absolute difference **3.6e-15** |
| Cauchy step: raw formula versus our normalized form | relative difference **4.7e-16**, confirming the scale invariance claimed in the code comment |
| Saved SC-013 bundles | no source hash mismatches, 17 and 9 stages committed and qualified, every accepted update strictly decreasing, area rescored bitwise identical |

## Material findings

### 1. `steepest_descent_iterations` depended on how updates were chunked — **accepted**

Codex ran the same two updates as one chunk and as two one-update chunks. The
second update offered both directions in the first case and steepest descent
only in the second, because `optimise_step`'s `iteration` argument restarts at 1
for every `fit_prepared` call. Driving the optimizer one update at a time is the
documented way to use the adaptive controller, so the knob was inconsistent
exactly where the interface is meant to be used.

Fixed by deleting the counter. `FitConfig.directions` now names the proposals
the search may use — `("gauss_newton",)`, `("steepest_descent",)` or both,
matching the reference's `optim_type` values directly. It cannot depend on
chunking because there is no counter. The reference's `sd-min(gn,sd)` phase is
now expressed by a strategy issuing two decisions, which is where a
frequency-scoped policy belongs. Regression test:
`test_direction_policy_does_not_depend_on_how_updates_are_chunked`.

### 2. The joint filter search skipped a better Gauss-Newton candidate — **accepted**

On the first update of the contrast-10 ladder, our search accepted steepest
descent at filter level 0 with residual 0.1035. Codex finished the Gauss-Newton
sweep our early exit had skipped: invalid at level 0 (self-intersecting),
invalid at level 1 (arclength projection unresolved), and **decreasing at level
2 with residual 0.0960** — better than the step we took. The reference filters
each direction to admissibility on its own and only then compares survivors, so
`reference_order_would_choose: "gauss_newton"`.

This was a declared difference in the audit, described there as mattering "only
when the two need different filter strengths". Codex showed that case occurs on
the very first update of a production ladder, so the difference is not benign.

`optimise_step` now sweeps filter levels per direction and compares the
survivors. Regression test:
`test_each_direction_is_filtered_to_admissibility_independently`. This changes
accepted trajectories, so both SC-013 ladders are re-run; the previous bundles
are superseded rather than edited.

### 3. The Figure 1 area convention is unverified — **accepted, and strengthened**

Codex flagged that our "2.5x to 26x better than published" comparison assumes
Figure 1 plots the normalized `εΓ = δA/A`, recorded the sensitivity, and set
`figure1_plotting_convention_verified: false`.

Checking the reference repository settles the direction if not the answer:
**every driver computes `err = area(pdiff1) + area(pdiff2)`, the raw symmetric
difference, and nothing in the repository ever divides by the true area.** §4's
text nonetheless defines `εΓ = δA/A`, and the figure's axis is labelled `εΓ`.

One physical argument favours the raw reading. The true area is 2.6215, so a
published value of 0.781 at k=1 is `εΓ = 0.781` under the normalized reading —
**worse than the unit circle we start from**, which scores 0.361, after a stage
that runs to 100 iterations under an enforced residual decrease. Under the raw
reading the same point is 0.298, an improvement on the circle. Ratios against
our runs become roughly 0.9x-10x rather than 2.5x-26x, so at low k the two are
comparable rather than ours being far better.

This is now recorded as the more likely reading and still not proven; both are
reported side by side and neither is used to claim a match.

## Beyond the review: the transmission driver

`reference_sources.json` lists `tests/driver_charlie_transmission.m` and
`examples/data_generation_scripts/starn_transmission_tensor_data.m`, which the
earlier reading missed — it used the Dirichlet `ex1_plane.m`. The transmission
driver is the configuration that matches Figure 1's penetrable problem, and it
differs from §4's prose on every count that affects accuracy:

| Control | §4 prose (what we ran) | Transmission driver |
|---|---|---|
| Optimizer | GN and SD compared | `optim_type = 'sd'`, **steepest descent only** |
| Update band | `floor(3 max(k,ki))` | `use_lscaled_modes`: `floor(2 k L / 2π)`, no `ki` |
| Inverse points/wavelength | 70 | 30 |
| Update tolerance | `1e-5` | `eps_upd = 1e-3` |
| Iteration cap | 50 | `maxit = 100` |

At contrast 10, k=5 the two band rules give **47 modes against 10**. Both are
now selectable as `paper.py --profile {paper,driver}`, and the four-arm
comparison against the digitized Figure 1 is the measurement that follows.
Neither profile is presented as the recovered Figure 1 input.
