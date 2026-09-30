# Cleaned interfaces — user requirements

Recorded 2026-09-30 from the user's requirements and clarification.
Status: requirements recorded; implementation has not started.
The corresponding [CI-001 plan](../03_plan.md) owns the implementation sequence.

This document governs the proposed cleanup of the current SC/MA inverse.
The [pipeline inventory](../../../../pipelines/shape_frequency_continuation.md) records the existing
implementations and evidence. The intended outcome is one maintained,
cumulative inverse pipeline, with clear continuation policies and a
replaceable physics backend.

## 1. Retain performance as the pipeline evolves

**User requirement:** The cleaned implementation must retain performance
across all 36 SC/MA scene configurations examined so far. SC and MA developed
through successive iterations: the latest implementation must be checked
against earlier scenes to establish that its improvements retained earlier
capabilities.

**User clarification:** This does not mean copying four historical algorithms
into the new code or routing each scene to its historical winner. The target
is one cumulative pipeline incorporating the latest improvements. Earlier
results are regression benchmarks for that pipeline.

Acceptance requirements:

- Run the current cumulative implementation end to end on all 36 configurations,
  including the original starts, previous scenes, contrast variants and saved
  noise draws. Replaying archived final curves or only fitting saved suffixes
  does not establish this requirement.
- Compare each configuration against its documented historical performance.
  Report recovery, boundary RMS, Hausdorff bound, data residual, numerical
  qualification, stopping outcome, work and runtime. An unchanged aggregate
  success count must not conceal a regression on an individual scene.
- Keep exact source/input references and the full predecessor path for every
  historical benchmark. Historical suffix-only costs must be identified;
  compare full-path costs on a matched basis.
- Use one maintained algorithm and shared policy rules. Decisions may depend
  on declared problem inputs and fitting diagnostics. Benchmark scene IDs,
  target geometry and post-fit truth errors must not choose an algorithm,
  stage sequence or stopping point inside the inverse.
- Expose any regression introduced by later SC/MA changes. Address it in the
  common implementation or shared policy, and repeat the affected regression
  checks; do not hide it behind a scene-specific historical fallback.
- Define numerical equivalence tolerances and runtime comparison conditions
  before validation. Same-backend refactoring should preserve the algorithmic
  path and work, with numerical differences explained. Exact wall-clock
  equality across different hardware or host load is not a meaningful test.

The scope is the 36 single-object configurations in the
[SC-051 manifest](../../../../../results/validation/shape_continuation/SC-051-frequency-only/manifest.json):
6 `core`, 6 `fresh`, 7 `far`, and 17 `modal`. The four `coupled` and one
`intrinsic` configurations are outside this requirement. These are 36
configurations, including repeated target shapes with different inputs.

Current evidence is **34/36 recovery from a mixture of archived reference
strategies**, not a result for one cumulative implementation. The original C
at contrast 13.3 remains unrecovered from two starts. Retaining performance
does not itself require solving these known failures, but both configurations
and their actual errors must remain visible.

## 2. Make the continuation policy understandable stage by stage

**User requirement:** The continuation-policy interface must be especially
clear and easy for an outsider to understand, including what the policy does
at every stage.

Acceptance requirements:

- Give the maintained policy a named, versioned definition in one discoverable
  location, separate from the optimizer, physics backend and benchmark data.
- Provide a readable plan before fitting. Static stages show their values;
  adaptive stages show their decision inputs, formulas, thresholds, bounds and
  possible transitions rather than pretending the future decisions are known.
- Record the resolved stage and the reason for every adaptive decision during
  execution. The displayed plan and execution log must derive from the same
  policy definition used by the runner.
- Make localization, warm-up, damping, return to real frequencies, state
  cleanup, band release and final audit explicit operations wherever the
  policy uses them. No hidden changes in driver conditionals or global
  overrides.
- Preserve the precise geometry-update and cleanup semantics when extracting
  the current code. A clearer interface must not silently change the numerical
  method.

An outsider should be able to read the following for each operation or stage:

| Item | Required explanation |
|---|---|
| Purpose and entry | Why this stage exists and what causes entry |
| Observations | Active frequencies, real/complex wavenumbers, damping and weights |
| Shape controls | Update band `M`, geometry-storage band `K_geometry`, update construction and cleanup |
| Numerical controls | Requested accuracy, backend resolution profile and refinement rule |
| Budget and exit | Iteration/work limits, stopping conditions and failure handling |
| Transition | Next stage or adaptive rule, its inputs, and its recorded decision |

