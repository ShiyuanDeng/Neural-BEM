# FM-005: the resolution response adds 3 paired recoveries (7/11); the rest are limited at the N1024/2048 ceiling

Frozen plan: [iteration 24](../iteration_24/03_plan.md) (user: "go"). Pre-registration
commit `9aea18d1`; sealed at that head. Existing branch, no branch or worktree created. One
worker, four frequency threads at both resolutions, `device=auto`. All 12 runs completed in
5,717 s, under the 3 h campaign cap; none was skipped, timed out or raised. There were no
memory-guard events.

## Result

Each run is FM-004's continuation with RB-001's `ResolutionResponse(1024, 2048)`.
"Promoted" is the stage where the run moved to N1024/2048. "Rejected at ceiling" counts
unresolved trials rejected at N1024/2048.

| Start | Block | FM-004 | FM-005 outcome | Promoted | Final RMS (mm) | Hausdorff upper (mm) | Max residual | Rejected at ceiling | Quota-limited stages | Recovered | Certified |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 82 | primary | refusal | completed | release_M19 | 0.0067 | 0.146 | 4.3e-5 | 0 | 6 | **yes** | yes |
| 399 | primary | refusal | accuracy-limited | stage_4_damped | 3.30 | 18.02 | 1.37 | 16 | 0 | no | no |
| 139 | primary | refusal | completed | release_M11 | 0.106 | 0.575 | 0.134 | 74 | 12 | no | no |
| 431 | primary | refusal | completed | release_M11 | 0.537 | 3.22 | 0.456 | 128 | 14 | no | no |
| 30 | primary | refusal | completed | release_M11 | 0.0033 | 0.053 | 3.4e-6 | 0 | 3 | **yes** | yes |
| 383 | primary | refusal | accuracy-limited | stage_4_undamped | 1.67 | 5.37 | 1.47 | 42 | 0 | no | no |
| 479 | primary | refusal | completed | release_M11 | 0.0032 | 0.056 | 4.2e-6 | 0 | 3 | **yes** | yes |
| C4 166 | primary | refusal | accuracy-limited | release_M11 | 0.737 | 4.47 | 0.384 | 16 | 0 | no | no |
| 289 | non-regression | recovered | completed | — | 6.5e-5 | 0.030 | 1.6e-6 | 0 | 0 | yes | yes |
| 142 | non-regression | recovered | completed | — | 1.5e-3 | 0.035 | 9.4e-7 | 0 | 3 | yes | yes |
| 443 | non-regression | recovered | completed | — | 1.4e-3 | 0.036 | 1.0e-6 | 0 | 3 | yes | yes |
| 262 | non-regression | recovered | completed | — | 1.1e-4 | 0.029 | 2.4e-7 | 0 | 0 | yes | yes |

"Accuracy-limited" is the response's own stop, `accuracy_limited_trials_exhausted`. At
N1024/2048, every remaining trial was rejected as unresolved.

**Pre-stop identity holds for all 12 runs.** Each FM-005 run reproduced FM-004's accepted
states exactly (stage, iteration, loss and curve) up to FM-004's last accepted state. The
refused runs then continued past FM-004's stop. The four non-regression runs never promoted,
and their curves are identical to FM-004. Two (289, 262) differ only in charged work units on
two states (2,526 against 2,469 units for 289), from the response's stricter dispatch
accounting.

## Pre-registered readings

- **P1 (gate or basin): mixed, 3/6.** Starts 82, 30 and 479 recover. Each was promoted once
  and then had no unresolved trial at the ceiling, so for these three the CI-001 hard stop was
  the only obstruction. The other three are not basin failures either:
  - **139** reaches 0.106 mm RMS and 0.575 mm Hausdorff (inside the shape limits). It fails on
    residual (0.134) after 12 quota-limited stages and 74 rejected trials at the ceiling.
  - **431** is at 0.537 mm RMS, with 14 quota-limited stages and 128 rejected trials.
  - **383** stops accuracy-limited at stage_4_undamped (1.67 mm).

  All three are limited at the N1024/2048 ceiling: their trial steps leave even the finer
  resolution. 139 and 431 are therefore **budget-limited, not negative**. 383 is a stop.
