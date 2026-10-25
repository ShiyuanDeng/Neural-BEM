# GU-002: CUDA slider preparation and stronger level penalties

## Questions

1. Can CUDA speed up slider preparation, including its solve, while preserving
   the geometry update and recovery of hook c13.3? How much faster is the
   slider fit than the CPU-preparation slider and the spectral baseline there?
2. Can a stronger level penalty make the N-update recover hook c13.3?
3. If both work, do these two methods recover the other hard TG-002 cases?

**Status: approved 2026-10-25.** After a grilling session on the GPU part
(decisions below), the user said: “okay. now /mattpocock-skills:implement the
plan with yes to allyour questions. i expect to see: speedups ratio on hook
c13.3 against spectral baseline and cpu slider; and how three weighs perform on
that scene for soft constraint.” “Soft constraint” is the level penalty.

The requested ratios need two same-machine reference fits that the earlier
draft excluded: a spectral baseline and a slider with CPU preparation. They are
added below; nothing else changes in scope.

## Decisions from the grilling session

The user accepted all eight recommendations. Informal timings at the saved
K=192 states (one BLAS thread) informed them: CPU preparation about 0.35 s
(rows 0.10 s, products 0.17 s, lstsq 0.06–0.07 s).

On CUDA the rows took under 1 ms and the products 11 ms. The solve took 17 ms
with `eigh` but 135 ms with `gesvd`, which is slower than the CPU solve.

1. Solve with symmetric `torch.linalg.eigh`, not `gesvd`. It keeps the same
   rank as NumPy at all three states, with errors of at most 5e-11.
2. Keep the dense float64 products on CUDA; no FFT shortcut.
3. Use CUDA at every band; no CPU switch for small systems.
4. Prepare fresh each time; no reuse of the matrix across stage entries.
5. Time the CPU reference with one BLAS thread, the fit setting.
6. Run the slider hook fit alone on the GPU, before the penalty fits.
7. Physics stays the limit: GU-002 changes no physics setting. Record the
   preparation share of the fit time.
8. Keep the “faster on both large states” requirement; report the speedup.

## Agreed scope

- Use the existing `organised` branch and worktree, pulled through
  `670524839`. Create no branch or worktree.
- Keep two separate methods: slider, and N-update with a stronger **level
  penalty**, the glossary's term for the soft constraint.
- Use existing modal CUDA without repeating its validation. New GPU work is
  confined to slider preparation, **including the solve**.
- Try penalty multipliers **0.1, 1 and 10** on **hook__c13.3**, one fit each.
  Each multiplier scales that run's data loss at stage entry, as before.
- Require hook recovery for the penalty direction; choose the smallest tested
  multiplier that recovers. Lower speed unevenness alone does not suffice.
- Expand only if both directions work. The later panel is hook__c13.3 plus
  aphex_twin__c0.5, aphex_twin__c4 and aphex_twin__c13.3.
- Keep TG-002 inputs, one centred start, no localization, modal Müller physics,
  default continuation and the existing recovery criteria.

## Existing evidence

[GU-001](../../../../results/validation/cleaned_interfaces/GU-001/README.md)
ran on the Mac CPU. Slider recovered hook c13.3 with about 0.0002 mm RMS.
Its 497 s fit included 37.83 s in 142 preparations and 0.72 s constructing
trials. That timing share need not hold with CUDA physics.

The N-update failed in stage_3_damped. Its last accepted curve had data loss
0.00582760 and penalty loss 0.0000123127: about 0.211% of data loss. Its
multiplier was 0.01, fixed against each stage's entry data loss.

The level penalty controls speed unevenness, not minimum separation. A physics
failure still ends the stage before combined loss comparison. Failure handling
and the existing stopping rules are not additional experimental variables.

## Direction 1: slider preparation on CUDA

The change belongs in B6 preparation in
[`slider.py`](../../../../solvers/bem_inverse/geometry_update_methods/slider.py),
selected through
[`geometry_selection.py`](../../../../solvers/bem_inverse/geometry_selection.py).

- Move dense construction, weighting, matrix products and the pseudoinverse
  solve to CUDA, using float64 and complex128 where appropriate.
- Preserve xi=10, Q=32K, the normal-matrix formulation and update coordinates.
  Keep the existing CPU implementation as the reference execution path.
- Solve with CUDA `torch.linalg.eigh`. The normal matrix is symmetric, so its
  eigenvalue sizes are its singular values. Match NumPy 2.0.2
  `lstsq(rcond=None)`: keep eigenvalues larger in size than float64 machine
  epsilon times 4K+2 times the largest. Apply the kept eigenvectors directly;
  do not form an explicit inverse.
- The circle has a true null direction. Installed PyTorch 2.8.0 CUDA
  `lstsq` supports only a full-rank solve, so it is unsuitable.
- Keep curve sampling, normalized-arclength basis construction, trial checks
  and the stored NumPy derivative format. Transfer inputs once into the dense
  preparation and return the solved derivative array once.
- Record actual preparation device, retained rank and component timings.
  An explicit CUDA request must not silently become a CPU solve.

