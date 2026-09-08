# Review of actual E0/E1 optimizer proposals

The saved proposals do **not** justify replacing Adam. Adam improves the measured geometric direction relative to total-gradient descent at every one of the ten tested frozen states. No Adam-state, projection, accepted-step or moment-rollback defect was found in these records.

This review reads `iteration-02-final/inverse-20260908T170732213677Z/{E0,E1}`. It constructs no neural model and runs no extraction, BEM, inverse or fresh perturbation. The reproducible array-only audit is [optimizer_review.py](optimizer_review.py), its detailed measurements and input SHA256 hashes are [optimizer_review.json](optimizer_review.json), and the ten-state comparison is [optimizer_review.csv](optimizer_review.csv). Runtime was approximately 0.15 seconds after imports.

## Exact implementation checks

- All five accepted updates in each arm use Adam. Fallback was available but never selected; no fallback reset occurred.
- Raw and bound-projected Adam proposals are exactly equal at all ten states. Bounds therefore introduce no direction distortion here.
- Accepted increments equal the logged backtrack factor times the Adam proposal to a maximum absolute difference of `5.56e-17`; saved accepted weights agree exactly with saved starting weights plus the accepted increment.
- Independently reconstructed Adam first and second moment recurrences match to `1.12e-16` and `1.74e-18`, respectively. The raw Adam update equation matches to `5.36e-17`.
- Saved moments after acceptance equal the moments after the single proposal exactly. The next iteration's starting moments and weights equal the preceding accepted state exactly. Step counters advance from 0 to 5 across five accepted updates, despite the rejected trials; rejected candidates do not add Adam steps.
- Nested optimizer trial records exactly match `trials.jsonl`. A single fixed Eikonal sample hash persists in both arms.

Global gradient clipping scales the gradient by `0.109–0.138` in E0 and `0.291–0.322` in E1. This scalar clipping does not rotate an individual gradient. Its effect on the history of Adam moments is real, but these records provide no evidence that it is harmful. The weighted Eikonal/data gradient-norm ratio is only `0.00126–0.00162` in E0 and `0.00336–0.00427` in E1. Data-only and total-gradient normal velocities have cosine at least `0.99999987`.

## Weight rotation is not harmful geometric distortion here

The cosine between negative total gradient and actual Adam is only `0.605–0.637` in E0 and `0.523–0.568` in E1 in weight space. Their predicted **normal motions** have much higher cosine: `0.942–0.964` and `0.961–0.965`, respectively. A low weight-space cosine alone is therefore a poor reason to blame Adam.

The following comparison rescales every direction to **20 µm predicted RMS raw normal motion**. Scores are signed inner products with the saved nearest-target correction, projected onto arc-length modes 0–20; positive means removing this geometric error. These scores are not radial Fourier-amplitude changes and do not establish target recovery.

| Arm / frozen state | Total-gradient score, 10⁻⁸ m² | Adam score, 10⁻⁸ m² | Saved finite raw-motion score, total / Adam, 10⁻⁸ m² |
|---|---:|---:|---:|
| E0 / 0 | 5.763 | 10.671 | 5.764 / 10.677 |
| E0 / 1 | 3.826 | 9.795 | 3.825 / 9.798 |
| E0 / 2 | 2.091 | 8.771 | 2.089 / 8.773 |
| E0 / 3 | 0.702 | 7.822 | 0.699 / 7.823 |
| E0 / 4 | **−1.285** | **6.166** | **−1.288 / 6.167** |
| E1 / 0 | 29.161 | 30.824 | 29.164 / 30.836 |
| E1 / 1 | 28.427 | 30.068 | 28.430 / 30.079 |
| E1 / 2 | 27.556 | 29.096 | 27.560 / 29.107 |
| E1 / 3 | 26.658 | 28.079 | 26.662 / 28.090 |
| E1 / 4 | 25.584 | 26.832 | 25.590 / 26.843 |

Adam has the better signed score in **all ten states**, in both the predicted and existing finite raw-motion measurements. It also gives a larger positive arc-length-mode-5 score at all ten states. The fallback is a positive scalar multiple of negative total gradient, and its common-scale normal motion is the same to roundoff. Selecting fallback would therefore not remedy the observed E0 state-4 geometric misalignment.

