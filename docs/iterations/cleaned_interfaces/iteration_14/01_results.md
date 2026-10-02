# NU-006 results: the GPU-batched prepare is decision-identical and cuts wall time by 38%

2026-10-02. Result of the [pre-registered plan](03_plan.md). The user replied "yes go".

## Decision

**Retained and adopted as the default `prepare`.** `NU-006` (arm MG: the NU-005 update with all
its `prepare` projections batched on the RTX 5090) passes both parts of the fixed rule:
- **NU-001 rule against nodal CI-001:** 6/6 matches and no drift flag.
- **Decision identity with NU-005:** the same accepted steps in every stage and the same units in
  every case.

The final curves lie within 2.1·10⁻¹⁰ σ₀ of NU-005. They are not bit-identical, as expected from
GPU rounding. All three predictions held.

## Stage 1: offline pre-check (passed)

On 72 NU-005 states, the worst column difference was 9.7·10⁻⁹ (gate 10⁻⁷) and the worst
base-projection difference 3.0·10⁻¹⁵ σ₀ (gate 10⁻¹²). There were no fallbacks. `prepare` took
44.1 s on the CPU and 0.92 s batched, 48× faster. Record:
[precheck.json](../../../../results/validation/cleaned_interfaces/NU-006-precheck/precheck.json).

## Stage 2: six-case campaign

| Core case | Status | Prepare s (MG / MC) | Wall s (MG / MC / MS / nodal) | Final vs MC / σ₀ |
|---|---|---|---|---:|
| `wrong_circle` | PASS | 0.27 / 9.4 | 6 / 15 / 16 / 27 | 0 |
| `peanut` | PASS | 0.52 / 19.7 | 17 / 37 / 36 / 76 | 1.4·10⁻¹¹ |
| `circle_to_c` | PASS | 0.55 / 20.4 | 29 / 49 / 40 / 77 | 1.3·10⁻¹¹ |
| `hook` | PASS | 0.56 / 19.8 | 40 / 60 / 42 / 79 | 3.2·10⁻¹¹ |
| `circle_to_star` | REGRESSION (all arms) | 0.71 / 29.9 | 22 / 52 / 48 / 92 | 8.4·10⁻¹² |
| `kite` | PASS | 1.29 / 50.6 | 127 / 177 / 112 / 222 | 2.1·10⁻¹⁰ |
| **Sum** | | **3.9 / 149.8** | **242 / 390 / 293 / 573** | |

Every `prepare` ran batched: 310 of 310, with no CPU fallback. The validity tiers again decided all
checks, with no sampled fallback. All final audits pass and every case recovers. Every physics
receipt is `cuda-modal`. The NU-006, NU-005, NU-004-MS and CI-001 seals pass `verify`, and no log
has a traceback.

**Where the time now goes.** MG's 242 s include **104 s of NU-005 certificates** (43%, inside trial
time) and about 9 s of other trial work. Most of the rest is modal physics. With the sampled
validity test instead of the certificates, the same pipeline would take about 138 s: 2.1× faster
than MS, and 4.2× faster than nodal.

These are single runs, not matched runtime pairs.

Records: [campaign](../../../../results/validation/cleaned_interfaces/NU-006/),
[drift, decision and identity](../../../../results/validation/cleaned_interfaces/NU-006-drift/drift.json),
[logs](../../../../results/validation/cleaned_interfaces/NU-006-logs/).

## Predictions against outcome

| Prediction | Outcome |
|---|---|
| Decision-identical to NU-005, final curves within 10⁻⁸ σ₀ | Held (≤ 2.1·10⁻¹⁰ σ₀) |
| Geometry preparation ≤ 15 s | Held: 3.9 s, 38× below NU-005 |
| Wall time 230–270 s | Held: 242 s |

## What this establishes, and what it does not

- **Established, on the six core cases:** the spline-free geometry update no longer costs time.
  The current pipeline (modal physics, spline-free map, certificate validity, batched GPU
  `prepare`) runs in 242 s against nodal's 573 s, with nodal's decisions.
- **Not established:** all-36 retention; matched runtime; CPU-only hosts (the `prepare` falls back
  to the sequential path, which is slower but has the same mathematics).

## Proposed next (not run)

1. **Certificate reuse** (now the largest single item, 104 s). Modal physics already builds a
   certified log|W|² for every curve it evaluates. Share the reciprocal Y between the candidate's
   tier-3 check and physics, or run the certificate's 2-D convolutions on the GPU.
2. **Batched LU across frequencies** and **GPU Graf waves**, for the physics remainder.
3. **All-36 campaign** with the NU-006 update, reported against nodal 28/36 and CI-001-modal-r2.
