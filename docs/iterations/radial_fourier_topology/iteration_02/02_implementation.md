# Iteration 02 implementation — automatic material topology

The user authorized implementation of the full-topology proposal on 2026-09-09, with discretion over the design and an explicit requirement for inversion videos. The new entry point is `run_fourier_topology_controller.py`; the iteration-01 and challenge drivers retain their reproducible historical behavior.

## Controller

`solvers/sdf_inverse/topology_controller.py` runs the existing central-FD LM refinement, reconsiders topology when refinement stops or exhausts its iteration budget, compares finite candidates, accepts the best improving state, and restarts LM with a new parameter vector, Jacobian cache and damping state. An empty initial state requests topology immediately. Neither truth geometry, target component count nor a prescribed event sequence enters the controller API.

All four event types compete in each pass:

- **Birth:** connected favourable exterior sensitivity regions supply weighted centres and finite circular radius ladders. Further controller cycles allow repeated births.
- **Death:** every component receives a direct leave-one-out trial. An optimizer feature-radius floor prevents indefinite shrinking of unwanted components and keeps radial necks resolved. It bounds the radial positivity certificate (or Cartesian equivalent-area radius). Existing components below that floor request topology immediately.
- **Split:** favourable interior removal thresholds and boundary-crossing corridors modify the material mask. Corridor directions come from the current component's principal axes. Candidate budgets preserve different child counts and corridor directions, so broad fragmented cuts cannot exclude a narrow two-child cut before objective evaluation.
- **Merge:** favourable exterior bridges modify the union of existing masks. Connected-component overlap determines all parent IDs, including additional components incidentally connected by a bridge.

Four-connected material labels and an old/new overlap graph classify events. Fully enclosed removal patches are recorded as `unsupported_nested_hole`. Small fragments, open contours and invalid fitted boundaries are rejected. Unaffected explicit components are retained exactly. Components wholly outside the inspection raster remain in the explicit state but are excluded from the visible connectivity count; an off-grid ghost therefore cannot hide an otherwise valid split. Split parents are retired; merge children record every parent. A lifetime ID set prevents reuse of retired IDs.

Each mask receives both a coarse area/centroid circle candidate and a smooth outer-contour fit. The latter uses a radial chart when admissible and accurate; otherwise it promotes to periodic Cartesian Fourier coefficients. Both charts use the same vector/rebuild interface and existing Kress objective. No new BIE solver or singular kernel is introduced.

## Interior sensitivity and acceptance

For the project's nonmagnetic scalar TMz convention, exterior scattering is `D_e u - S_e q` and the interior total field is `S_i q - D_i u`. Interior evaluation uses only the containing component's traces, with the same ordinary Helmholtz layer kernels used for exterior evaluation. No incident field is added to the interior Green representation. Probe points remain a configurable distance from boundaries; this is not a close-evaluation quadrature extension.

The removal derivative reverses the addition contrast and uses current interior physical and reciprocal fields:

\[
D^-J(z) = \sum_f \frac{w_f}{s_f^2}\operatorname{Re}\left[
(k_{e,f}^2-k_{i,f}^2)\sum_p \overline{r_{p,f}}\,u_{i,p,f}(z)\,u^{\mathrm{recip}}_{i,p,f}(z)
\right].
\]

The reciprocal receiver-source strength is one; the physical source retains the acquisition strength. Source pairing, conjugation, frequency weights and observed-column normalization match iteration 01. Tests check manufactured interior fields and compare the volume-integrated removal derivative against a finite uniform material perturbation, avoiding an unsupported nested-hole solve.

Every candidate is scored by the production Kress objective. The best candidate of each event type and resulting component count can receive the same short local-refinement budget to reduce contour-projection bias. Every improving candidate then receives a refined Kress solve. Acceptance requires both objective reductions to exceed an absolute/relative margin plus five times the disagreement between reductions. The best eligible production objective wins. Rejected events leave the exact current immutable state intact.

Videos show actual accepted states, including discrete transitions. Candidate-local trial states are not represented as accepted optimizer progress. The event jump may include the explicitly recorded candidate-local refinement.

## Numerical scope

The demonstration suite uses the qualified 0.5-GHz, noiseless, same-material ring acquisition. Circle observations come from the independent cylindrical-harmonic reference. The connected elliptical truth uses a separately sampled 256-node analytic-boundary Kress solve. Production/refined event checks use 64/128 nodes, a 121-square inspection raster, and the existing physical 10-mm component-clearance policy (plus its sampling-dependent clearance requirement).

Nested holes, touching boundaries, multi-material regions, noisy-data selection and a global-convergence guarantee remain outside this implementation. The Cartesian fallback has a nonradial C-contour and mixed-state regression; the headline inversions themselves select radial charts. The controller reports `topology_stationary`, `maximum_events` or `maximum_cycles` honestly when its finite search or budgets do not recover the data.

The final measured results and videos are indexed in [03_results.md](03_results.md).
