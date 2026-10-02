# NU-003 results: the spline-free increment map qualifies and reproduces nodal decisions

2026-10-02. Result of the [pre-registered plan](03_plan.md). The user replied "go".

## Decision

**Adopt the spectral increment map.** Both stages pass. Under the rule copied from
NU-001, NU-003 matches nodal on 6/6 core cases and has no drift flag on any case.
Beyond the rule, the runs are decision-identical to the archived nodal runs: the same
accepted steps in all 72 stages, the same fit units in every case (9,677 in total), and
final curves within 6.0·10⁻⁸ σ₀ of nodal.

## Stage 1: offline pre-check (72 states, 648 trials, none refused)

| Gate | Threshold | Measured | Pass |
|---|---|---|---|
| max \|T_spectral − T_spline\| / σ₀ | ≤ 10⁻⁵ | 3.0·10⁻⁶ | yes |
| spectral refines no worse than spline (floor 10⁻¹²) | ≥ 90% of trials | 100% | yes |
| max relative Jacobian column difference | ≤ 10⁻³ | 2.3·10⁻⁷ | yes |

The largest trial difference (kite, `release_M11`, 6 mm step) is spline error. At that
trial the spline's own coarse–fine difference is 4.0·10⁻⁶ σ₀, close to its 10⁻⁵
tolerance, while the quadrature's is 1.0·10⁻¹⁰. Median refinement differences are
1.7·10⁻¹⁴ (spectral) and 3.1·10⁻¹² (spline). Record:
[`NU-003-precheck/precheck.json`](../../../../results/validation/cleaned_interfaces/NU-003-precheck/precheck.json).

## Stage 2: six-case CUDA campaign

RTX 5090, `device=auto`, four frequency threads, one case at a time, `nodal_kress`
physics. Every run's receipt includes CUDA work. The campaign seal and the CI-001 seal
pass `verify`, and no log contains a traceback.

| Core case | Nodal status | NU-003 status | Recovered | max r_σ (nodal / S) | Same accepted steps | Final curve vs nodal / σ₀ |
|---|---|---|---|---|---|---:|
| `wrong_circle` | PASS | PASS | yes / yes | 1.000 / 1.000 | all stages | 0 |
| `peanut` | PASS | PASS | yes / yes | 1.012 / 1.012 | all stages | 1.9·10⁻¹⁰ |
| `circle_to_c` | PASS | PASS | yes / yes | 1.154 / 1.154 | all stages | 3.2·10⁻⁹ |
| `hook` | PASS | PASS | yes / yes | 1.182 / 1.182 | all stages | 8.0·10⁻⁹ |
| `circle_to_star` | REGRESSION | REGRESSION | yes / yes | 1.092 / 1.092 | all stages | 1.1·10⁻⁹ |
| `kite` | PASS | PASS | yes / yes | 1.078 / 1.078 | all stages | 6.0·10⁻⁸ |

`circle_to_star` is a frozen comparison regression in both arms, so it counts as a
match. All six final audits pass in both arms.

Records: [campaign](../../../../results/validation/cleaned_interfaces/NU-003/),
[drift and identity report](../../../../results/validation/cleaned_interfaces/NU-003-drift/drift.json),
[logs](../../../../results/validation/cleaned_interfaces/NU-003-logs/).

## Timing (six-case sums, single runs)

| Arm | Total wall (s) | Fit + localization (s) | Fit units | Geometry preparation (s) | Geometry trial (s) |
|---|---:|---:|---:|---:|---:|
| Nodal (CI-001) | 572.8 | 488.6 | 9,677 | 64.8 | 5.41 |
| NU-003 | 659.4 | 564.3 | 9,677 | 145.3 | 9.16 |

The work is identical, but geometry preparation is 2.2× slower and the total wall time
is 15% longer. The quadrature is a dense (K+1) × count product per projection, and the
crop-error record doubles it. These are single runs, not matched runtime pairs.

## What this establishes, and what it does not

- **Established.** The CI-001 trial map runs without splines, interpolation or
  arclength inversion, and gives the same decisions on the six core cases. The pre-check
  shows the spectral resampler is more accurate than the spline it replaces.
- **Measured, then interpreted.** NU-001 and NU-002 together show that the
  increment form, not node-freeness, is what controls drift. NU-003 keeps the increment
  and removes the nodes.
- **Not established.** All-36 retention (the six cases are a subset), a runtime gain
  (it is slower), or a fully node-free inverse. Two node-based pieces remain:
  1. `nodal_kress` physics;
  2. the sampled validity test inside the trial (`self_intersections` on the moved
     curve's grid), which NU-003 inherits unchanged.

## Proposed next (not run)

1. **NU-004: node-free inverse end to end.** Run NU-003 with the modal Müller backend in
   place of `nodal_kress` on the six core cases, under the same rule against CI-001-modal-r2
   and nodal. The derivative path needs no change, because the modal backend already takes the
   update's coefficient columns.
2. **Validity without samples.** Put NU-001's tiered certificate in front of the
   sampled test. In NU-001 its O(K) tier decided 61–62% of the trials that passed validity (163/261 in A, 266/439 in B).
3. **Cost.** Replace the dense quadrature with a type-1 NUFFT or a cheaper crop-error
   record. Target: geometry preparation at or below nodal.
