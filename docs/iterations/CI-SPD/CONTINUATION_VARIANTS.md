# Continuation-schedule variants and how they performed

2026-10-05. Read-only synthesis of recorded evidence; no fits or solves were
run. It lists every implemented or proposed change to the inverse
continuation schedule, grouped by the phase of the
[agreed schedule](CONTINUATION_SCHEDULE.md) it changes, with results on the
scenes each variant was actually tested on.

**Check the scene column before comparing numbers.** Only **TG-002** rows share the current contract:
centred 65 mm start, `localization none`, `modal_muller` + `certified_spectral`
and the unchanged recovery gates (audit passes, RMS ≤ 1 mm, Hausdorff upper
bound ≤ 2 mm, every residual ≤ 0.003). Legacy rows used other scenes, starts,
nodal Kress physics and budgets. They explain why the schedule has its current
form, but their scores are not comparable with TG-002 scores. **Case 8** is the
external GauGal cylinder: noisy data, one object 0.62 m off-centre, far start.

Status: **Default** (in `CumulativePolicy`), **Opt-in** (implemented, off by
default), **Retired**, **Not adopted** (tested; lost or failed its gate),
**Diagnostic** (run to explain, not to adopt), **Proposed** (not run).

## TG-002 scoreboard

| Variant | Phase changed | Cases | Recovered | Recovery change | Paired speed, common successes | Evidence |
|---|---|---:|---:|---|---|---|
| B: default policy | — | 30 | 26/30 | — | — | [ON-001](../cleaned_interfaces/iteration_31/01_results.md), [PC-001](../../../results/validation/cleaned_interfaces/PC-001/README.md) |
| E: required-accuracy exit | 4 | 30 | 26/30 | none | 1.546x vs B | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| DP-001 F: E + agreement damping, exact reuse, progress stop | stage control | 30 | 26/30 | none | 1.134x vs E | [DP-001](DP-001_results.md) |
| RG-001: E + decision-relative resolution gate | stage control | 30 | 26/30 | none; failures progress | 1.006x; suite 554 → 841 s | [RG-001](../cleaned_interfaces/iteration_31/05_results.md) |
| PC-001 N1: nodal physics + resolution response | stage control | 30 | 26/30 | none | median 157 s vs modal 31 s (backend differs) | [PC-001](../../../results/validation/cleaned_interfaces/PC-001/README.md) |
| G: reach clipping | stage control | 8 | 4/8 | none | 0.924x vs B | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| EW: working-frequency proposals on E | stage control | 8 | 4/8 | none | 0.890x vs E | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| CS-001: agreed four-phase schedule | 1, 3, 4 | 8 | 4/8 | −1 (`c_shape__c13.3`) | 1.499x vs control | [CS-001](CS-001_results.md) |

The same four cases fail under every variant: `aphex_twin` at all three
contrasts and `hook__c13.3`. No variant has recovered any of them within the
TG-002 caps. The 8-case rows are development screens, not 30-case claims.

## The baseline schedule

`CumulativePolicy` v1.0.0 ([policy.py](../../../solvers/bem_inverse/policy.py)),
as run on TG-002:

| Phase | Operation | Data | M; K_geometry | Notes |
|---|---|---|---|---|
| 1 | Start | — | circle | Centred 65 mm circle; `localization none` keeps it |
| 1 | Warm-up | 0.25 GHz damped | 1; 4 | M=1 normal modes move and resize the circle |
| 2 | Prefix stages 1–4 | cumulative 0.5/0.75/1/1.25 GHz, damped k(1+0.25i) | 3/5/7/9; 8/12/16/20 | M=⌊3 max Re k_ext⌋, K=2M+2 |
| 2 | Undamped return | the same four, real | 9; 20 | Explicit return to the measured objective |
| 3 | Release | all 19 real, 0.25–2.5 GHz | 11/15/19; 192 | 1500 units each |
| 3 | Fixed | all 19 real | 25/31/37; 192 | One-time K64 cleanup before M25; recurrent under noise |
| 4 | Frontier tail | all 19 real | 43, 49, … ≤ 95; 192 | Up to the measured 1% paired-Jacobian frontier |
| 4 | Stop | — | — | Loss tolerance or noise discrepancy; a numerical failure goes to the final audit |

The modal trace cutoff follows the storage band: K_trace 64/96 up to
K_geometry 52 and 128/160 at K_geometry 192. Every stage applies a fatal
per-frequency production/refined field gate (1e-5 at ≤ 0.5 GHz, otherwise 1e-7).

