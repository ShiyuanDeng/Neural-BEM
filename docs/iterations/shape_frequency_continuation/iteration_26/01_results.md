# Iteration 26 — prospective band decisions with charged diagnostics

2026-09-26. **SC-043 COMPLETE: 18/18 paths, all 18 endpoint audits pass.**
Owner: Codex; independent reviewer: unassigned. [Frozen contract and raw
evidence](../../../../results/validation/shape_continuation/SC-043-prospective-band/README.md).
No numerical production code, policy threshold or default changed during
this comparison. All 248 saved-evidence checks pass.

**Reject this atlas rule as a superior controller under the frozen cost
model.** Its geometric-mean RMS ratio is **1.11301 against fixed escalation**
and **1.00512 against stagnation**, versus the required <=0.8 against both.
Worst floored geometry ratios are 1.88097 and 1.67889. The decisive kite
failure is geometric, with qualified fields and derivatives; it is not an
operational timeout. This rejects the tested rule, not every possible atlas.

## Comparison and complete costs

Six saved development starts receive the same initial K64 cleanup and
subsequent K192 evolution. All 19 frequencies are used throughout. Three
blocks choose current M or M+6: fixed always releases, stagnation uses the
prior stop and last accepted improvement, and atlas requires an additional
10% of current loss in optimal predicted decrease at the higher band.

Each block allows 304 work units. An atlas diagnostic costs 76 for
coarse/refined fields and full Jacobians, leaving 228 for fitting. Batch
and endpoint-reserve constraints can leave unused allowance. Decisions
are saved before fitting and truth scoring. Last returned states are
reported; no best-truth iterate is selected. These are development suffixes,
not full reconstructions or an adaptive-frequency experiment.

RMS in mm. Work is fitting plus diagnostics, excluding the identical
114-unit endpoint audit per path. The comparison uses 0.01 mm floors.

| Case | Fixed RMS | Stagnation RMS | Atlas RMS | Work: fixed / stagnation / atlas |
|---|---:|---:|---:|---|
| Star | 0.011028 | 0.018149 | 0.011146 | 741 / 741 / 703 |
| Kite | 0.034606 | 0.038771 | 0.065093 | 798 / 817 / 817 |
| Circle | 0.000245 | 0.000245 | 0.000245 | 114 / 114 / 342 |
| C | 0.004093 | 0.006280 | 0.006222 | 779 / 532 / 684 |
| Peanut | 0.002428 | 0.003457 | 0.002543 | 418 / 646 / 646 |
| Hook | 0.002053 | 0.002254 | 0.002715 | 646 / 570 / 684 |

Total fitting/diagnostic work is **3,496 / 3,420 / 3,876** for fixed,
stagnation and atlas. Atlas includes **1,368 diagnostic units**. Audits add
684 per policy, giving **12,844 units** for the study. Atlas uses 10.9% more
fitting/diagnostic work than fixed and 13.3% more than stagnation.

Supplementary common-work RMS ratios are **1.11425 versus fixed** and
**1.00933 versus stagnation**. These select the last accepted checkpoint
within the smaller actual path cost, including diagnostic charges. Those
checkpoints retain fitting acceptance but receive no new endpoint audit.
They do not replace the frozen terminal-state gate. See [all tables and
receipts](../../../../results/validation/shape_continuation/SC-043-prospective-band/TABLES.md)
and the [complete geometry/work figure](../../../../results/validation/shape_continuation/SC-043-prospective-band/geometry_by_work.pdf).

## What the cases establish

**Kite is the decisive failure.** Atlas keeps M22/M22/M22, while stagnation
uses M22/M22/M28 and fixed M28/M34/M40. Atlas RMS is 88.1% worse than fixed
and 67.9% worse than stagnation; Hausdorff is 0.213832 mm versus
0.170575/0.154320 mm. Atlas and stagnation spend exactly the same 817 units;
fixed spends 798. This failure is not explained by unequal actual work.

The three atlas release increments are 5.0655%, 7.7456% and 3.5068%, all
below the frozen 10% threshold. At the first state, low/high models predict
94.93%/99.998% reduction, with physical norms 0.2358/0.06532 mm inside the
inactive 0.9350 mm cap. Field and full-Jacobian discrepancies are only
4.50e-15 and 2.39e-14. The diagnostic is numerically qualified but does not
choose the wider space that helps the completed inverse.

The first atlas block reaches exactly the same state as stagnation's first
block at the same total cost: diagnostic work displaces later rejected
trials. Thus overhead is not a one-for-one loss of progress. The full
comparison nevertheless fails after both decisions and costs are included.

**Star supports capacity release, not a need for this diagnostic.** Fixed
and atlas both choose M31/37/43; stagnation stops releasing at M37. Atlas
improves RMS about 39% over stagnation, but fixed has slightly lower RMS.
Atlas has the lower Hausdorff estimate: 0.02552 versus fixed 0.02929 mm.

**C also violates the fixed-control guard.** Atlas retains M31 on its final
9.87% forecast, whereas fixed releases M37. Hausdorff is 0.03381 versus
0.02592 mm, ratio 1.30456 above the permitted 1.25. Both RMS values are
below the comparison floor. Doubled geometry sampling changes that ratio
to 1.30417; this is an empirical refinement check, not an exact-distance
certificate or a replacement gate.