There is still adverse content: E0's summed modes 2–20 score becomes negative for total gradient by state 2 and for Adam by state 3. By state 4 it is `−1.99e-8` versus `−1.47e-8 m²`. Thus Adam's positive total score does not mean all shape components improve. E1's modes 2–20 score remains positive for both directions at all five frozen states. This supports examining the acquisition/physical metric mechanism while retaining Adam as the current control.

The existing 20 µm raw-motion probes agree with the IFT-predicted motion to RMS relative error `0.034–0.062%` in E0 and `0.029–0.075%` in E1. This supports the local ranking but is **one finite scale**, not an independently verified alpha-convergence window. No conclusion about late-state IFT validity follows.

## The denominator is a mild modifier in these early states

The cosine between `−N` and `−N/G` is `0.9962–0.9987`. At matched RMS their target-score signs agree throughout. In particular E0 state 4 already has a negative total-gradient numerator score (`−1.39e-8 m²`); division by G changes it to `−1.29e-8`, not its sign. Adam's corresponding numerator and velocity scores remain positive (`6.36e-8` and `6.17e-8`). The leading early E0 misalignment is already present in the neural numerator; it is not created solely by poor field-gradient magnitude.

On-contour gradient spread grows only from `1.50` to `1.67` in E0 and `1.65` in E1 over the six accepted states. This early-window observation does not displace the separate late-star conditioning evidence. Energy in modes 11–20 stays below 1% for the tested total-gradient and Adam normal motions; more high-mode energy in Adam is not accompanied by a worse signed correction here.

## What rejects the proposals

| Quantity | E0 | E1 |
|---|---:|---:|
| Accepted updates / attempted candidates | 5 / 33 | 5 / 35 |
| Rejected candidates | 28 | 30 |
| Motion-limit rejection counts | 28 | 24 |
| Topology / conversion-distance rejection counts | 0 / 0 | 4 / 2 |
| Data / regularized Armijo rejection counts | 1 / 1 | 0 / 0 |
| Binding reason for each next-larger rejected trial | motion, 5 / 5 | motion, 5 / 5 |
| Accepted Adam factors | 1/64, 1/64, 1/64, 1/32, 1/32 | 1/64 throughout |
| Accepted maximum converted motion | 1.05–1.96 mm | 1.28–1.42 mm |

Rejection counts can overlap: E0's Armijo failures occur on a candidate already failing the motion limit. Its 28 rejected candidates are therefore not 30 distinct failures.

The full raw Adam proposal predicts maximum normal motion of approximately `60–85 mm` in E0 and `82–92 mm` in E1 against a fixed `2 mm` limit. It is unsurprising that several halvings precede acceptance. The next-larger rejected trial moves `2.02–3.71 mm` in E0 and `2.53–2.87 mm` in E1. Accepted objective decreases are `93.6–98.2%` and `99.1–99.3%` of the saved adjoint linear predictions, respectively. At the accepted scales these records do not suggest a broken data derivative.

## Actionable decision

1. **Keep Adam for the current control.** Neither switching to Euclidean descent/fallback nor changing moments is justified by these records. There is no demonstrated optimizer bug to fix.
2. Interpret E0's adverse total-gradient geometry, and E1's better geometry, as evidence for the acquisition/metric diagnostic already in the plan. Retain the separate late-state field-conditioning tests; these five early updates cannot settle that mechanism.
3. A later runtime-only experiment could avoid repeatedly starting the line search at a clearly excessive proposal scale, for example by testing a starting backtrack index informed by the preceding accepted scale. Such a change still needs a bounded comparison with all existing geometry and Armijo gates intact; an IFT predictor alone is not a certificate that a skipped candidate would fail. Do not relax the 2 mm bound or infer long-run authorization from this suggestion.

The present evidence does not establish the late-star optimizer direction, a Method-B differential defect, or the outcome of a different optimizer. Those questions require their designated frozen or matched diagnostics rather than inference from five early accepted updates.
