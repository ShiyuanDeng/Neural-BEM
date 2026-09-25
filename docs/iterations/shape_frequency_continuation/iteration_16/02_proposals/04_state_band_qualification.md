# SC-035 review: state restriction needs its own derivative and speed control

2026-09-25, Codex. Review under the autonomous instruction and the new
[high-level brief](../../../../atlas_geometry_high_level_next_steps.md).

RD-4's saved-state approximation measurements remain useful. Its universal
radius claim does not apply to a truncated arclength fit. For a degree-K
curve z(t), v=|z'(t)| and physical lengths in the same units,

`|curvature| <= ||z''||_inf / v_min^2 <= K v_max / v_min^2`,

so the guaranteed radius is `v_min^2/(K v_max)`. Only exact constant speed
reduces this to `L/(2 pi K)`. Sampling estimates of speed extrema do not by
themselves certify their continuous extrema. A K=1 ellipse already disproves
an unconditional degree-only curvature bound.

This matters numerically: the saved kite truth projected to K=8 has actual
minimum radius 3.58 mm, BELOW RD-4's nominal 4.57 mm bound. The corrected
sample-based bound is 1.78 mm, with speed ratio 1.72. Star K=8 has speed ratio
1.64 and a correction factor 0.44. Measurements and script:
[coordinate review](../../../../../results/validation/shape_continuation/SC-036-coordinate-review/results.json).
These are diagnostic fits, not executed inverse results.

[The authors' manuscript](https://arxiv.org/html/2210.11607v1), equations
(10)–(13), separately limits normal updates, stores the curve, and constrains
the candidate curve's curvature-energy tail. Equation (13) is neither a
pointwise curvature cap nor a clearance condition. It does not justify a
universal feature cutoff for these data. Theorem 2.1 supplies the normal
shape derivative, not a derivative through an intentional state projection.

A naive `P_K arclength(z+h n)` changes a general stored z even at h=0.
Differentiating only h n then compounds the inconsistency. The smallest
consistent pilot is a centred construction:

`T_z(a) = z + P_K[A(z + h(a) n) - A(z)]`.

Here A resamples by normalized arclength anchored at parameter zero; both
projections use the SAME resolved map. `T_z(0)=z`, every state retains band K,
and the derivative includes the complete arclength map and projection.
This is a NEW smoothing retraction, not merely a storage optimization and
not an exact projection onto a constant-speed manifold. Record speed ratio,
actual curvature and projection discrepancy; never claim a degree-only
curvature guarantee. A matched K=192 version isolates the low-band restriction
from the centring change. Its relation to the original normal hybrid is a
separate numerical qualification. Both arms retain the same backend.

The trial derivative can be assembled with central differences of this cheap
geometry map, then passed as normal velocities to the existing reciprocal
shape Jacobian. This requires NO finite-difference field solves in the inverse.
Qualify its full field derivative and step-size stability before fitting.
Do not silently reuse the old normal Jacobian. Keep conformal maps conditional:
there is no present representation result that warrants a new inverse chart.
