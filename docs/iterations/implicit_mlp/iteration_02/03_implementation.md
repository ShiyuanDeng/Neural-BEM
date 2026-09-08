# Iteration 2 implementation and runnable handoff

## Closeout — completed 2026-09-08

**Iteration 2 is closed; iteration 3 has opened at the results stage.** The
mandatory bounded diagnostics and the supported acquisition experiments have
run. Both user-run long inverses completed their saved results and scheduled
reporting, stopping because no decreasing admissible neural step was found.
Completion is not convergence or successful star recovery. The current record
is [iteration-3 results](../iteration_03/01_results.md), and the active research
handoff is [the project README](../README.md). No iteration-3 proposal or agreed
plan has been adopted.

| Final-plan work | Closeout disposition |
|---|---|
| Stage 0: geometry bottleneck | Completed exact scalar/vectorized predicate checks and available saved-state replay. Historical rejected candidate geometries were not archived and cannot be claimed as replayed. |
| Stage 1: saved-state characterization | Completed circle 55/60, wrong-start star 0/16/32/40/47, and the available target-fitted star states from actual saved weights. Field drift and conversion measurements remain diagnostic evidence, not recovery. |
| Stage 2: curve metric | Completed resolved modal Jacobians and finite SD/GN/TSVD curve probes. Useful curve-space loss reduction was measured; it does not by itself qualify a neural GN optimizer. |
| Stage 3: weight-to-geometry motion | Completed frozen N/G/velocity, raw/converted motion and objective-derivative measurements. Repaired polygon-chord bias and confirmed quadratic motion errors in bounded saved-direction rechecks; failed finite geometry probes remain explicit. Numerator/denominator attribution is not fully resolved. |
| Stage 4: field-only repair | Completed at old star states 32/47. The tested repair did not establish improved conditioning and conversion with sufficiently preserved geometry; no inverse sampling factor was promoted. |
| Stage 5: contour-aware sampling | **Conditional, not run.** Stage-4 support was not established; uniform-box Eikonal sampling remained fixed in the acquisition experiments. |
| Stage 6: actual optimizer geometry | Completed fresh moment/proposal/trial instrumentation and short/long saved-record reviews. Intermediate paired Adam distortion is now measured; late finite proposal scores are incomplete where geometry rejects the probes. |
| Stage 7: paired-8 vs multistatic-8 | Completed qualification and both five-update inverse arms from identical weights, followed by shared evaluation and geometry review. This supported acquisition as the single longer-run factor. |
| Stage 8: higher-frequency multistatic | **Conditional, not run.** No reviewed finding isolated remaining acquisition conditioning as the cause after geometry/field ambiguity was controlled. Longer-run lobe collapse does not automatically pass this gate. |
| Stage 9: neural GN/TSVD | **Conditional, not run.** The prerequisites for promoting a neural metric were not collectively established; the supported acquisition change was tested first. Frozen curve GN evidence is not a completed neural GN test. |
| Separate late-star conversion audit | Completed independent production/audit resolution variation. A sample-sensitive historical refinement check was corrected using 1,024 base audit samples while retaining 0.2/0.01 mm limits. The new long-run terminal failures are documented separately. |
| Circle control | Completed frozen late-state motion/conditioning diagnostics, including corrected IFT checks. No new long circle inverse was scheduled. |
| Ellipse startup | Completed persistent initialization, failure logging, saved-weight replay and independent qualification. The tested initialization still fails the distance limit, so the conditional short smoke inverse was not run; this is not an ellipse accuracy result. |
| Reviewed longer star comparison | Completed the selected acquisition-only comparison: paired accepts 42 updates and multistatic 31, both below declared caps. Multistatic improves aggregate geometry but does not recover the lobes; paired develops severe distortion. |
| Handoff and next cycle | The [diagnostic repair record](04_diagnostic_fixes.md), [short acquisition decision](05_acquisition_review.md), and [iteration-3 results](../iteration_03/01_results.md) supply the measured answers and limitations. Unresolved mechanisms become iteration-3 questions; they do not authorize another run. |