**Circle, peanut and hook are below the RMS floor.** Peanut and hook also
finish below the Hausdorff floor. The converged circle is identical under
all policies, but atlas spends 342 rather than 114 units. An earlier
loss-based exit or cache reuse could save work in another implementation;
no retroactive discount is applied here.

## The remaining finite-step and geometry limitations

All 18 forecasts have inactive radius constraints in both low/high spaces:
**0 of 36 solutions activate the cap**. The largest norm uses 36.0% of the
radius; no high-band solution exceeds 7.7%. This study therefore compares
unconstrained linearized fitting capacity and does not demonstrate a
benefit from an active physical-radius constraint. An early-stage controller
could behave differently; that is outside this suffix test.

The optimizer uses damping and backtracking. At the initial kite state its
first damped candidates predict 86.18%/99.15% reductions at M22/M28, while
actual accepted decreases are 48.49%/49.34%. Replacing the forecast with
this damped model would change the threshold decision, but these post-fit
observations do not validate a replacement policy.

Fixed's final M40 block has a stronger finite-step obstruction: its first
trial predicts 98.2% reduction but increases production-grid loss about
209-fold. Backtracking to 1/16 produces the sole accepted step. The block
spends 285 units for 5.54% improvement, with eight nondecreasing and one
interrupted trial. The rejected full step was not refined on the finer
grid; this is a saved fitting observation, not an independently qualified
finite-step probe. A multi-step LM decrease is also not a calibration
measurement of a single optimal linearized forecast.

Cleanup does not remove all curvature artifacts. Fixed's minimum radius
is 1.125 mm on a flank where nearby truth has radius 20.37 mm. Atlas's
minimum is 1.091 mm nearby, while its true-tip neighborhoods have radii
3.318/3.506 mm versus truth 2.138 mm. Intrinsic curvature energy above
order 64 remains about 29–31% across the policies, versus truth 0.250%.
A smaller tail alone does not rank reconstruction accuracy. These are
[post-fit feature measurements](../../../../results/validation/shape_continuation/SC-043-prospective-band/regularity.json),
not policy inputs or new gates.

The star also required a wording correction: its 5.1136 mm truth minimum
radius occurs at a concave valley, while its convex-tip radius is
10.4167 mm. Earlier text used the global minimum as evidence of blunt
tips. Current reports separate the matched features; original numerical
measurements remain unchanged.

## Qualification and campaign closure

Every SC-043 endpoint passes N/2N fields, every active Jacobian column and
a full-construction directional finite difference. All diagnostic
qualifications pass. The 248 checks cover budgets, decision receipts,
prior stagnation flags, monotone accepted losses, final-state identity,
audit accounting and identical initial fit prefixes when policies choose
the same band. All frozen source/input manifests remain unchanged.

Across all 60 comparison paths, doubled metric sampling changes RMS by at
most 5.30e-6 mm and Hausdorff estimates by at most 1.65e-4 mm. Conservative
Hausdorff bounds remain separately reported; sampling agreement is not a
formal distance certificate. The original scores and gates are retained.

The entire SC-042/043/044 campaign is complete: **60 paths plus six shared
fresh-case prefixes**, with **49,120 recorded unique work units**. SC-045's
lost first audit ledger contributes up to **130 unrecorded units**. All
60 returned endpoints now have passing original or separately recorded
numerical qualifications. Two fitting numerical stops, five original
audit timeouts and the lost-result execution failure remain in the records;
follow-ups do not rewrite original strategy gates. [Complete accounting](../../../../results/validation/shape_continuation/STRATEGY_CAMPAIGN.md).

## Reviewer decision and further iteration

SC-042 supports a practical repair: one-off cleanup removes much of a known
kite artifact, with no meaningful extra geometry benefit from recurrent
cleanup or a permanent cap on those starts. SC-044 transfers stabilization
to one noisy C trajectory; most other RMS comparisons tie. Those results
justify simple regularization baselines. They do not establish a new
filtering principle or a general robust method.

The atlas rule has not earned its claimed decision value. There is a
structural reason to demand more: nested high-band spaces cannot have
lower optimal predicted decrease at the same radius, and more columns add
no frequency-batch cost under this accounting. A reason to retain a lower
band must come from finite-step behavior, regularity, noise stability or
another measured cost. The current rule does not model those tradeoffs.
This does not imply that the nonlinear inverse always favors the largest M.

For the next meaningful iteration, retain a simple fixed-band-release and
state-cleanup baseline. Separate explicitly charged quadrature adaptation
from geometry regularization at unchanged accuracy gates, and include the
closest published filtering and intrinsic-curvature controls. Protect sharp
features through development feasibility checks before releasing new shapes
and noise. Iteration 06 already found a constraint excluding the exact star;
SC-031/032 already tested curvature-weighted steps. A resulting-state
constraint needs its own isolated question.

A revised diagnostic should predict the improvement the solver can actually
accept for a given total cost, potentially using already-paid trial
information. That is a new hypothesis requiring prospective validation,
not a reason to tune the 10% threshold on these outcomes. Full reconstructions
on untouched shapes/noise and controlled model mismatch are still needed.
An adaptive-frequency claim also needs an actual frequency decision and
comparison with the earlier SC-017 result; this campaign uses all frequencies.

For publication, the supported scope is a qualified mechanism and strategy
assessment. Superior atlas-driven continuation, an observability limit, and
novelty of filtering or constrained least squares remain unsupported. See
the [primary-source claim review](../iteration_24/02_claims_review.md).
