# Iteration 25 — fresh full reconstructions and measurement noise

2026-09-26. **SC-044 COMPLETE: six common prefixes and 18 suffix paths.**
Owner: Codex; independent reviewer: unassigned. Numerical production code and
defaults remain unchanged. [Contract and raw evidence](../../../../results/validation/shape_continuation/SC-044-noisy-fresh-cases/README.md).

Stage-boundary cleanup and a permanent state cap transfer a useful
stabilization effect to one of the noisy C trajectories. They do not give
a broad RMS advantage on the other datasets. Local artifact suppression is
more apparent in Hausdorff and curvature measurements than in average error.

Two shapes were fixed before data generation: asymmetric lobes and a deeper
C-shaped domain. Each receives clean data and two fixed 1% complex-RMS
Gaussian noise draws. Every path starts from a circle and uses the same
four-stage prefix, then M11/19/31 with all 19 frequencies. No truth selects
the stopping point or treatment. A shared prefix is computed once and charged
to every complete path. At the prefix's K20 state, an initial K64 cleanup
would do nothing; this is a test of recurrent treatment, not repair of the
saved kite used in SC-042.

## Final geometry and work

RMS in mm. Complete-path work includes the shared prefix, excludes endpoint
audits, and follows the declared field/reciprocal-batch unit convention.

| Target/data | None | Each-stage cleanup | K64 cap | Complete-path work |
|---|---:|---:|---:|---|
| Lobes, clean | 0.010827 | 0.010827 | 0.010827 | 863 each |
| Lobes, noise 0 | 0.067808 | 0.067808 | 0.067808 | 451 each |
| Lobes, noise 1 | 0.113378 | 0.113378 | 0.113378 | 384 each |
| Deep C, clean | 0.073616 | 0.073270 | 0.073293 | 1,343 each |
| Deep C, noise 0 | 0.353514, numerical stop | 0.158045 | 0.157676 | 829 none; 905 each treatment |
| Deep C, noise 1 | 0.107694 | 0.107272 | 0.106986 | 898 each |

The noise-0 unchanged C proposes a loss-decreasing M19 trial but its maximum
field refinement discrepancy is 1.0857e-7 against the frozen 1e-7 gate. The
saved last accepted state passes its audit. Cleanup and the cap avoid the
obstruction and reach the declared noise discrepancy. The second noise draw
does not cause that fitting failure in any arm.

At a common 380-unit suffix allowance (829 with the prefix), cleanup's last
accepted state has RMS 0.2010 versus 0.3535 mm and Hausdorff 0.5816 versus
1.6091 mm: about 43% and 64% improvements. Its final RMS improves further
with another 76 units. These common-work states are selected by work only;
they retain fitting acceptance checks but have no additional endpoint audit.

Across the six datasets, terminal geometric-mean RMS ratios are **0.87318**
for cleanup and **0.87250** for the cap; common-work ratios are **0.90889** and
**0.90839**. Worst floored geometry ratios are 1.000004 and 1.000059. These
small excesses on effectively tied lobed paths are not meaningful harm.
Most aggregate gain comes from the one avoided noisy-C stop. There is no
evidence here for a materially better RMS choice between cleanup and cap.

## Local features and the remaining geometric limitation

On the clean C, Hausdorff estimates improve from 0.4820 mm without treatment
to 0.3846 with cleanup and 0.3877 with the cap. On noise draw 1 the values
are 0.7030, 0.6263 and 0.5765 mm. Average RMS changes by less than 1% on both
datasets. The [feature figure](../../../../results/validation/shape_continuation/SC-044-noisy-fresh-cases/cavity_feature.pdf)
shows an oscillatory artifact near the mouth's outer curve, which the global
outline plot largely conceals.

Cleanup does not recover exact curvature. The clean unfiltered endpoint's
minimum radius is 0.835 mm; cleanup/cap give 2.268/2.208 mm, while the truth
minimum is 9.645 mm. The [regional error and intrinsic-spectrum diagnostics](../../../../results/validation/shape_continuation/strategy_feature_errors.json)
are explicitly post-fit, descriptive measurements. They never change the
frozen selection gates. In particular, the clean cavity-wall RMS is roughly
0.094 mm without treatment and 0.095 mm with cleanup: improved global worst
error should not be relabeled improved cavity-wall recovery in every metric.

## Qualification, cost and interpretation

All 107 saved-evidence checks pass. Every common prefix qualified. Sixteen
original suffix audits pass; lobed-clean/cap and lobed-noise-0/cleanup time
out during host memory pressure. Both later pass unchanged serial SC-045
audits. Their original false flags remain, so **the original transfer gates
do not pass**. Separate passing qualifications supply numerical evidence
without retroactively changing the original campaign's operational outcome.

Unique work: 1,766 prefix fitting +9,158 suffix fitting +2,169 original
prefix/suffix audit +76 data-generation units = **13,169 units**. Additional
SC-045/046 costs and the lost SC-045 ledger are recorded in the
[campaign accounting](../../../../results/validation/shape_continuation/STRATEGY_CAMPAIGN.md).
Shared-host elapsed time is not a controlled speed comparison.

The two noise draws have realized truth residuals 1.0584 and 1.0388 times
expected noise loss, within the 1.21-times-expected discrepancy threshold.
This is a post-fit observation check; the truth residual never selects the
stop. The same standardized draws are paired across shapes and methods, so
these are **two distinct shapes with repeated measurements**, not six
independent target shapes. Data and inverse share the physical model;
material, calibration and experimental mismatch are untested.

The result favors retaining a simple stabilization baseline, noise-aware
stopping and explicit local-feature evaluation. It does not establish a new
filtering principle or a general robust continuation method. The completed
[SC-043 study](../iteration_26/01_results.md) rejects its frozen prospective
diagnostic rule as superior to both cheap controls; see the
[reviewer constraints](../iteration_24/02_claims_review.md) and
[conditions for further iteration](../iteration_24/03_next_decisions.md).
