# NU-004 results: modal Müller physics with the spline-free map retains nodal on the six core cases

2026-10-02. Result of the [pre-registered plan](03_plan.md). The user replied "yes go".

## Decision

**Retained.** `NU-004-MS` (modal Müller physics plus the NU-003 spline-free increment map)
matches nodal CI-001 on 6/6 core cases and has no drift flag. The rule is the NU-001 rule,
unchanged. The `NU-004-MN` control (modal plus the CI-001 spline map) also matches 6/6. The
attribution branch of the plan therefore does not apply.

All three arms are decision-identical: the same accepted steps in every stage, the same
9,677 fit units, and RMS equal to three significant figures. MS final curves lie within
5.9·10⁻⁸ σ₀ of both MN and nodal. All three plan predictions held.

## Per case

| Core case | Status (nodal / MS / MN) | Recovered | max r_σ | RMS (mm) | Units | MS final vs nodal / σ₀ | Wall s (nodal / MS / MN) |
|---|---|---|---|---:|---:|---:|---|
| `wrong_circle` | PASS / PASS / PASS | all | 1.000 | 7.58·10⁻⁶ | 266 | 0 | 27 / 16 / 10 |
| `peanut` | PASS / PASS / PASS | all | 1.012 | 2.07·10⁻³ | 1,152 | 1.8·10⁻¹⁰ | 76 / 35 / 23 |
| `circle_to_c` | PASS / PASS / PASS | all | 1.154 | 9.76·10⁻⁴ | 1,167 | 3.2·10⁻⁹ | 77 / 40 / 27 |
| `hook` | PASS / PASS / PASS | all | 1.182 | 1.39·10⁻³ | 1,201 | 7.9·10⁻⁹ | 79 / 42 / 30 |
| `circle_to_star` | REGRESSION ×3 | all | 1.092 | 1.88·10⁻² | 1,391 | 1.1·10⁻⁹ | 92 / 48 / 30 |
| `kite` | PASS / PASS / PASS | all | 1.078 | 1.18·10⁻² | 4,500 | 5.9·10⁻⁸ | 222 / 112 / 78 |

`circle_to_star` is a frozen comparison regression in all three arms, so it counts as a
match. All final audits pass. Every MS and MN physics receipt is `cuda-modal`, including the
damped stages. Both NU-004 seals, NU-003 and CI-001 pass `verify`, and no log has a
traceback.

## Timing (six-case sums, single runs)

| Arm | Total wall (s) | Fit + localization (s) | Geometry preparation (s) | Geometry trial (s) |
|---|---:|---:|---:|---:|
| Nodal (CI-001: Kress + spline) | 572.8 | 488.6 | 64.8 | 5.41 |
| MS (modal + spectral) | 292.6 | 265.5 | 153.6 | 9.97 |
| MN (modal + spline) | 198.5 | 179.4 | 64.2 | 5.30 |

The physics work is identical in MS and MN: 379 s of evaluations summed over four
frequency threads, with every stage's seconds within 1%. The 94 s by which MS is slower
than MN is almost entirely geometry preparation (+89 s). With modal physics, the
quadrature's cost is **52% of MS wall time**. MS is 2.0× faster than nodal and 1.5× slower
than MN. These are single runs, not matched runtime pairs.

Records: [MS](../../../../results/validation/cleaned_interfaces/NU-004-MS/),
[MN](../../../../results/validation/cleaned_interfaces/NU-004-MN/),
[drift, decision and identity](../../../../results/validation/cleaned_interfaces/NU-004-drift/drift.json),
[logs](../../../../results/validation/cleaned_interfaces/NU-004-logs/).

## What this establishes, and what it does not

- **Established, on the six core cases.** The inverse runs with node-free physics and a
  spline-free geometry update, and makes the same decisions as the nodal pipeline at half its
  wall time.
- **Not established.**
  - A **fully** node-free inverse: the trial map still runs the sampled self-intersection
    test (`project(validate=True)` and `FourierCurve.validate`).
  - All-36 retention. Modal has two known contrast-13.3 C stops (iteration 07), which these
    six cases do not test.
  - Matched runtime.

## Proposed next (not run)

1. **NU-005: validity without samples.** Place NU-001's certificate tiers (exact area, then the
   O(K) incremental certificate of Lemmas 3–4, then the full |W|² certificate) in front of the
   sampled test, which remains the fallback. Measure how many trials still need the fallback.
   Removing it would require the full certificate to decide every remaining case.
2. **NU-006: cheaper quadrature.** Replace the dense (K+1) × count product with a type-1 NUFFT,
   and make the crop-error record optional. Target: MS geometry preparation at or below MN's 64 s.
   That would bring MS to about MN's 199 s with no change in decisions.
3. **All-36 MS campaign**, after NU-006, reported against nodal 28/36 and CI-001-modal-r2.
