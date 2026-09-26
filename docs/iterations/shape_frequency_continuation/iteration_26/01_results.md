# Iteration 26 — prospective band decisions with charged diagnostics

2026-09-26. **SC-043 RUNNING.** The final six-case accounting is pending.
Owner: Codex; independent reviewer: unassigned. [Frozen contract and raw
evidence](../../../../results/validation/shape_continuation/SC-043-prospective-band/README.md).
The numerical implementation and policy thresholds remain frozen.

The atlas cannot pass the declared superiority gate: on the completed C
comparison its Hausdorff ratio against fixed escalation is 1.30456, above
the allowed 1.25. The absolute errors are small (0.03381 versus 0.02592 mm),
and both RMS values fall below the 0.01 mm comparison floor. This is a
failure of the predeclared criterion, not evidence that every atlas policy
is ineffective. All remaining paths continue to their own declared limits.

## What this comparison tests

Six saved development starts receive the same initial K64 cleanup and
subsequent K192 state evolution. All 19 frequencies are used throughout.
Three decisions per path select the current normal-update band M or M+6.
The fixed rule always releases; the stagnation rule uses the previous
stop and last accepted improvement; the atlas requires at least 10% of
current loss as additional optimal linearized decrease at the larger band.

Each block has 304 work units. An atlas diagnostic costs 76 units for
coarse/refined fields and full Jacobians, leaving 228 for fitting. Batch
and endpoint-reserve constraints can leave unused allowance. Actual work
therefore differs between methods, even though maximum allowances match.
The saved decisions precede fitting and truth scoring. No best-truth
iterate is selected. These are continuation suffixes on development shapes,
not full reconstructions or an adaptive-frequency experiment.

## Completed discriminating cases

Star: fixed and atlas both choose M31/37/43; stagnation chooses M31/37/37.
Their RMS errors are 0.011028, 0.011146 and 0.018149 mm, respectively.
The atlas improves over stagnation but does not beat fixed escalation in
RMS. Its Hausdorff estimate is lower than fixed (0.02552 versus 0.02929 mm).
All three endpoints qualify. Increasing capacity is useful on this case;
the result does not establish that a diagnostic is needed to select it.

C: fixed selects M25/31/37; stagnation M19/25/31; atlas M25/31/31.
The atlas's third predicted incremental fraction is about 9.87%, just
below the frozen threshold. Its final RMS/Hausdorff is 0.006222/0.033810 mm,
against 0.004093/0.025917 mm for fixed and 0.006280/0.033539 mm for
stagnation. The threshold is not retuned after this observation.
Doubling geometry sampling changes the atlas/fixed Hausdorff ratio from
1.30456 to 1.30417, retaining the same conclusion. This empirical refinement
check does not replace the original gate or certify exact Hausdorff distance.

Converged circle: all three geometries are identical (RMS 0.0002447 mm).
Fixed and stagnation use 114 fitting units each; the atlas uses 342
combined units, including 228 diagnostic units. Its three retained-band
decisions provide no geometric benefit. An earlier loss-based stopping
check or cached diagnostics could avoid some work in another method, but
neither receives a retroactive discount in this experiment.

## Interpretation that survives the unfinished paths

The diagnostic's mathematical qualification and its decision value are
different questions. A physical-metric constrained least-squares forecast
can be well defined without improving the complete inverse. Its prediction
concerns one optimal linearized step; a subsequent multi-step LM decrease
is not a direct calibration test of that forecast.

All fifteen non-kite forecasts have inactive physical-radius constraints;
their high-band minimizers use at most about 4.1% of the declared radius.
These decisions reduce to comparing unconstrained linearized fitting
capacity. They do not establish a benefit from an active physical-radius
cap. An early-stage controller could behave differently; this suffix study
does not evaluate that possibility.

Under the declared reciprocal-batch accounting, adding M columns does not
add a frequency batch. Keeping M low therefore does not itself save those
field evaluations. The diagnostic has to pay for itself through a better
trajectory or fewer wasted steps. This comparison tests that specific cost
model; uncontrolled shared-host timing is not a speed benchmark.

Feature interpretation also matters. The star's 5.1136 mm truth minimum
radius belongs to a concave valley, while its convex tips have radius
10.4167 mm. The current post-fit regularity report separates these features;
earlier language that called the minimum a tip radius has been clarified.
Improving a global curvature extremum does not prove every feature improves.

Final endpoint tables, complete costs, sampling refinement and evidence
checks will be added when all 18 paths have returned.
