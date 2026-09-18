# Iteration 07 — calibration quality decides *where* a neighbour helps, not *whether*

Opened by **LAU-005 COMPLETE**, authorized by the user's 2026-09-18 instruction to try
the alternative in the Laurent report while compression is parked.
[Contract](../iteration_06/03_plan.md) ·
[Measured closeout](../../../../results/validation/laurent/LAU-005-20260918-closeout/README.md).

**The question the neighbour study left open is now answered, and the answer is not the
one its selected configuration suggested.** That study named *scattering-assisted
separation of shape and calibration* as its hypothesis and explicitly recorded that its
results left "the stronger claim of improved shape sensing with perfect calibration
unsupported". Making calibration uncertainty continuous — one Gaussian log-gain prior of
scale `tau` whose endpoints are that study's own known-gain and free-gain arms — settles
it: across all **189** configuration/prior cells of the recorded 63-point screen, coupling
already beats the additive control at **exact** calibration in **137**. Where no
calibration nuisance remains, the benefit cannot be nuisance ambiguity; it is illumination.

**70 cells do cross over**, and those carry the quantitative result: coupling pays only
once per-antenna gain error exceeds a median `tau*` of **0.132** (**0.172 dB**, **1.89
degrees**, one standard deviation). **15 cells never pay.** The configuration the neighbour
study analysed is in the crossing minority and crosses at **0.021 dB / 0.23 degrees** —
because it was *selected* to maximise the coupled-over-additive gain with gains free, which
is precisely the criterion that rewards the calibration mechanism. The second,
overall-information configuration never crosses.

**The reparameterisation is the recorded study, not a new quantity.** Endpoint
reproduction over all 189 cells and four arms: worst relative disagreement **1.5e-14**
free-gain and **0** known-gain. No swept curve is non-monotone beyond `1e-9` — a looser
calibration prior never adds information. The bridge arm, which keeps the study's improper
flat gain prior, reproduces **all five published medians exactly** (0.654 / 0.257 / 0.118 /
0.091 / 0.075 mm) on the five seeds per scene it ran.

**Matched nonlinear recovery follows the bound.** 600 fits, 2 shape pairs, 10 seeds, 2
starts, 5 arms, 5 calibration scales; 600/600 converged and the worst fresh 192-node
full-boundary check is **3.1e-14**. The seed-paired coupled-minus-additive difference is
indistinguishable from zero at `tau=0` (−0.0042 mm, 95% [−0.0090, +0.0008]) and
significant from `tau=0.1` upward (−0.0275 mm, 95% [−0.0450, −0.0105]), widening to
−0.1023 mm at `tau=1`. The Fisher ordering and the recovery ordering agree at every tested
`tau`, so the contract's "investigate further" branch is not triggered.

Knowing the calibration prior is itself worth 1.70x on the isolated target at `tau=1`,
against 1.06x on the coupled arm. Part of what an uncertain neighbour buys is calibration
information a prior can also supply — which is the same mechanism seen from the other side.

**Dependency drift is recorded, not hidden.** Two `solvers/` files the neighbour bundle
hash-pins changed earlier under the speed-up track's commit `25de4cd`; nothing here touched
them, every pinned experiment file is unchanged, and the bridge arm's exact reproduction of
the published medians is the evidence that the drift does not perturb the comparison.

**No production promotion, speed claim, Laurent-specific novelty claim or field-GPR claim.**
The compiled scattering path is used because it is the qualified tool for this scene; the
same sweep would run on a nodal forward. 13 new controls pass, including an independent
block-inversion check of the Schur elimination and an identity test against the neighbour
study's own objective. Compression tooling (LAU-001…LAU-004) is untouched and parked, not
closed; the priority review's reopening condition still stands.

**Cycle closed here.** The user accepted this result and closed the Laurent cycle on
2026-09-18. No successor is scheduled and no experiment ID follows LAU-005. The two
candidates below are recorded as open scientific options, not as planned work; the same
applies to the compression line parked by the iteration-06 review. Closed, not abandoned —
reopening either needs a fresh contract and a named ID under the standing approval rule.

**Directions left open.** Two candidates, both cheap and both discriminating:

1. **Why do 15 cells never pay?** They are the counterexamples that would sharpen a
   placement rule. A geometry-indexed explanation of the crossing/always/never partition
   would turn 189 measured cells into a predictive statement.
2. **Does the crossover survive a realistic calibration model?** The Gaussian log-gain
   prior is a modelling choice. Correlated, drifting or frequency-dependent gain errors are
   the obvious stress, and the same `tau` machinery takes them without new algebra.

Neither is authorized and neither is scheduled. The standing limits are unchanged: lossless homogeneous 2-D TMz,
one target and at most one neighbour, disjoint bounding circles, known component count,
locally constrained starts, no air/soil interface, antenna pattern, clutter or conductivity.
