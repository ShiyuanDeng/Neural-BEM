# Inverse pipeline review — 2026-09-05

Assessment of the current working tree, including the uncommitted neural and
multi-component additions. This is a review and proposed direction, not a
record that the proposed extensions have been implemented.

## Verdict

The repository has a strong controlled 2-D boundary-inversion foundation.
Independent Mie, Nyström, and multiple-cylinder oracles, coherent ordered
geometry, explicit failure states, and separate canonical/representation
metrics are substantive strengths. The successful latest experiment proves
that the radial Fourier inverse can recover its matched target. It does not
establish an advantage from an SDF or from thousands of neural parameters.

The present production MLP path optimizes a single star-shaped radial Fourier
curve. At K=5 it has eleven geometric controls: two center coordinates, mean
radius, and cosine/sine coefficients for modes 2 through 5. The data residual
determines updates in these controls. The MLP is then trained to represent the
accepted curve and can veto an update or prevent a convergence declaration.
Its weights do not independently determine the next production geometry
Jacobian. See [ownership](solver_neutral_inverse.md) and
[the optimizer](../solvers/sdf_inverse/neural_optimization.py).

Thus the SDF is currently mostly redundant **for reconstruction in this
chart**. It remains useful as an initialization/extraction interface and an
exportable representation, but is expensive to require on every iteration.
Increasing network capacity does not remove the authoritative chart's
single-component, star-shaped restriction.

## What the saved evidence actually says

The [2026-09-04 radial-continuation K5 run](../results/inverse_solver_comparison/mlp-radial-continuation-k5-ellipse-to-star-kress-20260904/metrics.json)
started from the wrong ellipse and accepted 44 updates:

| Measurement | Canonical curve | Extracted MLP contour |
|---|---:|---:|
| Training relative field L2 | 1.068e-8 | 0.005085 |
| Held-out frequency relative field L2 | 1.339e-8 | 0.004327 |
| Maximum sampled analytic-target distance | 2.570e-10 m | 0.216 mm |

The separately measured MLP/canonical curve-set drift was 0.329 mm, above
the 0.2 mm representation-convergence threshold. Its stop reason was
`representation_limited_stationary`, with `converged=false`.

Of 234.43 seconds in the inverse, direct forward evaluations used 78.19 s,
neural re-distancing used 125.63 s, and geometry audits used 30.07 s. Together,
re-distancing and audits account for approximately 66% of recorded inverse
time. This is a measured cost breakdown, not a measured speedup from a
curve-only ablation. Initialization is separate.

These are saved results; the audit did not rerun that long experiment. The
target is exactly representable in the selected K5 chart, measurements are
noiseless, materials and source calibration are known, and held-out data use
different frequencies on the same ring acquisition. These results do not
establish robustness to noise, unseen angles/apertures, multiple starts,
non-star-shaped targets, unknown materials, or unknown object count.

The legacy MOD path does couple an adjoint-derived shape surrogate into neural
parameters, but its leading-order geometry derivative freezes normals and
weights. Its directional tests therefore do not certify differentiation of
the complete re-extracted/remeshed boundary. Kress owns the solved system and
receiver operator but still has no implemented shape adjoint. These are two
different limitations, not interchangeable gradient implementations.

## How the SDF could earn its place

For the current homogeneous transmission problem, the physical domain is
determined by the interface and the assigned materials. Multiplying an
implicit field by a positive constant changes neither. Its off-interface
distance values are consequently a representation choice, not additional
measured physics. Eikonal regularization selects a useful distance-like
extension; it does not supply new observations.

I would retain the curve inverse as the numerical control and, after agreeing
the design, make per-iteration distillation optional. If only a final SDF is
needed, train and verify it at export. Keep reconstruction convergence and
representation accuracy separately visible.

To make the SDF an optimization variable, the next substantial numerical
milestone is a verified Kress geometry derivative. Differentiate the actual
discrete system, its right-hand side, receiver map, and paired observation
selection, including normals, derivative jets, speeds, quadrature weights,
and singular-split/diagonal terms. First check derivatives on coherent smooth
curve perturbations across finite-difference step sizes and node resolutions.
The existing parameter-FD path is a useful reference for those checks.

Then couple the unweighted normal shape-gradient density to the field. On a
regular negative-inside zero set, implicit differentiation gives

\[
\delta x\cdot n=-\frac{\delta\phi}{\|\nabla\phi\|},\qquad
\frac{dJ}{d\theta}
=-\int_\Gamma g_n\frac{\partial_\theta\phi}{\|\nabla\phi\|}\,ds.
\]

Here `g_n` is defined by `delta J = integral(g_n * delta x.n ds)`; apply arc
weights once, and verify the sign against finite differences. A custom shape
coupling is possible without differentiating discrete marching-square
connectivity. It still needs to be checked against the actual geometry update
and accepted forward objective. Simply replacing the current optimizer's
curve with its approximate MLP representation would reintroduce the drift
that the canonical-state correction deliberately removed.