The deliberately unrun branches above retain the controlling plan's evidence
gates. There is no outstanding mandatory inverse command to execute merely to
close this cycle. The current results distinguish complete accepted-transition
measurements from selected finite proposal probes that fail geometry, and retain
unavailable polar measurements rather than replacing them with zeros.

The original suite manifest retains `review_partial_results`: its 15 other jobs
completed, while ellipse startup exited 2 on qualification failure. That failure
was subsequently inspected and recorded; ellipse has not been relabelled as
qualified or counted as a successful inverse.

Final commit review also hardened future qualification fingerprints to cover
the underlying solver, geometry, oracle and SIREN packages, so changing a
numerical dependency invalidates an earlier qualification. This bookkeeping
change does not alter the archived trajectories. Recorded CSV bytes and their
hashes are preserved, including standard CRLF line endings; small reviewed
figures are included while generated neural-weight trajectories and checkpoints
remain local. Historical records are retained without replacing their results.

## Original implementation handoff — historical

The remainder preserves the implementation-time handoff. Its “runnable,”
“pending,” and “next command” statements describe that earlier point in the
cycle; they are superseded by the closeout above and are not current execution
instructions.

Implemented 2026-09-08 against the controlling [final plan](02_proposals/04_final_plan.md).
Existing September-8 results and working-tree changes are preserved. The new
commands use fresh output directories. This original handoff predates the
completed short inverses; the [acquisition review](05_acquisition_review.md)
now supports a longer controlled star comparison and gives the current command.
No long inverse has been run by the agent.

After the diagnostic suite completed, the [diagnostic repairs and updated inverse command](04_diagnostic_fixes.md)
supersede the original motion measurements and matched audit sampling below.

## Implemented paths

| Plan stage | Implementation | Execution status |
|---|---|---|
| 0: exact geometry bottleneck repair | Chunked original intersection predicate, retained scalar oracle, `audit_implicit_mlp_geometry_runtime.py` | Bounded saved circle/star replay completed; exact outcomes matched |
| 1: saved-state characterization | `run_implicit_mlp_frozen_diagnostics.py --stages characterize` | Runnable; restore actual named CSV weight columns and checkpoint constructor |
| 2: curve metric | `--stages curve_metric` | Runnable; twice-resolved central differences, normalized modal SD/damped GN/TSVD; truth only scores completed directions |
| 3: neural motion | `--stages neural_motion` | Runnable; unclipped N/G/1/G/V, arc-weighted spectra, normal-line correspondence, IFT convergence window, actual objective differences |
| 4: field conditioning | `--stages field_repair` | Runnable; deterministic band Eikonal plus zero anchors; no data or Kress call; original weights restored |
| 5: sampling ablation | `run_implicit_mlp_iteration2_matched.py --comparison sampling` | Requires measured Stage-4 support; preserves paired-12 and all other settings |
| 6: actual optimizer proposals | Core optimizer callback and per-iteration `.pt` snapshots | Enabled for new runs; stores m/v/step, clipping, Adam and fallback proposals, trials, accepted step, reset and sample hash |
| 7: acquisition comparison | `--comparison acquisition` | Qualify indexed neural path first, then paired-8 versus multistatic-8 |
| 8: higher-band comparison | `--comparison high_band` | Requires original-band multistatic evidence |
| 9: neural GN/TSVD | Deferred under the controlling evidence gates | No production optimizer change; curve GN must first be qualified |
| Late-star conversion | `--stages conversion_audit` | Production and audit resolutions vary independently; limits remain 0.2/0.01 mm |
| Ellipse startup | `run_implicit_mlp_ellipse_startup.py` | Saves freshly pretrained weights before geometry, logs failure stage/traceback, qualifies independent resolution; optional bounded smoke only |

Stage 0 measured exact equality for 25 unique saved/synthetic polygons (13,417
vertices). Polygon predicate time was 10.94 s scalar versus 0.89 s vectorized,
about 12.3 times faster. The complete bounded replay took 29.16 s. Full saved
circle60/star47 geometry outcomes and a fresh underresolved-star rejection
matched. Historical geometry-rejected candidate weights/polygons were not saved,
so they cannot be claimed as replayed. See the [evidence report](../../../../results/validation/implicit_mlp_adjoint/iteration-02-implementation/geometry-runtime/README.md).

