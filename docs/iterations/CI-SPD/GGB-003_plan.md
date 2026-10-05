# GGB-003 Stage one exact translation on case 8

2026-10-05. Owner: Codex. Independent reviewer: Codex translation design review.
**APPROVED — user: "Approve GGB-003" (2026-10-05), before either inverse run.**
Implementation and bounded correctness tests are preparation, not an inverse
experiment. The user's request to test stage-one translation on case 8
explicitly selects this external scene as an exception to the TG-002 default.
It does not authorize a new branch or worktree; use the existing checkout.

## Question and hypothesis

Does exact centre motion during the first stage improve the latest
four-frequency case-8 inverse, compared with its original normal-only update?
Hypothesis: relocating without deforming the curve reduces residual and
geometric error under the same data and budgets. Failure to improve those
metrics, or an unresolved endpoint, does not support promotion.

## Fixed comparison

- **B:** a fresh control using GGB-002 F4's original stage sequence and settings
  with the current maintained package. Archived GGB-002 F4 is contextual
  evidence, not substituted for the fresh control.
- **T:** same fitting inputs and settings, except stage M3 alternates one exact
  translation LM update and one ordinary certified-spectral M3 shape update.
  At most 100 translation/shape cycles, with both blocks sharing the original
  2600-unit stage quota and the original global cap. Count the additional
  forward/derivative evaluations and repeated linearizations explicitly.
- M7 and M11 use the original ordinary shape update and 100-iteration caps
  in both arms. No explicit translation block is used after M3. Ordinary
  normal updates may still move a curve's centre at later stages.

The new translation coordinates change only Cartesian coefficient c0 by
`(tx + i ty)/length_unit_m`. Their exact derivative changes only that same
coefficient. Their existing order-one limits are 18 mm per axis before
halving. Do not multiply Jacobian columns or use an artificial sensitivity.
There is no new centre prior or truth-based direction. This first test uses
an on/off stage schedule; it does not test a gradual decay schedule.

Translation and shape blocks retain separate damping values, initialized at
1e-3 and carried from each block's last accepted next-damping value. Each
block rebuilds its objective/Jacobian after the other moves the curve; stale
checkpoints are never resumed. A translation-only gradient or no-step stop
does not imply whole-problem convergence. Stop M3 if neither block accepts
in a full cycle, the full objective meets the existing discrepancy target,
or the original work/time/numerical-stop rules apply. Numerical failures
remain failures; no candidate retry policy is changed.

Keep the GGB-002 sealed `inputs.npz` byte-identical: four real frequencies
0.5/0.75/1/1.25 GHz, 512 pairs each, the same 5% noise, known material, and
centred 0.35 m circle. No regeneration, localization, grid search, restart,
extra data or outcome-dependent tuning. Keep storage band 32, trace cutoffs
64/96, field agreement 1e-4, original frequency weights and noise discrepancy,
domain [-1,1]^2 m, scheduled damping, and all shape validity/acceptance checks.
Use CUDA, one case worker, one frequency thread and single-thread BLAS.
Exact translation preserves intrinsic geometry; domain admission and solver
readiness still require their existing checks.

Each arm retains 8000 fit work units and 2400 seconds total fit allowance.
Work exhaustion remains distinct from convergence. The additional translation
work consumes the same quota rather than receiving a separate budget. Run B
once, validate/commit/push it, then T once and validate/commit/push it. No
automatic reruns or setting changes. Report wall times as single observations,
with concurrent machine activity declared rather than as precise speedups.

## Qualification and evidence

Before inverse execution require exact invariance of every nonzero Cartesian
coefficient under translation, correct non-unit metre conversion, zero-step
identity, and validation of the base geometry. Check the reciprocal derivative
against rebuilt translated fields on a circle and a saved curved state at
all four frequencies, on CPU and CUDA, including non-unit scaling; maximum
relative column error must be <=1e-5. Check the alternating controller with a
bounded mocked controller fixture: separate damping, no quota reset,
continuation after translation-subspace stationarity, and refusal to invoke
the translation controller in M7/M11. Retain accepted states independently
of terminal Jacobian construction so quota exhaustion cannot drop a step
from the saved trajectory or reset the carried damping.

Use a fresh manifest under `results/validation/cleaned_interfaces/GGB-003/`.
Verify the GGB-002 input hash directly against its original preparation record;
do not rewrite its source seals to accommodate the new module. Save the new
source hashes, qualification records, approval, environment, complete block
and stage histories, candidate exceptions, curves, work and physics receipts.
Preserve unsuccessful runs and endpoints before any audit or report can fail.

Audit each endpoint at cutoffs 64/96 across all four fitted frequencies plus
the archived 0.4 GHz holdout. Report every residual against its noise target,
field refinement, joint discrepancy, original GGB image scores, and boundary
centre/size errors as post-fit diagnostics only. Retain direct boundary
comparison figures and a video using the existing generator; do not display
the inverse as a rasterized material image. Truth never selects a step.

Improvement means lower qualified residual and improved shape/centre metrics;
recovery requires the fitted-frequency noise targets and numerical gates,
with image quality reported alongside. Faster failed termination is not a
recovery. This single-case experiment cannot establish a general continuation
schedule or superiority over GauGal.

## Approval and implementation

The user explicitly requested this intervention, but repository AGENTS.md
separately requires approval of the experiment ID before execution. Request
approval of GGB-003 after implementation, correctness checks and review.
Approval was then received verbatim: "Approve GGB-003". The fixed comparison
above is the approved protocol.

Numerical primitive: `solvers/bem_inverse/translation.py`.
Campaign and block schedule: `experiments/benchmark/ggb003.py`.
Tests: `pytest/bem_inverse/test_translation.py` and
`experiments/benchmark/test_ggb003.py`.

Preparation completed before approval: 105 package, adapter and controller
tests passed (10.75 s). Translation derivative qualification at all four
frequencies and both geometries passed on CPU and CUDA; maximum relative
column errors were respectively 1.425e-9 and 1.430e-9 (limit 1e-5).
The first qualification attempt stopped on an erroneous cleanup call to an
absent `close()` method, before any inverse run. Its failed receipt and driver
snapshot are retained under `qualification_attempt_01/`; the corrected driver
passed. No inverse outcomes are available at preregistration.

Reproduction (EMNerf Python; `PYTHONPATH=solvers:.`; single-thread BLAS):

```bash
python -m pytest pytest/bem_inverse experiments/benchmark/test_ggb003.py experiments/benchmark/test_ggb002.py -q
python -m experiments.benchmark.ggb003 qualify
# Only after explicit GGB-003 approval is recorded:
python -m experiments.benchmark.ggb003 run --arm B
python -m experiments.benchmark.ggb003 verify
# Commit/push B before running T.
python -m experiments.benchmark.ggb003 run --arm T
python -m experiments.benchmark.ggb003 verify
```
