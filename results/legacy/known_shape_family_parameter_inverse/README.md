# Legacy inverse controls with known shape families

**These are not full-MLP inverse runs.** The circle, ellipse and star controls
use analytic shape formulas expressed as implicit fields. The random-feature
case learns four output weights on frozen hidden features plus center/radius.
All use parameter finite differences and damped Gauss–Newton through extraction,
Method B and both MOD/Kress forward solvers.

The shape family is supplied in advance. In particular, the star uses the
target's fixed five-lobe family. Its center, size, amplitude and rotation are
unknown and recovered from observations; the true numerical shape parameters
are not handed to the optimizer. This strong prior makes these controls much
easier than unrestricted neural-weight reconstruction.

| Bundle | Optimized variables and supplied geometry structure |
|---|---|
| [wrong-circle-mie-20260902](wrong-circle-mie-20260902/summary.md) | 3: center x/y and radius; always a circle |
| [wrong-ellipse-mie-20260902](wrong-ellipse-mie-20260902/summary.md) | 4: center x/y and two axes; always an ellipse, fixed rotation; circle target lies in that family |
| [random-feature-implicit-mie-20260902](random-feature-implicit-mie-20260902/summary.md) | 7: center x/y, radius and four output weights; fixed radial tanh features, exact circle available with zero output weights |
| [wrong-star-nystrom-20260903](wrong-star-nystrom-20260903/summary.md) | 5: center x/y, mean radius, amplitude and rotation; lobe count fixed at five |

The saved videos show accepted contours from these parametric updates, with
optional labelled interpolation between iterates. Method B is a conversion
step, not evidence that a learned MLP owns the shape.

Moved from `results/inverse/method_b` on 2026-09-07. Original bundle IDs,
measurements, videos and recorded commands are preserved. Successful recovery
here is evidence for known-family parameter estimation, not full-MLP recovery.
See the [two current inverse pipelines](../../inverse/README.md),
[catalogue](../../README.md) and [relocations](../../relocations.json).