Use three saved GU-001 slider stage-entry curves for the focused comparison:

| State | Storage band K | Update band M | Purpose |
|---|---:|---:|---|
| stage_1_damped entry | 8 | 3 | Small constant-speed curve and singular direction |
| release_M11 entry | 192 | 11 | Large system at shape release |
| fixed_M67 entry | 192 | 67 | Large system with many update directions |

Compare CPU and CUDA on this same RTX 5090 machine. Require matching retained
rank and relative Frobenius error of prepared directions at most 1e-6. Apply
one deterministic bounded update per state; require maximum sampled curve
difference at most 0.001 mm. Also record normal-motion and relative-speed
variation differences. These checks involve no inverse fits.

Time total preparation including sampling, synchronization and transfers;
separate dense construction/products, solve and transfers. Record first use
separately, then take three warmed measurements per state/device and compare
medians. Run these timings without concurrent fits.

Success requires these numerical comparisons and faster CUDA preparation on
both large states. Report small-state overhead without requiring a speedup
there. If accuracy or large-state speed fails, preserve the evidence and stop
this direction before its hook fit. Do not change cutoffs, precision, solvers
or comparisons after seeing the result.

If the comparison succeeds, run three hook c13.3 fits on this machine, one at
a time with nothing else running, all with CUDA physics:

1. spectral, the default method, as the baseline;
2. slider with CPU preparation (`preparation_device='cpu'`);
3. slider with CUDA preparation, which must retain TG-002 recovery.

Report total fit time, work units, seconds per unit, preparation time and its
share, and the time to reach release_M11, which both methods reach. Spectral
fails in release_M11, so its total time is not a like-for-like ratio. If the
comparison fails, these three fits are skipped.

## Direction 2: stronger level penalties on hook

Make the multiplier an explicit `LevelPenalty` setting, preserving 0.01 as the
default. Pass it through benchmark settings and saved configuration; each
weight gets a fresh run directory. Avoid runtime mutation of a global constant.

Run N-update once at each multiplier **0.1, 1, 10**, with existing CUDA physics.
Each stage sets the coefficient from its own entry data loss and holds it
fixed until the next stage. The N-update geometry is unchanged.

Reuse GU-001's saved 0.01 run as reference. At that unchanged endpoint, the new
settings would contribute 2.11%, 21.13% and 211.28% of data loss. These are
fixed-curve calculations, not predictions of the new trajectories.

Use existing records for data loss, penalty loss, stage weight, speed
unevenness, speed ratio, actual normal movement, recovery, work and time.
Compare losses only at matching stages and frequency catalogs. A stronger
penalty also affects the combined gradient and stopping behavior.

Success requires at least one weight to meet all existing TG-002 recovery
criteria: passed endpoint checks, RMS at most 1 mm, Hausdorff upper bound at
most 2 mm, and every frequency residual at most 0.003 for these noiseless
cases. Choose the **smallest recovering multiplier**, without further tuning.

Complete the three penalty runs independently of the GPU slider outcome.
If no weight recovers, report their failures and stop before expanding to Aphex.
Passing the old failure stage or completing the schedule alone is insufficient.

## Conditional four-case comparison

Only if slider preparation is faster and agrees with the CPU reference,
the GPU slider recovers hook, and a stronger penalty recovers hook:

1. Freeze the slider implementation and selected penalty multiplier.
2. Run the two separate methods once each on the three Aphex cases.
3. Reuse the successful hook runs to complete the four-case table.

Scope: **at most six preliminary inverse fits** (three timing fits plus three
weights), then **six additional fits** if both directions work. No extra hook
rerun is needed. This does not test retention of the other 26 TG-002 recoveries.

## Execution and evidence

- Use explicit CUDA, four frequency threads per fit and at most two concurrent
  case workers. Time saved-state preparation in isolation before fits. Run the
  three timing fits one at a time, then the penalty fits two at a time. Use
  single-threaded BLAS to avoid nested CPU oversubscription.
- Keep the 13,412-unit and 1,800-second fit limits and existing 300-second
  endpoint allowance. No automatic reruns, extra weights, budget extensions
  or alternate starts follow a failure.
- Add a small GU-002 driver under `experiments/benchmark/`; keep numerical
  code in `solvers/bem_inverse/`. Preserve GU-001 and NR-001 evidence.
- Save settings, exact code commit, actual device, comparison errors, timings,
  retained rank and all fit/failure evidence under
  `results/validation/cleaned_interfaces/GU-002/`.
- Use only the focused slider comparison and existing slider/level-penalty
  checks, extended for the new device and explicit weights as needed. No broad
  test rerun or existing modal CUDA revalidation is included.
- Produce a short results table answering the three questions. Generate any
  useful curve illustrations from saved history, without additional fits.
- After each new experiment run, commit and push its code, documentation and
  results, including failures, to `organised`. Verify push and working-tree
  status. All implementation and runs await an instruction to begin.

The existing glossary covers the agreed terms. These are reversible numerical
and experiment choices, so no new ADR is needed.
