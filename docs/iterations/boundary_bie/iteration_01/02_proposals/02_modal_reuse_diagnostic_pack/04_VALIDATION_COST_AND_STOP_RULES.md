# Validation, work ledger and stopping rules

All numerical values below are **proposed diagnostic policy choices**, not literature guarantees, production defaults or already measured performance. Freeze them in the approved plan before results are seen. Deviations require an explicit record and, when scope/budget changes, new approval.

## 1. Scene selection and reference qualification

Use a maximum of five fixed geometries: a circle calibration, an ellipse, a smooth noncircular star, a saved separated multi-component state, and one saved difficult but admissible multi-component state. Prefer existing deterministic fixtures and stored coefficients; do not optimize or fit a new scene to make compression easier. Missing or unsupported saved states are recorded, not silently replaced by an easier circle.

Use at most two already supported frequencies: a low working frequency and a higher one drawn from existing qualified configurations. The historical 0.5 GHz and 1.25 GHz cases are candidate choices, not universal defaults. Record wavelength, object size and minimum gap so “high frequency” has physical meaning. Copy materials and acquisition from the selected fixture/bundle.

Do not use a withheld evaluation acquisition or truth to select the retained basis and then report that same data as independent validation. Since this is a fixed-geometry diagnostic, the known geometry is an input, not an inverse answer. Label any reused development/evaluation frequencies honestly.

Reference hierarchy:

1. Same-resolution production Kress is the algebraic reference for the modal transformation.
2. A separately refined Kress result qualifies physical discretization accuracy for each candidate.
3. Existing Mie/reference-solver data may add an independent control where already available; do not implement another solver for this packet.

For the same continuous curve, use a declared even-node ladder, normally 64/128/256 per component; allow 512 only where the selected existing difficult scene requires it and budget allows. The latest qualified topology cases need not share B0's old 64/128 settings. Further refinement is not automatic. If convergence cannot be established inside the cap, label the physical comparison `REFERENCE_UNQUALIFIED`.

Match nodes only for the full-coordinate equivalence test. For efficiency comparisons, let the reduced-node baseline choose its cheapest qualifying entry from the same frozen ladder. Do not compare different geometry fits at different node counts.

## 2. Default diagnostic accuracy tiers

Apply production acquisition selection and a fixed residual transform to all predictions and derivatives. Also retain unnormalized complex errors. Record absolute errors as well as normalized relative errors, especially near cancellation or nearly unobservable directions.

A practical primary screening tier is:

| Quantity | Proposed requirement |
|---|---:|
| Full-mode unitary control, scaled state/data | relative agreement 1e-10 on a well-conditioned calibration fixture |
| Candidate forward-data error against qualified reference | <=1e-6 |
| Refinement discrepancy of the forward reference | <=2e-7 |
| Candidate analytic directional-data error against qualified nodal derivative | <=1e-4 |
| Refinement discrepancy of the derivative reference | <=2e-5 |
| Scaled lifted full-space residual for a reduction/compressed solve | <=1e-6 relative to the RHS scale |

Use an absolute floor fixed from the scene/source scale, not a denominator selected per candidate. For example, with y the real-stacked, transformed response and S_y a fixed nonzero incident/reference source-response scale, use

    error_y = ||y_candidate - y_reference|| / max(||y_reference||, 1e-12*S_y).

Record the chosen S_y and its construction. For derivatives per unit physical displacement use an analogous floor 1e-12*S_y/ell. Mark floor-dominated cases; do not turn an unobservable direction into a large relative-error claim or silently count it as strong sensitivity evidence.

These tiers are an initial screen, **not qualification for the project's smallest existing inverse tolerances**. If a production endpoint requires 1e-8 prediction fidelity, success at 1e-6 does not establish readiness. Optionally report already affordable stricter results, without changing the primary gate or spending beyond the cap. A large roundoff/conditioning issue must be explained; do not loosen the equivalence check silently.

Compare Dirichlet and Neumann trace errors separately with arc-length weighting. Keep the fixed nondimensional scaling used for algebraic comparisons. Do not combine raw mixed-unit entries into unexplained condition-number or energy claims.

## 3. Sensitivity checks

Validate the actual reduced/compressed equations, not a projection of the reference answer. Use analytic operator derivatives as specified in [02](02_BIE002_MODAL_DIAGNOSTIC.md). A minimum supported single-interface test set includes noncircular geometry and a nontranslation direction at the higher frequency.

Taylor remainders

    ||y(c+alpha*v) - y(c) - alpha*Jv||

should display the expected local second-order trend over a useful range before roundoff/discretization floors. Inspect several decreasing physical amplitudes, holding topology, gauge path, modes, masks, nodes and normalization fixed. Explain branch changes or infeasible steps rather than interpreting them as derivative error.

A small number of central-FD comparisons may serve as an independent check where necessary. They consume the same work budget and are never the proposed production gradient. No full FD Jacobian or inverse replay is required.

Where analytic multi-interface support is missing, retain forward/operator results but write `SENSITIVITY_UNQUALIFIED` prominently. Do not infer inverse readiness from single-interface checks. Also do not claim that sampled JVP checks prove full-Jacobian or loss-gradient accuracy in every direction.

## 4. Cost accounting and fair comparisons

Separate at least: geometry/gauge work; kernel/system assembly; incident RHS construction; receiver-operator construction; transforms/projection/mask construction; LU factorization; triangular/RHS solves; receiver evaluation; analytic derivative assembly; validation; and total time.