## Phase 1 — start, position and size

| Variant | Change | Status | Tested on | Result | Evidence |
|---|---|---|---|---|---|
| M=1 damped warm-up from the kept start | — | Default | TG-002, all 30 | Part of the 26/30 baseline | [PC-001](../../../results/validation/cleaned_interfaces/PC-001/README.md) |
| No localization from a far start | — | Failure control | SC-049 far C | 188 mm; stage-1 stop | [SC-049](../shape_frequency_continuation/iteration_29/01_results.md) |
| Circle grid localization + warm-up (SC-050) | Exhaustive centre/radius search before shape fitting | Retired 2026-10-04; `--localization grid` is a control only | SC-050 far set, 7 configurations 220–267 mm from target | 7/7, including 5/5 clean transfers and 1/1 noisy, vs 0/6 without; far C 0.00131 mm in 93 s | [SC-050](../shape_frequency_continuation/iteration_30/02_results.md) |
| Dense exact-Mie localization (L) | Finer search | Not adopted | MA-003 legacy contrast-4/13.3 failures | Repairs 0/4; c13.3 star 99 → 7.7 mm | [MA-003](../modal_atlas/iteration_04/01_results.md) |
| NL-001: grid on vs off | A/B on the default policy | Proposed | TG-002, all 30 (planned) | — | [plan](../cleaned_interfaces/iteration_26/03_plan.md) |
| Interleaved exact translation (GGB-003) | Alternate translation and M3 shape updates | Diagnostic | Case 8, 4 frequencies | Centre error 458.6 → 1.40 mm; residual 111% → 14–16%; not recovered; 297.7 s, 260 s of it shape-certificate work; thin protrusions | [GGB-003](GGB-003_results.md) |
| Restricted translation + uniform scale (GGB-004) | 3 exact coordinates; shape stays circular | Diagnostic | Case 8, 4 frequencies | Centre error 0.198 mm, radius within 0.18 mm, 3.70 s; residuals 5.2–6.6% vs 5.5% noise target | [GGB-004](GGB-004_results.md) |
| The same at one frequency (GGB-005) | 0.5 GHz only | Diagnostic | Case 8 | Centre error 0.103 mm, 1.32 s; fitted-frequency noise target reached; 0.75–1.25 GHz holdouts miss | [GGB-005](GGB-005_results.md) |
| CS-001 phase 1 | Exact translation + scale at damped 0.25 GHz replaces the warm-up | Opt-in (`ShapeFrequencyPolicy`) | TG-002 8-case screen | Neutral: prefix-end losses within −10% to +7% of control in the seven non-circle pairs (both circles reach ~1e-12); initialization 1.62 → 1.30 s summed over 4 successes | [CS-001](CS-001_results.md); split below |

A separate position-and-size stage matters from far starts: on case 8 it is
the difference between 0.1–0.2 mm in 1–4 s and 1.4 mm in 298 s. From TG-002's
near starts the existing M=1 warm-up already does that job.

## Phase 2 — frequency ladder: data, damping and prefix bands

The user fixed this phase: "frequency ladder stays as it is now". Rows below
show where its pieces came from and which proposals would reopen it.

