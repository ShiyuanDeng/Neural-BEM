# Iteration 10 — consolidated atlas, independent interpretation

2026-09-24. Owner: Codex. This cycle opens from Claude's SC-026 dataset and
first analysis, pushed as `1e16e91` and `9b8918c`. The user requested a delay
while Claude finished, followed by analysis, proposed strategies, executed
tests and documented results, with commit/push after every milestone. The
extra hour ended at 03:04 UTC; local HEAD and the remote agreed and the
working tree was clean before this follow-up began.

## Evidence and its limits

The [dataset](../../../../results/validation/shape_continuation/SC-026-atlas-dataset/README.md)
contains 1,286 unique curves, 2,066 recorded states and 24,434 frequency/state
cells from 49 trajectories. All six cases are development data, including
the former held-out kite, peanut and hook. These are accepted states from
particular policies; this is not a sample of every possible boundary.

The [independent audit](../../../../results/validation/shape_continuation/SC-026-independent-audit/audit.json)
checks every binary artifact and input hash, reconstructs the state index
from the original histories, checks cell dimensions/finiteness and loss
algebra, and recomputes the SC-022 G and g comparisons. It also deduplicates
identical transitions before summarizing roughening. Run it with the
[audit script](../../../../results/validation/shape_continuation/SC-026-independent-audit/audit.py).

**Audit outcome:** all 12 binary hashes and all 12 source-input hashes
match. Recomputed G/g relative discrepancies are <=4.5e-16. The 1,875
step occurrences reduce to 1,280 distinct transitions; 24, rather than 39,
meet the original pathological-sharpening definition, all in stage 1.
They split as circle 6, star 0, C 13, kite 0, peanut 4, hook 1. This event
definition therefore misses some known difficult cases; it is not a
complete failure detector. Mean next-frequency gradient agreement across
the six case-level fractions is 98.0%.

**The normal-ray layer is incomplete for many curves:** 967/1,286 states
have coverage below 99%; the minimum is 50.7% on the kite. The first
analysis's projected-error shares were not filtered for this limitation.
They remain exploratory, not quantitative certificates of invisible error.

Claude's [first analysis](../../../../results/validation/shape_continuation/SC-026-atlas-dataset/ANALYSIS.md)
provides useful hypotheses, with these qualifications:

| Observation | Interpretation and limitation |
|---|---|
| The per-column sensitivity frontier grows roughly with k | Supports keeping the ladder as a baseline. A column that changes the data is not necessarily distinguishable jointly from other columns. The highest sensitive harmonic is not a proven recoverable band. |
| Most stage/next-frequency gradients agree | Supports testing extension. Gradient agreement in the mass metric does not prove that an LM step transfers, that a finite step is useful, or that higher frequencies remove a local minimum. |
| The remaining error projects into more sensitive directions at higher frequencies | A local, truth-assisted diagnostic under an assumed noise scale. It does not establish that 1.25 GHz is the sole binding accuracy limit. The cumulative analysis uses all catalog frequencies from 0.25 GHz, whereas the inverse used four frequencies starting at 0.5 GHz. |
| All 39 recorded pathological-sharpening occurrences are in stage 1 | A reason to intervene early. The event definition uses truth curvature and cannot become an online gate. Repeated trajectories inflate the occurrence count; use the audit's distinct-transition counts and case breakdown. |
| Weakly sensed steps tend to do little | Association may reflect convergence and small steps. It does not by itself qualify a spectral cutoff or demonstrate saved work. |

The threshold called 0.1% noise in `analyze.py` is actually a standard
deviation of 0.001 per **real normalized component**, compared through the
total noise norm `0.001 sqrt(48 F)`. It is not a measured noise level or
0.1% of each channel's own amplitude. Neither its threshold nor its error
projection is used by the proposed controller. The audit also records
normal-ray coverage and misalignment; actual finite-boundary distances
will decide the tests.

## Decision

Keep the dataset and the ladder baseline. Test two cheap, distinct
interventions: M=2 in stage 1, and a continuation to 2.5 GHz. Include a
control that spends additional work and opens the same bands using only
the original data. The [proposal](02_proposals/01_atlas_strategies.md)
compares the alternatives; [SC-028's frozen plan](03_plan.md) sets the
tests. SC-027 remains the separate, unexecuted Sobolev-metric proposal.

This cycle's empirical conclusions apply to the six noiseless development
cases at one material contrast and one start each. They will not justify a
generalization or noisy-data claim.
