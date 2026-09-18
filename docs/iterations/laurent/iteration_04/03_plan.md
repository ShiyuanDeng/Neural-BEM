# LAU-003 — preserve inverse sensitivities in a reduced Laurent trace space

- **Approval status:** APPROVED by the user's 2026-09-17 direction, “we should
  divert to our innovations. so you go ahead”. This authorizes this bounded
  innovation screen and supersedes the generic named-ID hold for this work.
  Work stays on the existing branch and checkout.
- **Execution status:** COMPLETE: bounded pilot closed 2026-09-17; the full
  campaign was not released after its gate failed. [Measured closeout](../iteration_05/01_results.md).
- **Question:** can a local coefficient-space basis preserve physical shape
  sensitivities and survive small geometry/acquisition changes where entry
  truncation failed, without using evaluation directions to construct it?
- **Hypothesis:** a basis enriched by four analytic shape tangents preserves
  all six tested derivatives, fields and flux residuals with at most half the
  trace unknowns, and survives both predetermined 0.5%-radius shape offsets.
  Failure at the frozen rank rejects that local-reuse hypothesis at this scale.
- **Baseline:** commit 25de4cd plus source-pinned existing workspace; LAU-001-R1
  independent physical gates and LAU-002 fixtures. No sparse-mask rerun needed.
- **Arms:** forward-only POD; equally normalized forward plus four state-tangent
  snapshot blocks; forward plus algebraic receiver-adjoint snapshots. All use
  an orthonormal basis V and the actual reduced solve `(V* A V) q = V* b`.
  Derivatives differentiate this frozen basis model, including b and C.
- **Rank selection:** sweep 8,12,16,24,32,48,64,96,128, plus available snapshot
  rank; numerical singular cutoff 1e-12. Select the smallest rank passing
  anchor-native receiver/flux residual 1e-8 and four training data tangents
  1e-5. If none, preserve the largest-rank failure. Neither Kress truth nor
  evaluation directions, geometry offsets or shifted acquisition selects rank.
- **Controls:** circle, ellipse, star, asymmetric star; common-radius ka=2/5;
  original trace cutoffs 16/24 for circle/ellipse and 40/48 for stars; B=128,
  terms=28. Pilot: ellipse and asymmetric star at ka=5. Campaign only if tests,
  full controls and representative frozen-basis finite differences pass and
  an enriched arm passes the asymmetric-star anchor at <= half dimension.
  Evaluation geometries: +/-0.005 times the normalized combination of four
  training directions with weights (1,-0.4,0.7,0.2). Shift source angles by
  pi/24 at the anchor as a separate development evaluation. Use the same six
  physical directions and 256/384-node independent Kress references everywhere.
- **Gates:** unchanged LAU-001-R1 physical receiver/residual 1e-6, six
  directional data derivatives 1e-3 and cancellation-aware objective agreement.
  Full controls use the existing stricter gates. Two independent directions
  never enter basis construction or rank selection. A synthetic offset truth
  supplies objective residuals only. These reused fixtures are development
  data, not generalization evidence.
- **Validation:** synthetic complex full-span and primal/dual derivative
  interpolation identities; frozen-basis finite differences including b/C;
  independent Kress gates; B=160 anchor refinement; source/artifact hashes and
  predicate read-back. Full output matrices are diagnostic; physical gates
  retain the same 24 paired measurements as the previous experiments.
- **Metrics:** ranks, actual reduced matrix sizes, basis and projected operator/
  derivative/acquisition storage, all errors and objective gates; separate
  assembly, basis, projection/solve timing and work. Dense full assembly is
  still required. No online complexity, memory-peak or runtime speed claim.
- **Scope/API map:** new `experiments/laurent_tangent_rom/` owns `model.py`
  (POD, reduced solve/tangent), `run.py` (bounded screen), `test_model.py`, and
  `audit.py` (read-back). Existing numerical packages are read-only imports.
  No production/default change, inverse campaign, material or topology extension.
- **Budget:** per pilot/campaign <= 30 minutes, 6 GiB RSS, 180 assemblies,
  1200 factorizations, 2500 RHS batches; reserve before operations. Fresh output
  directories; preserve all failures and source hashes. Stop at failed pilot.
- **Decision:** advance a passing compact enriched basis to a future local
  inverse/rebuild-policy test; otherwise retain the diagnostic and identify
  whether rank, physical accuracy or reuse radius failed. Generic sensitivity
  POD and interpolation are established methods, not a novelty claim. Our
  candidate contribution is their derivative-qualified Laurent transmission
  implementation and, conditionally later, an inverse acceptance policy.
- **Standing limits:** lossless scalar TMz, equal permeability, fixed component
  count, admissible Laurent log quotient, fixed center/scale, tested Cartesian
  coefficient directions only; finite-window refinement is numerical, not a
  rigorous window bound. Frequencies inherit the qualified low-frequency range.
- **Owner:** Codex. **Independent reviewer:** unassigned.
- **Artifacts:** `results/validation/laurent/LAU-003-20260917-<stage>-<nn>/`;
  results open iteration 05.