Shape-update bandwidth, geometry storage, physics trace cutoff and assembly
resolution must have distinct names. For example, `M`, `K_geometry`,
`K_trace`, and nodal/coefficient-workspace resolution must not be conflated.

## 3. Substitute the forward solver through one selection

**User requirement:** Substituting modal Müller, or another accurate forward
solver, must be as easy as a toggle.

Acceptance requirements:

- A single public backend selection chooses the physics implementation. For
  example, `solver=nodal_kress` or `solver=modal_muller` is the intended user
  experience; these names illustrate the design, not an implemented command.
- Changing that selection must not require changes to the continuation policy,
  optimizer, scene definitions, geometry update or reporting code.
- The selected backend supplies predictions and shape derivatives consistent
  with the complete geometry trial, plus backend-specific accuracy/refinement
  and work information. An already qualified solver can be treated as a
  service under this contract.
- Backend state is opaque to the inverse. Nodal traces, modal coefficients,
  system matrices, factorizations and quadrature choices remain inside the
  implementation. The inverse may inspect common diagnostics without relying
  on those internal representations.
- The selection covers every physics-dependent operation used by the run:
  fitting, Jacobians, localization qualification, frontier diagnostics and
  numerical checks. An explicitly declared independent audit backend is
  allowed and must be recorded; hard-coded hidden Kress calls are not.
- Validate required capabilities before fitting: acquisition, material model,
  geometry and any complex-frequency observations. Unsupported combinations
  must be reported explicitly rather than silently changing the algorithm,
  data or solver. CPU/GPU execution is separate from solver selection.

The nodal backend remains the reference during cleanup. A native modal
backend is the next implementation step, after the common pipeline passes
the retention checks. The cleanup must establish the interface for it now.

## Additional user direction: integrate the latest SPD work

On 2026-09-30 the user additionally requested that the latest SPD work be
checked and integrated when writing the cleaned implementation. Requirement 1
therefore includes retaining the qualified execution improvements as well as
the cumulative algorithm's reconstruction performance.

Preserve the integrated frequency threading, real-frequency CUDA execution
and exact geometry-validation/cache improvements from SPD-010 through SPD-015.
Integrate SPD-016's selected Mie-grid and damped CUDA assembly improvements
through maintained interfaces, with reference execution and capability checks.
Keep solver selection separate from CPU/GPU and concurrency settings. The
optional SPD-016 field-table extension is not selected because its measured
incremental saving is inconsistent.

The [SPD integration assessment](02_spd_integration_review.md) records the
evidence, code responsibilities, limits and required integration checks.
These results do not yet establish complete DF or all-36 speedups.

## Concerns to resolve during implementation planning

- **Retention has not yet been demonstrated.** MA-005 DF has saved results on
  20 configurations; 16 of the 36 lack a DF run. Its latest improvements cannot
  be assumed to preserve every earlier SC result.
- **A known later-stage accuracy tradeoff exists.** On the two noisy MA transfer
  cases, D already recovers and DF increases RMS from about 0.206 to 0.228 mm
  at contrast 4 and 0.015 to 0.076 mm at contrast 13.3. This is evidence to
  assess against retention tolerances and shared policy behavior, not a reason
  to install per-scene D/DF branches. See the
  [MA-005 results](../../../modal_atlas/iteration_06/01_results.md).
- **Preserve the observation contract.** Damped stages need complex-frequency
  data. Earlier real-frequency-only cases do not automatically supply them.
  If the cumulative policy requires additional observations, identify that
  explicitly; generating new synthetic observations is a changed data contract,
  not an unchanged-input replay. Preserve the existing noise draws and disclose
  the independently generated damped-noise model.
- **Forward accuracy alone is insufficient for the toggle.** The shape
  derivative must match the actual update and solver accuracy must support the
  inverse step. MA-006 demonstrates that a small field error can coexist with
  a much larger local-step error. Its projected nodal-to-modal study is distinct
  from a native modal assembler; see the
  [MA-006 qualification limits](../../../modal_atlas/iteration_07/01_results.md).
- **Performance needs an explicit comparison contract.** Numerical tolerances
  and acceptable runtime variation remain to be specified from the existing
  evidence and matched execution conditions. Aggregate recovery alone is
  insufficient, and no numerical tolerance or speed claim is established by
  this requirements document.

The earlier suggestion to preserve four historical algorithms as the cleaned
pipeline is superseded by the user's clarification. The requirement is one
cumulative implementation with demonstrated retention across earlier scenes.
