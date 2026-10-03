# FM-003: model-free lifting check and early-stage basin census (paired contrast-13.3 C)

Frozen before execution, 2026-10-03. **APPROVED** by the user ("yes") after the
[outsider proposal](02_proposals/01_lifting_and_census.md). Baseline: current
`feature/shape-frequency-continuation` head (`27904e7d` or later; record the hash). No new
branch or worktree. Owner: Codex. Independent reviewer: unassigned. Production defaults,
CI-001/FM-001/FM-002/RB-001 sources and archived results are not changed.

## Question

Is the paired contrast-13.3 C failure an **early-stage search failure** (the data, through the
shape model, determine the shape, but local continuation from the fitted circle misses the
basin), rather than an information failure?

## Fixed definitions

- **Case:** `modal__c13.3__development_c`. Control case: `modal__c4__development_c`.
- **z1:** the CI-001 `stage_1_damped` endpoint of the case
  (`results/validation/cleaned_interfaces/CI-001/runs/<case>/stage_1_damped.json`).
- **Stage-2 problem:** the CI-001 `stage_2_damped` operation from `CumulativePolicy.operations`
  (damped paired observations at 0.5 and 0.75 GHz, γ = 0.25; M = 5; K_geometry = 12; CI-001
  weights, tolerances, acceptance rules and N512/1024 nodal resolution; spline projected
  update; `nodal_kress`; `device=auto`).
- **Converged stage 2:** the same problem with `iterations=200` and stage quota 10,000 units,
  so each run ends at a local stop (no decreasing step, gradient, relative step or numerical
  refusal), not at the 22-iteration cap. Every stop reason is recorded.
- **Distance:** phase-aligned arclength RMS between curves, in mm (as in FM-001 stage
  distances). Truth is used only for scoring after all runs of a census finish.
- **Full data:** the FM-001 qualified 24 × 24 catalogs (`fm001.full_problem`), damped, same
  frequencies, same z1.

## Phases (order fixed; about 7 h on the RTX 5090 host)

### Phase L: lifting check (CPU, about 2 min, evaluation only)

    python -m experiments.cleaned_interface.fm003_lift --output results/validation/cleaned_interfaces/FM-003/lift

**Gates:** disk |S_nn| − 1 ≤ 1e-10; unitarity and symmetry errors ≤ 1e-8 at 0.25, 0.5 and
0.75 GHz; doubling nodes changes data ≤ 1e-8. Record the lift table. Expected, not gating:
a usable lift (ambiguity < 1e-3 and paired residual < 1e-2) only at 0.25 GHz with N = 2.

### Phase 0: replay (minutes)

Run the CI-001 stage-2 operation from z1 with CI-001 settings.
**Gate:** 4 accepted steps, stop `no_decreasing_step`, final loss 0.004623098588 to relative
1e-10, identical curve coefficients. Then run the converged stage 2 from z1 and record it as
census start 0.

### Phase 1: paired census, contrast-13.3 C (512 starts, cap 4 h)

Start i (i = 1…511) = z1 moved by a normal displacement through the same projected trial map
used for LM steps:

    h(s) = σ₀ Σ_{j=0..5} (α_j cos(2πjs/L) + β_j sin(2πjs/L)),   α_j, β_j ~ N(0, (ρ/(1+j))²)

σ₀ = L/2π of z1, s = arclength; ρ = (0.05, 0.1, 0.2, 0.4)[i mod 4]. For i mod 8 ≥ 4 the
moved curve is also rotated by ψ ~ U(0, 2π) about its area centroid. Random generator:
`numpy.random.default_rng(20261004 + i)`. A start failing geometry validation is redrawn with
sub-seed `(20261004 + i, attempt)` up to 10 times; every refusal is recorded. Each start runs
the converged stage 2 with its own ledger.

Clustering (truth-free): endpoints whose losses agree within 2% and whose distance is below
0.5 mm belong to one cluster (single linkage). Report clusters sorted by loss: size, share,
loss, stop reasons, and (after the census) the representative's distance to truth.

### Phase 2: continuation from the census winner (≤ 15 min)

Select the endpoint with the **lowest stage-2 loss** (ties: lowest start index). Run the CI-001
operations from `stage_3_damped` onward from it, unchanged, with the global cap reduced by what
CI-001 spent through stage 2 (162 units, 15.5 s). The census cost is reported separately and
added in the total. Score with the frozen paired recovery contract.

### Phase 3: full-data census, contrast-13.3 C (256 starts = the first 256 of the Phase 1 list, cap 1.5 h)

### Phase 4: paired census, contrast-4 C (256 starts, same construction from its own z1, cap 1.5 h)

If a cap is reached, stop at the completed prefix of the fixed start list and report n.
Workers and frequency threads are execution settings; record them and check one start for
identical results across the settings used.

## Gates and readings (pre-registered)

- **G1 (search or information):** the lowest-loss Phase-1 cluster lies within 5 mm of the
  truth. FM-001's full-data stage-2 endpoint (3.49 mm) sets this scale.
- **G2 (recovery):** Phase 2 recovers the C under the frozen paired contract.
- **G3 (controls):** report the share p of starts reaching the lowest-loss cluster and the share
  within 5 mm of truth for Phases 1, 3 and 4, each with a Wilson 95% interval, plus the share of
  z1's own cluster. Prediction: p(full) > p(paired) and p(c4) > p(c13.3).

| G1 | G2 | Reading |
|---|---|---|
| yes | yes | Search failure: a global stage 2 recovers the paired C; expected cost ≈ census cost / hits |
| yes | no | The right stage-2 basin is not enough; report where the continued run departs |
| no | — | A lower-loss wrong minimum exists at stage 2: information or non-uniqueness under this representation; claim rejected |
| none within 5 mm | — | Inconclusive for search; report the 95% upper bound on p |

## Constraints

- No change to ρ, start counts, seeds, clustering thresholds, caps or the policy after any
  result is seen. Truth only for scoring.
- Damped data are the existing synthetic catalogs; no realism claim is made.
- New directories under `results/validation/cleaned_interfaces/FM-003/`; source and input
  seals; every refusal, timeout and failed start retained.
- Results open `iteration_21/01_results.md`. Commit and push after the run, as `AGENTS.md`
  requires.

## Not tested here

A two-stage census (perturbing the localized circle through stages 1–2), the same question
for the star or thin C, and any change to the production policy.
