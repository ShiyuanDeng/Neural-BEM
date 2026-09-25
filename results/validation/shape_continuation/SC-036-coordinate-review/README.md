# SC-036 coordinate controls and SC-035 state-band qualification

Rebuild `results.json` with `run.py` (zero field solves), and `chain_rule.json`
with `chain_rule.py` (15 field/reciprocal units), under EMNerf,
`PYTHONPATH=solvers:.`, one BLAS thread. These are fixed-geometry diagnostics;
truth shapes never enter an optimizer. The six existing cases are development
controls, not held-out generalization tests.

The same seven-dimensional spaces coincide on the circle and differ away
from it. The least principal cosine is 0.973 on peanut, 0.772 on the five-lobe
star, and 0.400 on the kite. The normal space is harmonics 0..3 in normalized
arclength; the radial space contains exact x/y translation plus radial modes
0, 2 and 3, multiplied by their normal projection. Principal cosines use
L2(ds)-orthonormal columns, not raw coefficient norms.

A rigid translation's normal component is not generally low-band: M=3 captures
59.7% of either translation's normal energy on the star. C and hook have a
negative ray/normal cosine and are outside this radial chart. These facts
rule out a universal ranking of coordinate gauges.

For the **same physical motion**, weighted projection B into a resolved
normal basis produces `J_alternative = J_normal B` and physical metric
`W_alternative = B.T W_normal B`, to representation accuracy. At P=48, the
largest data-action errors are 1.22e-9 (peanut), 4.11e-6 (star), and 3.11e-11
(C translations/affine motions). At P=96 they fall to 2.44e-15, 8.35e-9 and
1.88e-15. The star's P=48 motion itself still has 0.9% relative approximation
error: agreement in weak data directions is not an exact motion representation.
No new information is created by this coordinate conversion.

The state-band fits also expose why RD-4's nominal curvature-radius bound
needs parametrization speeds. At K=8, kite's actual 3.58 mm radius is below
the nominal 4.57 mm claim; the speed-adjusted sampled lower bound is 1.78 mm.
See [the review](../../../../docs/iterations/shape_frequency_continuation/iteration_16/02_proposals/04_state_band_qualification.md).

Recommendation: retain the normal atlas as a physical local-information map,
with explicit bandwidth/metric qualification. Treat radial modes and exact
global motions as different admissible subspaces, not equivalent low-order
coordinates. The present evidence does not justify a wholesale chart change.