Report cold setup and warm/reused work separately. If a factorization or derivative is reused in one arm, offer the same reuse to the comparator whenever mathematically legitimate. All source RHS must be batched identically. Report implementation limitations instead of assigning theoretical cached times to an unimplemented baseline.

The projected-matrix prototype still allocates the full matrix. Report peak live storage including A, transformed matrices, temporaries and derivative arrays. Smaller reduced-factor storage is not smaller peak memory.

Use one numerical worker, fixed single-thread BLAS settings, no simultaneous benchmark arms, and recorded load/environment. Reuse assembled fixtures for algebraic repeats but label that correctly. For finalists, use three paired repeat timings with identical warm-up policy. Publish median and range. If system load or timing variability dominates the difference, state `TIMING_INCONCLUSIVE` rather than selecting the best run.

A full unitary Fourier transform has the same singular values as the original scaled matrix. A lower reported condition number after some other scaling, truncation or change of norm must be attributed to that separate intervention.

## 5. Hard execution budget for BIE-002

The first approved campaign, including smoke tests, validation and repeats, stops at the first reached limit:

- **120 full frequency-system assemblies**, including exact-forward, refinement, derivative-validation and timing-repeat assemblies.
- **36 analytic directional-operator assembly calls**; count additional primal kernel recomputation inside them, separately in the ledger, rather than calling it free.
- **300 factorizations in total**, including full-mode, reduced, sparse-pattern, nodal, tangent-library hidden factorizations and repeat runs.
- **600 RHS solve batches**, with RHS column counts recorded; batched solves are not one physical transmitter unless there is only one RHS.
- **1,800 seconds of numerical execution** accumulated across diagnostic processes; this is a stop budget, not an expected completion time. Documentation/editing time is not used to justify extra numerical work.
- **8 GiB process resident memory**, with a planned live-array budget below 4 GiB. Stream/discard large derivative arrays; never cache q dense derivatives without accounting for them.

Count attempts as well as completions, failures and reused results. Reserve resources before each operation; checkpoint before launching an expensive block. Stop rather than automatically increase limits. Partial valid results are the deliverable when a cap is reached.

Suggested ordering: wiring control; reference qualification; single-interface primal/sensitivity reduction; multi-interface forward scope checks; fixed operator-pattern checks; finalist timing. Spend on scientific discrimination before extensive repetitions or aesthetic plots.

At most one bounded implementation-repair round is permitted after a wiring failure. Mathematical/prototype failure is not a license to introduce a new method. Do not launch a topology suite, full inverse run, frequency continuation, optimizer replacement or multi-interface derivative development.

## 6. Predeclared continuation criteria

These are screening thresholds, not claims of universal optimality. Report evidence on both hypotheses independently.

**H2-FIELD supports a next prototype** when a retained dimension r/n<=0.5 meets the primary forward and sampled derivative gates on at least two noncircular single-interface tests including the higher frequency, and either measured setup-inclusive savings exist or the profiled cost model identifies a substantial removable cost that reduced-node Kress does not already eliminate. Multi-interface inverse claims remain gated on their own sensitivity evidence.

**H2-OPERATOR supports a next prototype** when the declared fixed pattern provides at least a fourfold reduction of nonidentity coefficient storage on at least two noncircular tests while preserving the tested action/solve and available sensitivity accuracy. Include dense cross blocks in the total accounting. If only oracle sorted-threshold profiles show this, report `ORACLE_STRUCTURE_ONLY`, not a verified sparse algorithm or speedup.

For a measured speed advantage, a proposed practical screening threshold is >=1.3x median setup-inclusive speed against the cheapest accuracy-qualified nodal control, with variability too small to explain the difference. Do not require an intentionally dense diagnostic to be fast before investigating genuinely measured structure; instead label that outcome `STRUCTURE_PROMISING / SPEED_UNPROVEN`, identify the one missing assembly mechanism, and stop before implementing it.

If reduction needs almost all modes, fixed-pattern sparsity disappears, sensitivities fail, or reduced-node Kress wins, stop the tested prototype. Do not state that all spectral techniques are impossible. An unqualified reference or unsupported derivative is `INCONCLUSIVE`, not pass or fail by invention.

## 7. Machine-readable outputs and closeout

Required files in a fresh result bundle:

- `manifest.json`: run ID, exact commit/dirty-state hashes, approvals, numerical options, scene provenance, acquisition/materials, seed, scales, tolerances, dependency versions, machine and BLAS environment.
- `work_ledger.jsonl`: timestamp, stage/case/frequency, operation type, attempted/completed/failed/reused, n/r, RHS count, wall seconds, memory where measurable, cumulative counters.
- `accuracy.csv`: case, frequency, N per component, retained modes, method, reference ID/qualification, data errors, block trace errors, lifted residual, direction ID and sensitivity qualification.
- `timings.csv`: cold/warm classification, all cost components, repetition ID, source/RHS count, peak storage and comparison eligibility.
- `tests.log`, `commands.md`, and `README.md`: actual commands, failures and skipped tests, an evidence-linked verdict, and the next-action decision.

Useful verdict labels: `FIELD_REDUCTION_PROMISING`, `FIXED_PATTERN_PROMISING`, `ORACLE_STRUCTURE_ONLY`, `NO_USEFUL_SIMPLE_COMPRESSION`, `REFERENCE_UNQUALIFIED`, `SENSITIVITY_UNQUALIFIED`, `TIMING_INCONCLUSIVE`, `BUDGET_STOP`, `IMPLEMENTATION_BLOCKED`.

Do not fill missing quantities with zero. Use null plus a reason. Preserve all failed arms. Update the handoff and open the next iteration only after execution/closeout; do not manufacture results to complete a folder template.
