# SC-047: coupled non-star-shaped continuation and topology diagnostics

Owner: Codex. Existing `feature/shape-frequency-continuation` branch, following
Claude's final `34355f99` review and the user's 27 September authorization.
This is an owner qualification, with no independent reviewer assigned.

[Frozen contract](../../../../docs/iterations/shape_frequency_continuation/iteration_26/03_plan.md).
The machine-readable measurements are `qualification.json`, `atlas.json`,
`strategy_summary.json`, `topology.json` and the rebuilt `summary.json`.
The [final interpretation is in iteration 27](../../../../docs/iterations/shape_frequency_continuation/iteration_27/01_results.md). Historical Claude and SC-042–046
records are preserved.

**Complete:** coupled numerical qualification and all 12 endpoint audits pass.
Worst-object RMS falls from 3.81 mm to 0.74–1.03 mm. Conditional object selection
passes none of its four superiority gates; all four conditional arms retain
their budget stops. The topological derivative qualifies to about 7 ppm, but
finite false births and a misplaced missing-object minimum prevent action
promotion. The 250-test continuation/Kress regression and 858 frozen-evidence
checks pass. Run `evidence_checks.py` to verify receipts and decisions without
rerunning the fits. See
[accuracy/work](accuracy_and_work.png), [all reconstructions](reconstructions.png),
[conditional spectra](conditional_information.png), and
[topology controls](topology_diagnostics.png).

## Method and scope

The small adapter in `experiments/shape_continuation/multi_object.py` composes
existing Cartesian Fourier curves and their existing finite updates. Every
source and reciprocal solve includes every object, including frozen objects.
The forward dispatch reuses `gpr_bem_kress.multicomponent`; LM, normalization,
refined-mesh acceptance and solve accounting reuse `lm_backend` unchanged.
The experiment injects SC-035's centred projected trial and its complete
geometry derivative. No polar-angle gauge is applied.

`MultiCurve` currently shares the state band K across objects. The injected
`MultiUpdate` supports separate update bands and active-object subsets. N is
the node count **per component**. The physical metric is the sum of each
object's mean-square normal displacement in metres, rather than a
perimeter-weighted global average. Trials retain each component's geometric
checks and the existing coupled separation/containment checks.

This is a **local fixed-count recovery screen**: an ellipse and an already
C-shaped initial component, known contrast, correct count and approximate
locations. Initial outlines are similarity transforms of the true outlines;
they do not contain intrinsic morphological errors. It does not demonstrate discovery of a non-star-shaped component
from a circle. Two separations and clean/1% noise variants of the same target
pair are four scenarios, not four independent shape families. The noise seed
is shared deliberately; no statistical generalization claim follows.

The independent multi-cylinder reference qualifies the circle physics. C-shape
observations use the same model at refined quadrature; shared-model bias
remains. The inherited 24 paired source/receiver observations and four
frequencies are retained; cross-pair predictions are not extra measurements.

## Conditional information and policy

The atlas transforms each Jacobian with its complete-trial physical metric,
then projects it off the other object's measurement-space span. All blocks
use one absolute numerical-rank threshold derived from the joint physical
Jacobian. These are relative data scales, **not noise whitening**. The
known-neighbour versus unknown-neighbour comparison uses the same scene and
data metric. The target-alone comparison retains that metric but changes the
physical fields; it has no information monotonicity guarantee.

The prospective policy selects the object with the largest residual
projection onto its conditional response space. This is a nomination rule;
the shared optimizer still checks the actual finite candidate. Its extra
forward and reciprocal work is charged. All arms have the same M=3/5 ladder,
K=32, N=256/512, physical step bound and maximum dispatch count. The first
ablation changes object selection only. The frozen superiority criterion
requires geometric improvement over both controls at no greater work.

`report.py` also scores the last saved states at a common work ceiling. These
states are chosen by recorded cost alone, never by the best truth score.
Endpoints remain the actual final accepted states, including budget stops.

## Topological response and its limits

For the equal-permeability, finite-contrast scalar transmission model, the
inserted-disk data response per unit package area is

`q(x) = (ki² - ke²) u_source(x) u_reciprocal(x)`.

Both total fields include the current coupled scene. Reciprocity is bilinear,
without conjugation. After applying exactly the objective's relative scales,
frequency weights and real stacking, the objective derivative is `r.T @ q`.
The inserted disk has area `pi * epsilon²`; one package length unit is 5 cm.
Thus the derivative per physical square metre is the displayed derivative
divided by `0.05²`. No per-frequency image normalization is used.

This follows the inherited project's current-domain convention in
`sdf_inverse.radial_topology.evaluate_current_domain_topological_derivative`.
[Carpio, Pena and Rapún, §4.2](https://arxiv.org/html/2501.15327v1#S4.SS2)
provide the scalar dielectric topological-imaging precedent; their displayed
one-step empty-background formulas do not substitute for current-scene fields.
The code's coefficient, area scaling and sign are checked directly using
progressively smaller finite insertions.

The tiny disks are reference probes, separate from the production topology
controller and its radius floor. Finite 3 mm births and whole-component
deletions are counterfactual forward calculations. They never modify a
baseline trajectory. Wrong-boundary and noisy correct-count cases test false
births; equal-budget shape refinement tests persistence. A negative map value
or a lower residual alone does not establish the correct component count.
Unknown-count acceptance still needs a declared discrepancy/complexity rule,
candidate refinement comparisons, more controls and independent noise draws.

## Work and reproduction

Runs are sequential with one BLAS/OpenMP thread. Frequency solves and
reciprocal batches are both charged to strategy ledgers. Topology records
also retain grid evaluation timings, RHS counts and separate refinement
ledgers. Geometry projection counts and timings remain in update records.
Raw wall times are observations from one run per arm, not repeated timing
benchmarks. Report generation and geometry-only scoring are separate.

`preflight_serialization_error.log` preserves an initial JSON encoding failure
before any qualification solve. The serializer was corrected before the
qualification manifest and numerical dispatch. No failed numerical result was
replaced.

Rebuild the summary and figures from the committed JSON:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/shape_continuation/SC-047-coupled-continuation/report.py
```

To rerun the numerical experiment while preserving these records, copy the
five driver scripts (`qualify.py`, `atlas.py`, `strategies.py`, `topology.py`,
`report.py`) into a fresh sibling directory under
`results/validation/shape_continuation/`. Execute them in that order with the
same environment. The scripts write to their own directory and locate the
shared SC-035 update and repository sources by relative paths. They require
no uncommitted NPZ arrays. Qualification and topology refuse to overwrite
existing result files; strategies resume completed arms from their records.
Manifests record source hashes, inputs, settings and commands.
