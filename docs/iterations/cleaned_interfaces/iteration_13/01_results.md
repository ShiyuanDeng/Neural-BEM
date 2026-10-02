# NU-005 results: certificates decide every validity check on the six core cases

2026-10-02. Result of the [pre-registered plan](03_plan.md). The user replied "keep up to NU005".

## Decision

**Retained, with no sampled fallback.** `NU-005` (modal Müller physics, the NU-003 spectral map and
the certificate tiers) passes both parts of the fixed rule:
- **NU-001 rule against nodal CI-001:** 6/6 matches and no drift flag.
- **Decision identity with NU-004-MS:** the same accepted steps in every stage and the same units
  in every case. The final curves are also bit-identical to MS (distance 0).

The tiers decided all **1,131** validity checks in the six runs. The sampled test was never
reached. By the plan's outcome rule, **validity was decided without samples on the six core
cases.** No check refused a trial, so this covers acceptance only (see the last section).

## Stage 1: offline pre-check (passed)

The pre-check covered 72 states (the last accepted state of every MS stage) with 12 random steps
each, 864 trials in all. Both gates held:
- every trial gave the same decision as the sampled map, with bit-identical candidates;
- every one of the 2,193 certified curves also passed the shadow sampled test.

The fallback decided 7.0% of the 2,444 curves checked:

| Step size | Increment | Full | Sampled accept | Sampled refuse |
|---|---:|---:|---:|---:|
| 10⁻⁷ m | 648 | 0 | 0 | 0 |
| 1 mm | 142 | 506 | 0 | 0 |
| 6 mm | 74 | 553 | 9 | 4 |
| 18 mm | 33 | 317 | 88 | 70 |

The 74 refusals were all `moved_coarse` self-intersections, which the tiers cannot refuse by
design. Tiered checks took 1,568 s in total, against 27 s for the sampled tests.

Record: [precheck.json](../../../../results/validation/cleaned_interfaces/NU-005-precheck/precheck.json).

## Stage 2: six-case campaign

| Core case | Status (MC / MS / nodal) | Trials | Increment | Full | Fallback | Certificate s | Wall s (MC / MS / nodal) | Final vs MS / σ₀ |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `wrong_circle` | PASS ×3 | 4 | 12 | 0 | 0 | 0.1 | 15 / 16 / 27 | 0 |
| `peanut` | PASS ×3 | 33 | 90 | 9 | 0 | 2.2 | 37 / 36 / 76 | 0 |
| `circle_to_c` | PASS ×3 | 47 | 91 | 50 | 0 | 9.7 | 49 / 40 / 77 | 0 |
| `hook` | PASS ×3 | 62 | 122 | 64 | 0 | 18.5 | 60 / 42 / 79 | 0 |
| `circle_to_star` | REGRESSION ×3 | 40 | 102 | 18 | 0 | 4.4 | 52 / 48 / 92 | 0 |
| `kite` | PASS ×3 | 191 | 259 | 314 | 0 | 67.7 | 177 / 112 / 222 | 0 |
| **Sum** | | **377** | **676** | **455** | **0** | **102.6** | **390 / 293 / 573** | |

The counts cover three checks per trial (moved coarse, moved fine, candidate). There were no
area refusals and no certificate construction failures, and the window-128 escalation was never
used: every full-tier acceptance came at window 64. `circle_to_star` is a frozen comparison
regression in all three arms, so it counts as a match. All final audits pass, every case
recovers, and every physics receipt is `cuda-modal`. The NU-005, NU-004-MS, NU-003 and CI-001
seals pass `verify`, and no log has a traceback.

**Timing.** MC takes 390 s against MS's 293 s. The 98 s difference is almost all certificates
(102.6 s, inside trial time: 111.6 s against MS's 10.0 s). Geometry preparation is unchanged
(150 s against 154 s). MC is still 1.5× faster than nodal. These are single runs, not matched
runtime pairs.

Records: [campaign](../../../../results/validation/cleaned_interfaces/NU-005/),
[drift, decision and tiers](../../../../results/validation/cleaned_interfaces/NU-005-drift/drift.json),
[logs](../../../../results/validation/cleaned_interfaces/NU-005-logs/).

## Predictions against outcome

| Prediction | Outcome |
|---|---|
| Decision-identical to MS | Held, and the final curves are bit-identical |
| Fallback > 0 and < 20%, in the K = 192 stages of `hook`, `kite`, `circle_to_c` | **Wrong:** 0. Real LM steps are much smaller and smoother than the random full-band steps of the pre-check: the increment tier alone decided 60% of checks, against 37% in the pre-check |
| Wall time 400–900 s | 390 s, just below the range. Certificates cost 102.6 s, not the 10–100× per-trial factor applied to every trial |

## Deviation from the plan

`nu005.drift` reuses the name `mc` for both the campaign path and the case table, so it raises a
`TypeError` after the case audits. `nu005.py` is hashed by the NU-005 seal, so it was not edited.
[`nu005_drift.py`](../../../../experiments/cleaned_interface/nu005_drift.py) carries the same audit
with the names separated. The rule is unchanged.

## What this establishes, and what it does not

- **Established, on the six core cases:** the inverse runs with node-free physics, a spline-free
  trial map and validity accepted by coefficient certificates. Its decisions are bit-identical to
  NU-004-MS. No polygon self-intersection test and no sampled speed test was run in the fit.
- **Not established:**
  - **Refusing without samples.** No trial was refused, so the fallback's refusal path was not
    exercised. In the pre-check, 74 self-intersecting moved curves were refused only by the
    sampled test. A node-free refusal needs a certificate of non-simplicity, which no tier provides.
  - **Fully grid-free geometry.** Grids remain as transform engines: the normal move h(α)n and
    its FFT fit, the eq. 9 quadrature, `log_modulus`'s proposed interval β, and the `measure`,
    `metric` and `speed_ratio` diagnostics. This is the proposal's definition of node-free, not
    the absence of grids.
  - All-36 retention, and matched runtime.

## Proposed next (not run)

1. **NU-006: cheaper quadrature** (iteration 12): a type-1 NUFFT in place of the dense
   (K+1) × count product, targeting MS geometry preparation at or below MN's 64 s.
2. **Certificate reuse.** Modal physics already builds the |W|² certificate (`ModalGeometry.log_interval`)
   for every curve it evaluates, and the candidate's tier-3 certificate repeats that work. Sharing
   the reciprocal would remove most of the 102.6 s. It would also let the window come from the
   physics profile.
3. **Node-free refusal.** A crossing z(s) = z(t) can be proved to exist by an interval Newton
   (Krawczyk) test on the two-variable system, seeded at the polygon crossing. This is a rigorous
   existence proof that does not rely on the polygon. Test it on the pre-check's 74
   self-intersecting moved curves, with the sampled test as the reference.
4. **All-36 campaign** with the NU-005 update, reported against nodal 28/36 and CI-001-modal-r2.
