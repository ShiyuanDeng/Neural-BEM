# SPD-001 — combined analytic Jacobian and execution-speed comparison

- Approval: **APPROVED** by the user's 2026-09-15 instruction: “you go ahead,
  i expect to see runtime speed ups in concrete numbers. be careful of running
  terminals b4 you wire anything in”. This approves the combined comparison
  discussed in this session; no branch/worktree creation is authorized.
- Execution: **COMPLETE**. [Results and closeout](../iteration_02/01_results.md).
- Owner: Codex /root. Review: self-review; no independent review claimed.

The preceding SPD-001 contract was a proposal, not an executed plan. This
contract resolves its overlap with the user's CPU/CUDA request and bounds the
first execution to numerical qualification and actual fixed-topology optimizer
timings. Broad four-/twelve-scene recovery claims and changing defaults require
separate evidence and are outside this measurement.

## Sequencing and scope

Before numerical edits, TOP-025's campaign and renderer had exited. Its
verification was PASS with complete counts; all 774 final artifact hashes
were checked successfully. Historical bundles stay intact. Work uses the
existing checkout and branch. Timing arms run sequentially with single-thread
BLAS and no sibling repository numerical/render worker. Check process state
and measured source hashes at every arm boundary.

Promote the BIE-004 coupled derivative into a solver module; add an opt-in
Jacobian mode in the existing multi-radial optimizer. Retain the default FD
path. Share real-argument special-function acceleration between primal and
derivative code; add CPU/CUDA factor/solve support with retained factors.
Execution settings are scoped to a run, not process-wide monkeypatches.
No optimizer, geometry, quadrature, damping, precision, acceptance or stopping
formula is changed. New accounting distinguishes derivative assembly and
tangent solves. Keep the existing optimizer function name and result fields.

The analytic path re-solves its base with factors retained, as proposed in
SPD-001; charge this setup. Avoid a broad objective-cache redesign. Exact
cross-direction special-function caching is deferred so the measured
interventions remain identifiable.

## Corrections to the proposal

1. An analytic derivative is not numerically identical to a finite-step central
   or one-sided quotient. Matching active constraints alone cannot imply
   identical iterates. Qualify Jacobians and measure resulting trajectory
   discrepancies. Do not promise bitwise trajectory equivalence.
2. An optional FD-compatible constraint policy uses geometry-only stencil
   checks, exact existing one-sided FD for the few affected columns, and the
   existing unresolved-zero convention when both sides fail. Charge and report
   fallback solves. The true analytic policy reports no stencil-based zeros;
   physical candidate feasibility still binds.
3. The brief's 90–95% shares are **solve-count** shares, not measured time
   shares. Recompute actual phase times before applying Amdahl estimates.
4. Use current production geometry validation (256 samples), all relevant
   residual weights, and the production FD step (1e-4). The BIE-004 diagnostic
   used 1024 validation samples and 1e-5 FD, so its 1.87x is not the new baseline.
5. Do not flip a production default based on this bounded experiment.

## Six arms

Jacobian: FD / analytic. Execution: reference CPU / fast real-argument CPU
kernels / fast kernels plus CUDA linear algebra. Include all six arms even
if CUDA adds no benefit. Same grids, sources, weights, states and optimizer
settings in each matched comparison. Keep float64/complex128. All GPU transfer,
factorization and synchronization costs belong in timing.

## Gates, measurements and ceilings

1. Permanent numerical tests: real/complex special-function parity including
   derivative orders -1..3; CPU/CUDA factor reuse; coupled derivative and
   weighted residual ordering; FD-default regression; constraint policy tests.
   Reuse existing BIE-004 algebra/operator controls. Any failure stops before
   optimizer timing until repaired and revalidated.
2. Saved-state qualification: current terminal two-star state, N=256 and all
   four training frequencies against the archived 192x34 Jacobian, plus small
   one-/three-component and selected N=512 derivative checks. Full/worst-column
   relative FD tolerance 1e-4; primal consistency 2e-11. Backend parity is
   checked directly against analytic CPU. Keep failed measurements.
3. Fixed-state full-Jacobian timing: terminal two-star state, N=256,
   1.25 GHz, 24 source RHS, 34 directions; all six arms, three alternating-order
   repetitions. Setup is charged. Report medians/ranges and phase/work counts.
4. Actual optimizer timing: same saved terminal geometry and four-frequency
   data, N=256 production with N=512 feasibility, one LM update plus its initial
   and terminal Jacobians per arm. Use frozen production optimizer settings;
   retain all candidate attempts, stop reasons, gradients and states. A short
   optimizer timing is not a completed reconstruction or topology campaign.
   Compare coefficient displacement and objective; a difference >1e-6 m in
   the coefficient infinity norm is labeled trajectory divergence, not silently
   accepted as an equivalent path. Hardware-only comparisons within a Jacobian
   mode require agreement to that tolerance. Analytic-versus-FD differences
   remain explicit even when the accuracy gate passes.

Hard ceilings: 3600 seconds for qualification plus Jacobian timings; 3600
seconds for optimizer timings; 8000 assembly equivalents, 4000 analytic
direction calls and 5000 factorizations overall. Initial failed attempts count.
No full scene campaigns within this contract. A failed accuracy gate prevents
optimizer runs. Runtime results may be negative. Do not extend a ceiling
silently. If source/concurrency changes affect a timing row, mark it invalid;
only rerun within the same declared budget after the cause clears.

## Artifacts and decision

Fresh `results/validation/speedup/SPD-001-<timestamp>-combined/`: source and input
hashes/snapshots, test log, contract, process/environment records, numerical
qualification, per-arm timing/counts, full Jacobians, optimizer trajectories,
summary CSV/JSON and README. Archive the baseline sources before modification.

Report actual speedups for the six-arm fixed-state comparison and separately
for the bounded optimizer. Choose a recommended opt-in execution mode from
those measurements. Preserve FD/reference CPU defaults and state the limits
of the evidence. Results open speed-up iteration 02.