| Variant | Change | Status | Tested on | Result | Evidence |
|---|---|---|---|---|---|
| Borges band ⌊3 max(k, k_int)⌋ | Prefix M grows with contrast | Replaced | MA-002 legacy far set at contrast 0.5/2/4/13.3 | 3/3, 3/3, 2/3, 0/3; over-releases bands at contrast > 1 | [MA-002](../modal_atlas/iteration_03/01_results.md) |
| Exterior band ⌊3 max Re k_ext⌋ (B) | — | Default | MA-003 failures | Removes stage-1 wiggles; repairs 0/4 alone | [MA-003](../modal_atlas/iteration_04/01_results.md) |
| Damped prefix k(1+0.25i) (D) | Laplace–Fourier damping of the prefix | Default | MA-004 development set | Repairs 2/4 failures, keeps 8/8 | [MA-004](../modal_atlas/iteration_05/01_results.md) |
| Extra undamped pass instead (R) | — | Not adopted | MA-004 | Repairs 0 | [MA-004](../modal_atlas/iteration_05/01_results.md) |
| Centred state band K=2M+2 (8/12/16/20) | Restrict geometry storage in the prefix | Default | SC-035, legacy contrast-0.5 development shapes | Peanut/C/kite 0.14/0.47/0.57 mm vs 2.94/3.20/2.98; star 16% worse | [SC-035](../shape_frequency_continuation/iteration_18/01_results.md) |
| Low-order ladder K 4/6/8/10 for SPD | Ladder in the polar SPD baseline | Diagnostic | SC-034 legacy six; SPD cannot represent C or hook | Circle/star/peanut ≤ 3.3e-5 mm, kite 1.25 mm: the ladder is the operative control | [SC-034](../shape_frequency_continuation/iteration_16/01_results.md) |
| Fixed M=32 from the first stage | No band ladder | Not adopted | SC-022/024 circle, star, C | Fails under every tested variant; ladder gives 0.005/1.43/19.4 mm | [SC-022](../shape_frequency_continuation/iteration_08/01_results.md), [SC-024](../shape_frequency_continuation/iteration_09/01_results.md) |
| A2 parsimonious band rule | Smallest band reaching 0.9 of the best model decrease | Not adopted | SC-025: C plus held-out peanut, kite, hook | Wins C 0.37 vs 3.20 and peanut 0.31 vs 2.94 mm; loses kite 4.38 vs 2.98 and hook 2.34 vs 0.53 mm | [SC-023–025](../shape_frequency_continuation/iteration_09/01_results.md) |
| M=2 first stage | Smaller first band | Not adopted | SC-029 legacy six | Geometric-mean RMS ratio 0.668 but worst 9.5: C and peanut much better, kite and hook much worse | [SC-029](../shape_frequency_continuation/iteration_12/01_results.md) |
| Real prefix, with or without relaxed BIE | FM-002 four arms | Not adopted | 3 legacy cases: C and star at c13.3, C at c4 | Damped 3/3 either way; real 1/3 either way | [FM-002](../cleaned_interfaces/iteration_19/01_results.md) |
| Stage-2 multi-start census | 512 starts; keep the lowest loss | Diagnostic | Legacy c13.3 C | Lowest-loss endpoint recovers; 4/11 below-gap endpoints recover | [FM-003](../cleaned_interfaces/iteration_21/01_results.md), [FM-004](../cleaned_interfaces/iteration_23/01_results.md) |
| One vs four frequencies, M3/M7/M11 | GGB-001/002 ladders | Diagnostic | Case 8 | 0.4 GHz: 87.7% residual in 348 s (GauGal 5.3% in 0.81 s); 0.5 GHz: 67.6%; four frequencies: 111%, numerical failure in M3 | [GGB-001](01_results.md), [GGB-002](GGB-002_results.md) |
| Frequency only, M=K=255 from the start | No band ladder at all | Not adopted | SC-051, 36 legacy single-object configurations | 0/36 vs 34/36 for the established strategies | [SC-051](../shape_frequency_continuation/iteration_31/01_results.md) |
| PX-001: contrast-13.3 prefix change | Stronger damping or a longer low-frequency phase | Proposed; would reopen this phase | Target `hook__c13.3` | — Hook leaves the prefix at 6.8 mm; all 26 successes at ≤ 1.13 mm | [RG-001 plan](../cleaned_interfaces/iteration_31/03_plan.md), [review R2](../cleaned_interfaces/iteration_31/02_claude_review.md) |
| Damping ladder γ 0.5 → 0.25 → 0 | Graded damping | Proposed | Target legacy c13.3 C | — | [MA-005](../modal_atlas/iteration_06/01_results.md) |
| H: homotopy at the damped-to-real switch | Blend objectives at the handoff | Proposed; ON-001 arm never released | — | Review: unlikely to fix hook | [ON-001 plan](../cleaned_interfaces/iteration_30/03_plan.md) |

## Phase 3 — shape release after the prefix