The baseline uniform-box sample draw and acceptance rules are preserved. The
optional mixed arm uses 256 seeded global points and 256 deterministic points
near the accepted raw contour, with offsets spanning ±5 mm. Samples remain fixed
through every candidate in one search. After acceptance the samples and reference
regularized objective are rebuilt. Therefore `objective` is iteration-local in
that arm; `acceptance_objective` records the accepted value on the previous set.
Data loss remains globally comparable. No extra division by observation count is
introduced.

Validation: 177 focused and regression tests passed in 5.77 s across the new
diagnostics, startup persistence, optimizer bookkeeping, indexed forward and
adjoint paths, geometry replay, conversion audits and Method-B pullback. A
subsequent 12-test matched-runner check passed in 0.75 s after adding the complex
modal-coefficient serialization regression (178 distinct tests in total).
A real saved circle60 characterization also completed in 1.99 s: its fresh data
objective was `3.92687580480553e-6`, on-contour gradient magnitude ranged from
`0.922471` to `1.724180` (spread `1.86909`), conversion passed the fixed limits,
and weights were restored exactly. The [smoke report](../../../../results/validation/implicit_mlp_adjoint/iteration-02-implementation/circle60-characterize/report.json)
preserves these measurements. This smoke verifies execution; it does not qualify
a new inverse factor.

## Commands for the user

The diagnostic suite is `run_implicit_mlp_iteration2_suite.py`; it does not run
the inverse comparisons. After the September-8 suite completed, the frozen repair
did not qualify contour-aware sampling and ellipse remained unqualified. Run the
currently supported paired-8/multistatic-8 inverse comparison with one command:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python /home/drdeng/Neural_SDF_BEM_AD/run_implicit_mlp_iteration2_matched.py --action all --comparison acquisition
```

This performs the numerical integration checks, then actually runs both inverse
arms with up to five accepted updates each. It creates a fresh timestamped output
directory automatically. Copy only the command, not Markdown fence markers.

Run from the repository root. This environment already has the scientific and
test dependencies used for validation:

```bash
IMPLICIT_PYTHON=/home/drdeng/miniconda3/envs/EMNerf/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLCONFIGDIR=/tmp/implicit-iteration2-mpl
```

Characterize the required saved states first. Each invocation has its own work
cap. A cap preserves partial output and returns exit 2; it does not silently
qualify missing diagnostics. Use a fresh output path when rerunning.

```bash
"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/circle \
  --states 55,60 --stages characterize \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/circle-characterize

"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/star \
  --states 0,16,32,40,47 --stages characterize \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/star-characterize

"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/star-truth \
  --states all --stages characterize \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/star-truth-characterize
```

Run the curve metric before interpreting neural motion. These are frozen-state
diagnostics; they never launch an inverse. The metric uses modes 0–12 (25 real
coordinates), damping relative to the largest squared singular value, and a
relative TSVD cutoff; all actual values are recorded in the report.

```bash
"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/star \
  --states 47 --stages curve_metric --curve-modes 12 \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/star47-curve-metric

for IMPLICIT_STATE in 32 47; do
  "$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
    --run-dir results/inverse/implicit_mlp/2026-09-08/star \
    --states "$IMPLICIT_STATE" --stages neural_motion --motion-modes 20 \
    --max-evaluations 160 --max-wall-seconds 600 \
    --output-dir "results/validation/implicit_mlp_adjoint/iteration-02-next/star${IMPLICIT_STATE}-motion"
done

for IMPLICIT_STATE in 55 60; do
  "$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
    --run-dir results/inverse/implicit_mlp/2026-09-08/circle \
    --states "$IMPLICIT_STATE" --stages neural_motion --motion-modes 20 \
    --max-evaluations 160 --max-wall-seconds 600 \
    --output-dir "results/validation/implicit_mlp_adjoint/iteration-02-next/circle${IMPLICIT_STATE}-motion"
done

"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/star \
  --states 32,47 --stages field_repair --repair-steps 25 \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/star-field-repair
