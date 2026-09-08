# Long acquisition run: completion and terminal geometry gates

The command **completed successfully**, including both inverse arms and all
scheduled posthoc reporting: exit 0, `status: complete`, no posthoc errors, and
all recorded numerical qualification gates passed. **Neither inverse converged**.
Both serialized results have `converged: false` and stop reason
`no_decreasing_neural_step`, after trying all 15 Adam and 15 fallback scales at
the final accepted state. The 60-update, 1440-candidate, 3600-second per-arm caps
were not reached.

| Quantity | E0 paired-8 | E1 multistatic-8 |
|---|---:|---:|
| Accepted updates | 42 | 31 |
| Attempted candidates | 349 | 312 |
| Inverse seconds, excluding posthoc | 1371.21 | 1421.62 |
| Final training objective | 0.3250024 | 0.0758042 |
| Final fixed 3 GHz relative error | 0.721501 | 0.544476 |
| Final mean / maximum node-to-target error, mm | 12.558 / 36.811 | 6.880 / 22.195 |
| Final raw-contour gradient minimum / maximum | 0.17645 / 3.72102 | 0.49002 / 3.26719 |
| Final gradient spread / RMS | 21.0877 / 1.79477 | 6.66746 / 1.51957 |
| Final conversion distance, µm; limit 200 | 190.2728 | 199.9554 |
| Final refinement change, µm; limit 10 | 6.2584 | 2.3345 |
| Last accepted boundary movement, µm | 6.0189 | 1.9171 |

Training objectives use different acquisitions and observed-column scales;
their absolute values should not be compared as the same residual. The fixed
evaluation acquisition and target geometry measurements are shared comparisons.

## E0: terminal small-step obstruction is detected topology

Of 30 terminal candidates, 22 fail extraction/topology, four fail conversion
distance and refinement together, one fails conversion distance alone, and three
fail boundary motion plus both objective gates. The **smallest tested Adam and
fallback candidates** both fail because the independent raw-zero-set audit
detects **two components**. Their rejection is not an Armijo decision: those
candidates never reach the BEM/data evaluation.

The final accepted state itself passes the sampled single-component checks and
both conversion limits. Therefore do not describe it as already topologically
invalid. The records show extreme sensitivity of nearby proposals to the
independent audit; they do not distinguish a true continuum bifurcation from
resolution-sensitive detection of a small additional component.

Geometry first becomes the next-larger-step binding constraint at accepted
state 30. Late accepted motions include 136.55 µm into state 40, 5.315 µm into
state 41 (Adam backtrack 14), and 6.019 µm into state 42 (fallback backtrack 13).
This is not a monotone collapse throughout the run: a previous 11.44 µm step
into state 36 was followed by millimetre steps. The final collapse is real, and
the last three transitions are topology-limited at their next larger scale.

## E1: terminal small-step obstruction is conversion distance

Of 30 terminal candidates, **27 fail conversion distance**, only one of those
also failing refinement change. Three larger Adam candidates fail the motion
limit, with two also failing both objective tests. The smallest tested Adam
candidate gives **201.1934 µm** conversion error; the smallest fallback gives
**200.1447 µm**. Their refinement changes, **2.3366** and **2.3349 µm**, pass.
Thus the final stop is the fixed **distance** gate, not a recurrence of the
historical 10 µm refinement-change stop.

The final accepted distance, 199.9554 µm, leaves only **0.0446 µm** of headroom.
Accepted motions into states 26–31 shrink from 206.27 to 51.81, 25.88, 12.91,
3.833, and 1.917 µm. The next larger proposal at every one of those states fails
conversion distance. Five final updates fall below the existing 100 µm
meaningful-motion reporting threshold.

There remains a larger data-descending neural proposal: terminal Adam backtrack
2 reduces its own data objective from 0.0758042 to **0.0370982**, passes both
conversion limits, but moves the boundary **16.672 mm**, exceeding the unchanged
2 mm limit. This does not establish target-shape improvement for that rejected
candidate or authorize relaxing the trust region.

## Field deterioration and interpretation

The shared initial raw-contour gradient range is 0.81989–1.23021, spread 1.50045.
At state 5 it remains mild (spreads 1.6730 / 1.6537), but subsequently deteriorates
to 21.09 / 6.67. The contour Eikonal mean square reconstructed from saved
arc-weighted spectra grows from 0.00529 to **0.96071 / 0.47668**. The fixed box
penalty grows only to 0.11118 / 0.11528. All recorded contour gradient values are
unclipped; no accepted sampled gradient is exactly zero.

The saved terminal Adam and fallback proposals are descending for both the
data and regularized local gradients before geometric evaluation. Both searches
therefore exhausted their actual feasible-step tests at substantial nonzero
gradients, rather than satisfying a stationarity or data-tolerance criterion.
Final rejected searches restore the empty Adam moments left by the last
accepted fallback update.

These terminal gates explain **why each search stops**. They do not establish
why earlier updates produced the remaining wrong shape, or prove that field
conditioning alone causes it. The observed field drift and conversion failure
justify further frozen-state causal diagnosis; this read-only review did not
perform a repair, a refined extraction, or a new inverse. Micrometre accepted
steps should not be counted as recovery, and these records do not justify
relaxing tolerances or silently increasing backtracking depth.

## Reproduction and consistency

For **both arms**, states 0–5 have exactly equal saved weight tensors, parameter
vectors, converted geometry arrays, and shared numerical metrics compared with
the completed short acquisition comparison. The complete 33/35-trial short
prefixes also match exactly. State-5 gradient availability differs by design:
the short run was terminal there, while the long run continued.

`terminal_review.py` reproduces this existing-data analysis. `terminal_review.json`
contains source SHA-256 hashes, exact terminal counts, gradients, transitions,
and replay results. `terminal_candidates.json` preserves all 60 terminal trial
records with the more specific failure stage. `accepted_field_trajectory.csv`
contains every accepted state's field conditioning and conversion measurements.
No model, geometry extraction, gradient, BEM, or inverse evaluation was run.