| Variant | Change | Status | Tested on | Result | Evidence |
|---|---|---|---|---|---|
| Wider state ladder K 8/16/32/64/192 | Release storage earlier | Not adopted | SC-037 legacy four | Star restored to 0.53 mm; C 27.65% worse than SC-035, failing the 25% gate | [SC-037](../shape_frequency_continuation/iteration_19/01_results.md) |
| Add five frequencies through 2.5 GHz after the prefix | New data vs extra work on the old four, same bands | Not adopted | SC-029 legacy six | Ratio 0.963 or 0.786 by prefix; extra hard stops | [SC-029](../shape_frequency_continuation/iteration_12/01_results.md) |
| All-frequency M=11/15/19 release | Raise M with the full catalog | Default (`release_bands`) | SC-038 saved C and kite states | C 0.024 vs 0.489 mm and kite 0.110 vs 0.552 mm for an all-frequency M=9 hold | [SC-038](../shape_frequency_continuation/iteration_20/01_results.md) |
| Larger single releases M22/M25 | Atlas-nominated bands | Diagnostic | SC-041 star, kite | Star M25 0.0476 mm; kite M22 0.0730 mm, then a numerical stop | [SC-041](../shape_frequency_continuation/iteration_23/01_results.md) |
| One-time K64 cleanup | Crop stored harmonics once | Default before M25 | SC-042 legacy six suffixes | Ratio 0.915 vs none; repairs the kite artifact; others tie | [SC-042](../shape_frequency_continuation/iteration_24/01_results.md) |
| Recurrent cleanup or K64 cap | Crop at every stage | Default under noise | SC-044 fresh lobes and deep C, clean plus two 1% noise draws | Ratio 0.873; avoids one noisy-C numerical stop; most tie | [SC-044](../shape_frequency_continuation/iteration_25/01_results.md) |
| Release rule: fixed +6, stagnation or atlas | When to raise M | Fixed is default | SC-043 legacy six | Atlas ratio 1.113 vs fixed, 1.005 vs stagnation; kite 88% worse under atlas | [SC-043](../shape_frequency_continuation/iteration_26/01_results.md) |
| Frontier tail (MA-005 DF) | Add fixed stages up to the measured frontier | Default | MA-005 legacy contrast-4/13.3 set | Transfer 7/8 vs 0/8 frozen (6/6 vs 0/6 without the duplicate scene); development 11/12; under 1% noise RMS worsens 0.206 → 0.228 and 0.015 → 0.076 mm | [MA-005](../modal_atlas/iteration_06/01_results.md) |
| CS-001 phase 3 | Four all-frequency stages (11,24), (15,32), (19,40), (25,52) replace release, fixed and tail | Opt-in (`ShapeFrequencyPolicy`) | TG-002 8-case screen | 4/8 vs 5/8; 1.499x on the 4 shared successes; `c_shape__c13.3` regressed at M15 on the resolution gate (1.128x over 1e-7 at 2.5 GHz). Successes take the same accepted steps at each M at half the trace cutoff | [CS-001](CS-001_results.md); split below |
| Noise-aware frontier | Count only harmonics above the noise level | Proposed | — | — | [MA-005](../modal_atlas/iteration_06/01_results.md) |
| One more release after the discrepancy stop | — | Proposed | — | — | [CI-001](../cleaned_interfaces/iteration_03/01_results.md) |

## Phase 4 — full release and stopping

| Variant | Change | Status | Tested on | Result | Evidence |
|---|---|---|---|---|---|
| Loss tolerance and whitened noise discrepancy | SC-044 noise rule | Default | CI-001 legacy all-36 | 34/36 recovered; 28/36 pass the regression contract. Seven of the eight misses are noisy cases that the discrepancy rule stopped at the noise level, five at M15 | [CI-001](../cleaned_interfaces/iteration_03/01_results.md) |
| E: required-accuracy exit | Stop when the full catalog's maximum residual ≤ 0.003 and the audit passes | Opt-in | TG-002, all 30 | 26/30 = B; 1.546x median (p10 1.225x); suite 803 → 551 s; median RMS 0.0019 → 0.015 mm, all within gates | [ON-001](../cleaned_interfaces/iteration_31/01_results.md), [review R6](../cleaned_interfaces/iteration_31/02_claude_review.md) |
| CS-001 phase 4: full release M95/K192 | Replaces the frontier tail | Opt-in | TG-002 8-case screen | Never entered: every case succeeded or stopped earlier | [CS-001](CS-001_results.md) |
| CI-002: noise-aware residual gate | — | Proposed | — | — | [CI-001](../cleaned_interfaces/iteration_03/01_results.md) |

## Stage-exit controls

These do not change the stage sequence, but they decide where a stage, or the
whole fit, ends. All four TG-002 failures end here, not at a schedule boundary.

