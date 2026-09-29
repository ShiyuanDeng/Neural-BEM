# MA-002 plan: does the frozen pipeline survive a denser-than-host target?

2026-09-29. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
Authority: the user's instruction of 2026-09-29, "check out latest vision doc.
use claudes findings as a reference … go next steps as you see fit, you have
my approval to stop only until genuine good news or hit every wall". Frozen
before any MA-002 inverse outcome was seen. No default, branch or worktree
changes.

## Why this question

MA-001 (reproduced on current code as
[MA-001R](../../../../results/validation/modal_atlas/MA-001R/README.md)) found
that the vision's §7.2 resonance mechanism is exact on the circle, including
its 0.1 constant, but only exists when `k_i > k_e`. It concluded that the
mechanism cannot explain the kite/C failures, because the whole continuation
campaign uses plastic (ε = 3) in sand (ε = 6), contrast `k_i²/k_e² = 0.5`.

That leaves a gap the vision cares about. GPR targets denser than the host are
common (water-filled voids or pipes, wet inclusions, rock). For a 5 cm disk in
the catalog band (0.25–2.5 GHz in ε = 6 sand, `k_e R ≈ 0.64–6.4`), the exact
Mie poles are ([pole census](../../../../results/validation/modal_atlas/MA-002/circle_pole_census.json)):

| Contrast | In-band poles | Q > 10 | Q > 100 | Q > 1000 |
|---:|---:|---:|---:|---:|
| 2 | 15 | 1 | 0 | 0 |
| 4 | 23 | 12 | 3 | 0 |
| 13.3 (water in sand) | 75 | 73 | 42 | 31 |

No inverse in this repository has been run with `k_i > k_e` on the GPR
benchmark. Iteration 04's contrast-10 "breakdown" was measured on the unit
circle only (SC-016 H2), and its contrast-10 controller runs (SC-017) were
never completed. So the cheapest decisive question is:

> **Does the frozen SC-050 policy still recover the benchmark scenes when the
> target is denser than the host?**

If it does, the resonance mechanism has no decision value on this benchmark
and the line stops. If it does not, the failure is a concrete target for the
vision's claim that modal (resonance) structure explains finite validity, and
the conditional diagnosis below runs.

## Frozen design

- **Policy.** SC-050's selected `localize_low`, unchanged: the same
  localization search, 0.25 GHz M=1 warm-up, SC-049 prefix, releases M = 11,
  15, 19 on all 19 frequencies, fixed M = 25, 31, 37 with the one-off
  cleanup, SC-050's `setup` and `localize` functions imported from its frozen
  `run.py`. Cap 13,412 fit+localization units and 1,800 s per attempt.
- **Only change: the interior permittivity.** The contrast is set once per
  process (the driver overrides `atlas_cases.contrast`, which every frozen
  entry point calls), for data generation, localization, fitting and audits
  alike. The material is known to the inverse, as in the whole campaign.
- **Scenes.** SC-050's `development_c`, `shifted_star` and `new_asymmetric`
  truths and initial circles (C, star-shaped, asymmetric), clean data.
- **Contrasts.** 0.5 (matched control in this harness), 2, 4 and 13.3.
  Twelve attempts, one each, no restarts, no retuning.
- **Input qualification.** Observations at 2,048 nodes; 1,024/2,048 relative
  field discrepancy ≤ 1e-8 at every frequency (SC-050's gate). SC-050's
  cross-check against SPD's Kress oracle is only available at contrast 0.5,
  so the solver is instead checked against exact Mie series on a 5 cm disk at
  every contrast and all 19 frequencies (relative error ≤ 1e-8). An input
  that fails is withheld and reported.
- **Truth boundary.** As SC-050: the fitting path reads observations and the
  initial circle only; truth is loaded after the final audit, for scoring.
- **Recovery.** SC-050's definition: final audit passes, RMS ≤ 1 mm,
  Hausdorff upper bound ≤ 2 mm, catalog residual ≤ 0.003 at every frequency.

## Decisions

- **D1 — all nine attempts at contrast 2, 4 and 13.3 recover.** The frozen
  pipeline is robust to `k_i > k_e` on this panel. Record the resonance line
  as having no decision value on this benchmark; report work and any
  quantitative differences. No successor from this line.
- **D2 — some fail.** Classify each failure by stage and stop reason (the
  implementation principles' categories). Then run the conditional
  diagnosis MA-002b on the failed attempts only.
- The contrast-0.5 control must recover all three scenes, as in SC-050.
  Otherwise the harness differs from SC-050 and no contrast comparison is
  made until that is explained.

## Conditional diagnosis MA-002b (runs only under D2)

Question: at the state where the failed attempt stopped making useful
progress, is finite validity shortened near scattering poles of that iterate?

1. Take the last accepted state of the failing stage, and its active
   frequencies, from the attempt's saved records (no refit).
2. Find the iterate's scattering poles near the band with a contour-integral
   (Beyn) eigen-solver on the existing Müller system at complex `k`.
   Qualify each pole by 512/1024 agreement and by reproducing the exact Mie
   poles on a disk first.
3. At each active frequency, measure the linearization horizon of the
   stage's own update space along its first saved LM direction (MA-001's
   10% criterion), and compare it with (a) SC-016's smooth law `≈ 0.1/k` and
   (b) the single-pole law `0.1 |k − k*| / |∂k*|` from the nearest pole.
4. Report the rank correlation between horizon and pole distance across
   frequencies, and whether rejected LM trials concentrate at stages or
   frequencies near poles.

This diagnosis explains; it does not change the pipeline. Any fix it
suggests is a separate, pre-declared comparison against simple controls
(for example smaller steps, or a finer frequency ladder), following the
competent-baseline rule.
