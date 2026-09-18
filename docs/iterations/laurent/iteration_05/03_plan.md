# LAU-004 — protected primal spans and guarded local reuse

- **Approval status:** APPROVED by the user's “go” following the LAU-003
  closeout and its proposed adaptive sensitivity-preserving reduction.
  Existing checkout/branch only; no branch or worktree creation.
- **Execution status:** COMPLETE, 2026-09-17. The pilot qualifies numerical
  accuracy and guard behavior but fails compact nonanchor reuse, so the full
  campaign is not released. [Closeout](../iteration_06/01_results.md).
- **Question:** does preserving the primal span before compressing sensitivity
  corrections improve rank/reuse, and can a computable defect check reject
  inaccurate frozen models without reading the physical evaluation reference?
- **Hypothesis:** a hierarchical basis preserves all six physical derivatives
  at <= half the original dimension and survives the two 0.5%-radius motions;
  a training-only guard has zero false acceptances on evaluated candidates.
  Report rank improvements even if the half-dimension target fails.
- **Baseline:** source-pinned LAU-003 joint tangent POD, freshly evaluated under
  this experiment's common rank ladder; earlier artifacts remain unchanged.
- **Arms:** JOINT_TANGENT; PRIMAL_TANGENT (retain primal span, POD the orthogonal
  four-tangent residual); PRIMAL_DUAL_TANGENT (retain primal and algebraic
  receiver-adjoint spans, then POD the orthogonal four-tangent residual).
  Normalize each snapshot block as in LAU-003; singular threshold 1e-12.
  Reduced solves and derivatives reuse the unchanged LAU-003 implementation.
- **Rank selection:** common ladder 8,12,16,24,32,40,48,56,64,80,96,112,128,144,
  plus each available maximum; hierarchical ranks cannot truncate the protected
  span. Select smallest passing anchor-native receiver/residual 1e-8 and four
  training data derivatives 1e-5, otherwise preserve the largest-rank failure.
  New rank ladder is declared; original LAU-003 results are not reclassified.
- **Guard:** use only the current A/b/C, reduced state/receiver adjoints and
  four training operator/RHS/receiver derivatives. Require native primal
  residual <=1e-7, finite-system paired field error bound <=1e-7 relative and
  four paired derivative bounds <=1e-4 relative. Bounds use sigma_min(A),
  so this diagnostic includes a full dense SVD; it is not a cheap speed claim.
  Full native/Kress evaluation results cannot enter guard decisions.
  When refused, rebuild at the candidate using its primal/training/adjoint
  states and the same rank rule; if that rebuilt model is refused, return the
  qualified full native solution. Record frozen, rebuilt and delivered outputs
  separately. Each candidate starts from the same anchor basis; no path ordering.
- **Bound:** for E=A^-1 R, Xj the reduced tangent, Rj=bj-Aj X-A Xj,
  Z the reduced receiver adjoint, S=C*-A*Z, bound each paired derivative error
  by ||(Cj-Z*Aj)_i|| ||R_i||/sigma + |Z_i* Rj_i| +
  ||S_i||/sigma (||Rj_i|| + ||Aj||_2 ||R_i||/sigma).
  The field bound is |Z_i* R_i|+||S_i|| ||R_i||/sigma.
  Aggregate Euclidean pair bounds; convert absolute to relative with
  ||candidate||-bound as denominator, failing closed if nonpositive/nonfinite.
  This bounds error to the finite native system, not error to continuum physics.
- **Controls:** same two pilot fixtures (ellipse, asymmetric star), ka=5,
  K=24/48, B=128, terms=28, six directions (four training/two evaluation),
  source/receiver acquisition and synthetic objective truth as LAU-003.
  Scenarios: anchor; +/-0.001 and +/-0.005 normalized four-direction motion;
  +0.005 normalized two-untrained-direction motion; shifted sources pi/24.
  Truth and untrained directions never construct/select/rebuild or guard a basis.
- **Validation:** protected-span/orthogonality tests; finite-system bound tests
  on complex nonsymmetric matrices; a case with accurate fields and wrong
  derivatives must be refused; two-step physical frozen-basis FD at 1e-4 and
  5e-5, both below 1e-4; independent 256/384 Kress qualification and B=160
  anchor refinement. Finite difference refinement is predeclared, not a repair
  of LAU-003's preserved failed coarse check. Original physical/objective gates
  and stricter full-control gates remain unchanged.
- **Campaign release:** only if pilot full controls, bounds, FD, window checks
  pass, no guard-accepted model fails physical gates, and at least one new
  hierarchical model reuses a compact (<=half-dimension) basis successfully on
  a nonanchor candidate. Then run circle/ellipse/regular/asymmetric star at
  common ka=2/5. Otherwise close the pilot and preserve the failed conditions.
- **Metrics:** rank/storage, same physical errors, frozen/rebuilt/delivered
  gates, false accepts, conservative rejections, rebuild/fallback counts;
  timing including guard SVD, setup and all full solves. No inverse speed,
  continuum certificate, production promotion or novelty claim for generic POD.
- **Budget:** pilot <=180 assemblies, 2000 factorizations, 5000 RHS batches,
  30 minutes, 6 GiB; campaign <=280 assemblies, 6000 factorizations, 15000 RHS
  batches, 30 minutes, 6 GiB. Charge before operations and save failures.
- **File/API map:** new `experiments/laurent_adaptive_rom/`: `model.py` for
  protected bases and guard; `run.py` for evidence, selection and bounded policy;
  `test_model.py`, `audit.py`. Imports existing experiment/solver packages
  read-only. Existing LAU-003 source hashes must continue to validate.
- **Artifacts:** fresh `results/validation/laurent/LAU-004-20260917-<stage>-<nn>/`.
  Results open iteration 06. Owner: Codex. Independent reviewer: unassigned.
- **Standing limits:** same lossless scalar TMz/equal permeability, fixed
  component count/material, fixed Laurent center/scale and admissible log
  quotient; numerical window checks only. Reused fixtures are development data.