| Variant | Status | Tested on | Result | Evidence |
|---|---|---|---|---|
| Fatal absolute field gate | Default | TG-002 | Ends all 4 failures; never trips in the 26 successes | [review R1](../cleaned_interfaces/iteration_31/02_claude_review.md) |
| Decision-relative gate (RG-001) | Opt-in | TG-002, all 30 | 26/30; failures progress (aphex c4 1.69 → 0.66 mm), but all four endpoints fail the audit | [RG-001](../cleaned_interfaces/iteration_31/05_results.md) |
| Nodal resolution response: reject, then promote to N1024/2048 | Opt-in (`nodal_fixed`) | FM-005 legacy C census; TG-002 as PC-001 N1 | Legacy 4/11 → 7/11. TG-002 26/30; aphex c4 reaches 0.30 mm RMS and a 1.95 mm Hausdorff upper bound but fails the residual gate (0.055); failures take 814–1863 s | [FM-005](../cleaned_interfaces/iteration_25/01_results.md), [PC-001](../../../results/validation/cleaned_interfaces/PC-001/README.md) |
| RP-001: modal resolution response | Proposed | — | — | [RG-001](../cleaned_interfaces/iteration_31/05_results.md) |
| Agreement damping, exact reuse, progress stop (DP-001 F) | Opt-in | TG-002, all 30 | 26/30; 1.134x vs E | [DP-001](DP-001_results.md) |
| Reach clipping (G) | Not adopted | TG-002 8-case screen | 4/8; 0.924x | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| Working-frequency proposals (W) | Not adopted | TG-002 8-case screen | 4/8; 0.890x vs E | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| Gaussian displacement map (F) | Unqualified | 16 saved states | 10/16 qualify; no fits run | [ON-001](../cleaned_interfaces/iteration_31/01_results.md) |
| Trust/fidelity control (R), W2 | Proposed; ON-001 arms never released | — | — | [ON-001 plan](../cleaned_interfaces/iteration_30/03_plan.md) |
| AF-001: adaptive-fidelity acceptance | Proposed | — | Refined re-solves are 47–49% of all solves | [RG-001 plan](../cleaned_interfaces/iteration_31/03_plan.md) |
| GN-001: lean LM | Proposed | — | Forecast only, with a known accounting limitation | [iteration 32](../cleaned_interfaces/iteration_32/01_results.md) |

## Where CS-001's time and regression came from

Computed read-only from `results/validation/cleaned_interfaces/CS-001/{control,revised}/runs/*/result.json`
(`stages[].seconds`, `accepted_steps`, `nodes`). Summed over the four shared
successes:

| Seconds | Control | Revised |
|---|---:|---:|
| Initialization (warm-up vs translation + scale) | 1.62 | 1.30 |
| Frequency ladder (identical operations) | 9.47 | 9.15 |
| Shape stages | 19.33 | 8.16 |
| Audits, setup and output | 6.58 | 6.41 |
| **Audited output** | **37.01** | **25.03** |

- All of the gain is in the shape stages. Each success took exactly the same
  number of accepted steps at each M in both arms (kite 3/3/1, peanut 2/1,
  cog 3/3/2/1, circle 0). The revised stages ran at K_trace 64/96, because
  K_geometry ≤ 52; the control's ran at 128/160 with K_geometry 192.
- The C-shape regression is that same resolution gate at the lower cutoff.
  It made 7 identical-count steps at M11, then 0 at M15, where the control
  took 3 steps and went on to recover at M31.
- Phase 1 changed nothing measurable. Prefix-end losses match the control
  within −10% to +7% in the seven non-circle pairs; both circles reach ~1e-12.

So CS-001 measured a coupling the plan already flagged: compact storage
lowers the modal trace cutoff. That coupling was not isolated by experiment.

## What the evidence supports

- **Phase 2 is the best-supported part.** Damping, the exterior band and the
  K=2M+2 state band each repaired measured failures. Its one known weak point
  is `hook__c13.3`, which leaves the prefix in a wrong basin.
- **Phase 1 matters only for far starts.** It is a large win on case 8 and
  neutral on TG-002.
- **Phase 3 compact stages buy speed by lowering numerical resolution.** They
  cost one recovery on the screen.
- **Phase 4's only proven lever is E.** It gives 1.55x at a 7.7x median RMS
  cost that stays inside the gates. Full release has not been exercised.
- **The four failures end on the resolution gate.** The proposed modal
  resolution response (RP-001) is the unrun piece. The same gate stopped
  CS-001's C-shape.

## Out of scope

These keep the schedule fixed or replace the method:

- Physics and geometry backends: NU-001…007a, PC-002, GC-001.
- Forward operators: ON-003, EW-001.
- The GauGal volume inverse: ON-002, GP-001 and GS-001. In GS-001, one
  frequency fit `c_shape__c13.3` data to 0.461%, yet the contour stayed near
  the start circle (28.1 mm RMS).