- **P2 (control): failed again.** The contrast-4 loss winner is accuracy-limited at release_M11
  (0.74 mm). This prediction failed in both FM-004 and FM-005. For contrast 4 the plain CI-001
  start recovers and the loss-minimum census endpoint does not.
- **P3 (wrong basin): as predicted.** 399 is accuracy-limited at stage 4 and 3.3 mm RMS, with a
  failed audit.
- **P4 (non-regression): 4/4 kept**, with identical trajectories.
- **P5 (certificate): agrees 12/12.** This test is stronger than FM-004's. Start 139 sits
  inside both shape limits but fails the residual limit, and it is correctly neither recovered
  nor certified. The three promoted recoveries also pass the extra audit at the original
  N512/1024. The promoted failures do not.

## Cost

| Quantity | FM-004 (no response) | FM-005 (response) |
|---|---:|---:|
| Paired recoveries of 11 below-gap candidates | 4 | **7** (Wilson 95% [35.4, 84.8]%) |
| Census cost per paired recovery | 14,025 units, 15.8 min | 8,014 units, 9.0 min |
| Mean suffix per paired candidate | 1,569 units, 87 s | 3,813 units, 498 s |
| Near-truth (≤ 5 mm) candidates recovered | 4/9 | 6/9 |

Promoted N1024/2048 stages are slow (four frequency threads, as at N512). Recovered promoted
runs took 419–683 s. The two budget-limited runs took 1,327 and 1,504 s, against the policy's
1,784.5 s fit wall budget.

## Mechanism

After a good stage 2 there are three populations:

1. Clean continuations (289, 142, 443, 262): never unresolved.
2. Continuations stopped by one unresolved trial (82, 30, 479): fixed by a single promotion.
3. Continuations whose LM trials keep leaving the N1024/2048 regime (139, 431, 383, and the
   C4 control): rejected trials eat the stage quotas or exhaust the trials.

Stage-2 distance does not separate population 3 from the others. Its stage-2 distances
(4.23, 4.53, 4.62 mm) overlap those of populations 1 and 2 (2.42–5.22 mm). Which trial
geometries leave the regime has not been examined.

## Scope

Retrospective selection on a truth-scored census, as in FM-004. Noiseless synthetic damped
data, development C only. The response is opt-in and not adopted as a default. Sources and
results of FM-003, FM-004, CI-001 and RB-001 are unchanged. `fm005.report` reads
`resolution_promoted`, which the runner records only for resumed fits, so `summary.json`
shows it as null. [`fm005_review.py`](../../../../experiments/cleaned_interface/fm005_review.py)
derives promotion from the stage resolutions and writes
[`review.json`](../../../../results/validation/cleaned_interfaces/FM-005/review.json).
The sealed module was not edited.

## Next (proposed, not run)

**FM-006: blind end-to-end test of the assembled pipeline on fresh seeds.** Truth is used only
for scoring at the end.

1. Run the plain CI-001 schedule from z1. Stop if it is certified; this recovers contrast 4.
2. Otherwise run a paired stage-2 census on new seeds.
3. Continue the below-gap endpoints in loss order with the resolution response.
4. Stop at the first certified continuation.

Same case and settings, with every rule frozen from FM-003–005. Measure success and the
total cost against the 63-minute FM-003 census. A second, separate question is why the
population-3 trials leave the N1024/2048 regime: curvature and self-distance of the rejected
trial geometries.

Evidence: [summary](../../../../results/validation/cleaned_interfaces/FM-005/summary.json),
[review](../../../../results/validation/cleaned_interfaces/FM-005/review.json),
[seal](../../../../results/validation/cleaned_interfaces/FM-005/implementation.json),
[run log](../../../../results/validation/cleaned_interfaces/FM-005/run.log).
Reproduce: `python -m experiments.cleaned_interface.fm005 seal|run|report`, then
`python -m experiments.cleaned_interface.fm005_review`.