The clearest SDF use case here is geometry outside the radial chart: concave
non-star-shaped boundaries, unknown component count, and explicit proposals
to add, remove, merge, or split components. A boundary-local shape gradient
does not by itself provide a mechanism to nucleate an unseen object. Such
proposals need additional spatial sensitivity or search, complexity control,
and a true forward/objective check after extracting a valid candidate.
Ordinary smooth-boundary BEM should not be evaluated at a singular pinch.

There is also a possible learned-prior role, provided the prior is actually
trained across shapes and tested on unseen ones. The referenced
[implicit-neural inverse-scattering paper](https://arxiv.org/abs/2206.02027)
uses both direct neural shape updates and a generative prior; that is a
different scientific claim from fitting an untrained network separately to
each accepted curve. It is background motivation, not validation of this
repository's dielectric solver.

One additional representation design issue deserves attention:
[re-distancing](../solvers/sdf_inverse/neural.py) supervises distance to the
polygon through solver nodes, while BEM uses a smooth curve. Polygon chord
error can therefore become a training target. For a 65 mm circle with 32
nodes, the midpoint discrepancy is `r*(1-cos(pi/N)) = 0.313 mm`. This example
does not attribute the latest 128-node run's entire error to polygonization;
it demonstrates why smooth-curve supervision must have a separately chosen
accuracy before interpreting the neural representation floor.

## Recommended next work

1. **Estimate one interior permittivity.** Interpret “updating epsilons” as
   recovering material `epsr`, initially with fixed exterior and fixed shape.
   Then solve jointly for shape and that scalar. Keep observations immutable;
   changing candidate materials must rebuild the prediction and enter the
   evaluation cache key. Use bounds or a positive parameterization. Inspect
   scaled Jacobian singular values and shape/material column correlations;
   report recovery error as well as field error. Sweep initial material and
   shape guesses, add noise, and test unseen scan angles. Add conductivity
   later, after validating lossy support in the selected forward path.

2. **Distinct materials on disjoint components.** The new multi-component
   package already discovers loops and solves their interactions, but all
   components share one lossless, nonmagnetic interior material. Introduce a
   material per persistent component identity and validate against independent
   two-cylinder data with unequal materials. Self blocks use their own
   interior material; cross-component interactions remain in the common
   exterior. Spatial sorting is not persistent identity across iterates.
   Nested/layered objects require a region/interface adjacency model.

3. **Data-driven topology and an SDF ablation.** Wire the multi-component
   forward seam into an optimizer that can change its geometry state and
   compare curve and SDF approaches at the same data, regularization, and
   accuracy. A decisive test starts with the wrong object count, recovers
   separated objects from data, and predicts held-out measurements. The
   current prescribed Cassini split video tests extraction and forwarding;
   it is not such an inverse experiment.

4. **3-D as a separate forward-model milestone.** Start with a validated
   forward sphere/multiple-sphere benchmark and a surface geometry contract.
   Full 3-D electromagnetics requires vector Maxwell traces and surface
   singular quadrature; the present scalar TMz/Hankel kernels and periodic
   curve quadrature cannot be promoted by adding a coordinate. The
   [Bempp operator documentation](https://bempp.com/handbook/api/boundary_operators.html#boundary-operators-for-maxwells-equations)
   illustrates the distinct Maxwell boundary operators and vector spaces.
   A deliberately scalar 3-D Helmholtz prototype would be a different target.

Across these steps, a validation matrix should include observation noise,
held-out acquisition geometry, multiple initializations, and targets outside
the chosen shape family. With additive measurement noise, consider weighting
residuals by measured noise uncertainty rather than solely by observed column
energy. If the intended endpoint is physical GPR, the missing air/ground
interface and acquisition model also need prioritizing: current physics is
homogeneous full-space.

## Correctness fixes in this review

- Parameter FD retains a valid one-sided probe when the other bound stencil
  probe has invalid geometry. Missing Jacobian columns no longer certify
  stationarity, and shrinking rejected steps no longer fabricates convergence.
  Complete projected gradients recognize true optima at declared parameter
  bounds with a distinct `projected_gradient_tolerance` stop reason.
- Single- and multi-component geometry enforce the declared negative-inside
  material convention using outward field-gradient direction. Previously CCW
  ordering could silently reinterpret a sign-reversed field as an inclusion.
- A supplied canonical initial curve without an explicit audited MLP contour
  now triggers one representation extraction. It no longer assumes zero drift
  or bypasses topology validation.
- Radial curves enforce node/validation sampling for their actual Cartesian
  Fourier bandwidth K+1, independently of Method-B's configured bandwidth.
- New MLP metrics preserve the exact acquisition, complex source strengths,
  material parameters, physical constants, target parameters, and declared
  noiseless observation policy. Existing saved bundles are unchanged.

These are bounded correctness and reproducibility repairs. The material,
topology, adjoint, distillation-policy, and 3-D proposals remain design work
for discussion. Test commands and outcomes are recorded in the
[validation change log](validation_change_log.md).