```

The independent conversion audit and ellipse qualification can be run separately:

```bash
"$IMPLICIT_PYTHON" run_implicit_mlp_frozen_diagnostics.py \
  --run-dir results/inverse/implicit_mlp/2026-09-08/star \
  --states 40,47 --stages conversion_audit \
  --production-factors 1,2 --audit-grids 257,513 --audit-samples 512,1024 \
  --max-evaluations 160 --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/star-conversion

"$IMPLICIT_PYTHON" run_implicit_mlp_ellipse_startup.py \
  --max-wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/ellipse-startup
```

Ellipse defaults to geometry qualification only. To audit those exact weights
again, pass `--checkpoint .../ellipse-startup/initial_model.pt` with a fresh output
directory. Adding `--smoke-updates 3 --max-candidates 30` requests a smoke inverse
only after qualification succeeds within the same declared cap. Pretraining
and any in-flight geometry/forward operation can finish beyond a wall cap; caps
are checked between operations, not by killing a solve.

After reviewing the earlier diagnostics, print the matched acquisition plan,
qualify it, then explicitly launch the short inverse arms:

```bash
"$IMPLICIT_PYTHON" run_implicit_mlp_iteration2_matched.py --action plan

"$IMPLICIT_PYTHON" run_implicit_mlp_iteration2_matched.py \
  --action qualify --comparison acquisition --state 0 \
  --accepted-updates 5 --candidate-cap 120 --wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/paired8-multistatic8

"$IMPLICIT_PYTHON" run_implicit_mlp_iteration2_matched.py \
  --action run --comparison acquisition --state 0 \
  --accepted-updates 5 --candidate-cap 120 --wall-seconds 600 \
  --output-dir results/validation/implicit_mlp_adjoint/iteration-02-next/paired8-multistatic8
```

The qualification checks oracle ordering/refinement, exact paired selection,
normalized neural derivatives, rejected-step rollback, and starting-curve forward
and derivative refinement. It binds inputs, settings and implementation hashes.
Both arms share exactly the saved starting weights and one explicitly fresh Adam
state; historical moments are absent. Each arm stops at 5 updates, 120 attempted
candidates, or its wall cap. Qualification and posthoc diagnostics have their own
costs outside the inverse wall cap. The validated disjoint multistatic 3 GHz
evaluation runs only after both training trajectories are saved.

`--comparison sampling` requires an evidence JSON entry named
`stage4_supports_field_conditioning`. `--comparison high_band` additionally
requires `stage7_original_band_multistatic_conditioning_limited`. Each entry must
contain `supported: true`, a measured `reason`, a `report` path relative to that
JSON file, and its `report_sha256`. Pass `--evidence path/to/decisions.json` to
both qualification and run. These decisions must come from actual measurements;
no qualifying decision is supplied here. For a selected contour-aware acquisition
arm also pass `--sampling contour_band` consistently to both commands.

## Scientific handoff

The executable diagnostics produce arrays and measurements, not an automatic
claim of recovery. The [required question table](02_proposals/04_final_plan.md#21-required-handoff-table)
must be filled from the user-run reports before selecting a principal factor.

| Question group | Current measured answer |
|---|---|
| Exact runtime equivalence | Passed on available saved circle/star polygons and fresh near-contact/rejection cases; historical rejected-state archive absent |
| IFT raw motion and Method-B differential fidelity | Pending frozen motion reports; failed first-order windows remain unresolved |
| N versus 1/G distortion; signed modal direction | Pending spectra and target-correction scoring |
| Current Eikonal control and causal field repair | Pending field-only repair measurements |
| Curve-space GN/TSVD usefulness | Pending resolved Jacobian and admissible finite steps |
| Actual Adam distortion | Instrumentation implemented; pending fresh proposal measurements |
| Matched sampling / acquisition / high-band improvement | Not run; conditional gates remain in force |
| Late-star conversion cause | Independent resolution audit implemented; causal interpretation pending |
| Ellipse startup validity | Reproducible checkpoint/logging/qualification implemented; fresh qualification pending |
| Single factor for the next long star run | None promoted |

No conversion limits, trust region, network architecture, or geometry ownership
were relaxed. Production neural GN, continuation and long wrong-start reruns
remain deferred by the controlling plan.
