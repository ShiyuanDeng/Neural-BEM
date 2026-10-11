# NG 003 reciprocal bootstrap and output coefficient error budget

2026-10-11. Registered after NG-002, before new numerical work. Specific
unanswered mechanism: are the remaining refusals caused by the prior speed
range proposer and a per-phase budget unrelated to the requested output?
This is a new component question after NG-001's one changed construction;
previous budgets/results remain frozen. No inverse or selector promotion.

## Derivation and assumptions

The [research derivation](../../reports/node_free_geometry_research_2026-10-11.md)
already separates scalar proposals from full reciprocal/phase residuals.
[Higham and Al-Mohy, section 6, (6.18)](https://eprints.maths.manchester.ac.uk/1406/1/covered/MIMS_ep2010_18.pdf)
supplies the multiplication-only inverse-root iteration. The following
bootstrap and projection bounds are adaptations for real scalar functions
of angle, not a cropped-matrix convergence theorem.

For real u and S=|p'|², r=||1−S u²||₁<1 implies S>0 and u has constant
nonzero sign. A positive mean of u selects the positive branch. Since
|u|<=||u||₁, S>=(1−r)/||u||₁²=a. Let q=C_B(S*u), with the entire discarded
mixed-product tail t=||S*u−q||₁. Then

q >= sqrt(a)*sqrt(1−r)−t = m_q.

Require m_q>0. With the full r_s=||q²−S||₁,
||q−sqrt(S)||_infinity<=r_s/(m_q+sqrt(a)). This bootstrap needs no angular
range anchors or sampled minimum. It certifies scalar regularity only; a
regular crossing can still satisfy it. Directed geometric proof stays separate.

Initialize inverse Newton with c=gamma*mean(S)>=2||S||₁, gamma a power of
two. Run at least eight iterations, at most 64, selecting the first iterate
meeting the unchanged full speed/reciprocal tolerance 1e-10 and positive
mixed margin. Refuse stagnation after at least 12 iterations and three
successive reductions smaller than 0.1 percent. Keep count and integer-scale
branches locally fixed in the actual forward derivative. Scalar exact
convergence does not guarantee success after crops.

For each output phase m, retain the full uniform estimate
E_m=|P_m(0)−1|+2pi||P_m'−im alpha_B' P_m||₁+m E_alpha.
The nonzero output coefficient sum is bounded by
2 nu(p) sum(E_m/m). Individual E_m need not satisfy an arbitrary identical
1e-8 threshold if the requested output accuracy is met. No residual mode is
discarded or ignored. For the centroid, set p_bar=p−p₀ and let e_s bound
speed error, q₀ its approximate mean:

E_0 <= ||p_bar||₁ e_s/(q₀−e_s) * (1+||q||₁/q₀).

This follows by subtracting the two normalized weighted means; centering
removes the irrelevant absolute translation. Require q₀>e_s. Charge E_0
and the nonzero sum together. Allocate at most half the production budget
1e-5*base mean speed to the base projection; require the moved projection
plus that base error to fit the same total budget. These bounds concern R
of the actual finite intermediate curve. They do not certify approximation
of an unspecified infinite normal move or rigorous floating arithmetic.
Construction receipts remain float64, marked arithmetic_verified=False.

## Frozen replay and acceptance

Reuse all 31 exact TG-002 states and 279 moves, their qualified independent
NG-001 references and hashes. First test original coarse/fine bands, then
double up to coarse B<=4096 and fine<=8192. Keep the 20-second per-move
boundary between attempts. Charge failures, preparation and both bands.
Both empirical reference gates and coarse/fine gate retain 1e-5 and 1e-7;
these cannot be replaced by the new theoretical receipt. Report fixed-band
and escalated results separately, all gains/regressions, and budget refusals.

Use all five complete-tangent diagnostics, three directions in each band,
independent 2N/4N quadrature and self differences at 1e-7/5e-8 m. Keep the
1e-3 gate and 1e-5 diagnostic. Repeat analytic base controls through B8192;
cusp and crossing must not be accepted by the unchanged directed verifier.
During every production-construction call, patch range_enclosure and all
FourierCurve sampling/fitting entry points to raise. This tests the stronger
coefficient-only bootstrap explicitly. Independent references are exempt.

This is construction-only; do not infer complete-trial validity or speed.
Existing NG-002 directed base proofs are retained as separate evidence.
Zero physics calls. Fresh source snapshots/hashes and failed-attempt evidence.
Validate, commit and push automatically. Stop after determining whether this
new criterion removes the measured artificial budgets; preserve any Fourier
tail or empirical-accuracy limitation instead of tuning it away.
