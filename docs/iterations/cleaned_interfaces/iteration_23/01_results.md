# FM-004: below-gap stage-2 endpoints recover 4/11; every failure is a numerical-gate stop

Frozen plan: [iteration 22](../iteration_22/03_plan.md) (user: "go"). Pre-registration commit
`26bc9574`; sealed at that head. Existing `feature/shape-frequency-continuation` branch, no
branch or worktree created. One worker, four frequency threads, `device=auto`,
single-threaded BLAS. Every run completed inside its 900 s deadline. There were no exceptions
and no memory-guard events.

## Result

The candidate rule reproduced the frozen list: 11 paired contrast-13.3 endpoints with stage-2
loss ≤ 0.9 × 0.0045209 (threshold 0.0040688; next loss 0.0043776). Start 289 is FM-003's Phase 2,
reused. The other ten and the contrast-4 control ran the unchanged FM-003 suffix.

| Start | Stage-2 loss | Stage-2 distance (mm) | Outcome | Stop | Final RMS (mm) | Hausdorff upper (mm) | Max residual | Recovered | Certified |
|---|---:|---:|---|---|---:|---:|---:|---|---|
| 289 (FM-003) | 0.001183 | 2.42 | completed | — | 6.5e-5 | 0.030 | 1.6e-6 | **yes** | yes |
| 82 | 0.001479 | 2.70 | numerical refusal | release_M19 | 0.138 | 0.433 | 0.135 | no | no |
| 399 | 0.001907 | 18.59 | numerical refusal | stage_4_damped | 3.31 | 18.05 | 1.40 | no | no |
| 142 | 0.001937 | 3.67 | completed | — | 1.5e-3 | 0.035 | 9.4e-7 | **yes** | yes |
| 139 | 0.002708 | 4.23 | numerical refusal | release_M11 | 1.77 | 5.92 | 1.30 | no | no |
| 431 | 0.002755 | 4.53 | numerical refusal | release_M11 | 1.08 | 4.37 | 1.00 | no | no |
| 30 | 0.002888 | 3.67 | numerical refusal | release_M11 | 0.699 | 2.01 | 0.752 | no | no |
| 383 | 0.003181 | 4.62 | numerical refusal | stage_4_undamped | 1.62 | 4.84 | 1.52 | no | no |
| 443 | 0.003480 | 4.70 | completed | — | 1.4e-3 | 0.036 | 1.0e-6 | **yes** | yes |
| 262 | 0.003693 | 4.32 | completed | — | 1.2e-4 | 0.029 | 2.4e-7 | **yes** | yes |
| 479 | 0.003835 | 5.22 | numerical refusal | release_M11 | 0.739 | 1.88 | 0.807 | no | no |
| C4 control 166 | 0.002428¹ | 5.32 | numerical refusal | release_M11 | 0.938 | 4.94 | 0.528 | no | no |

¹ Contrast-4 stage-2 loss, not comparable with the contrast-13.3 losses.

"Numerical refusal" is the hard stop `candidate leaves the frozen numerical-resolution regime`
(`lm_backend.py:564`). A **trial** candidate fails the N512/1024 accuracy gate and the CI-001
policy, which has no resolution response, ends the schedule. The remaining stages are skipped
and the final audit runs. Two of the four completed runs (142, 443) exhausted stage quotas at
`fixed_M55`–`M67` and still met every contract limit.

## Pre-registered readings

- **R1 (basin or luck): mixed, 3/8.** The eight new near-truth candidates recovered 3 times
  (Wilson 95% [13.7, 69.4]%). Including 289, near-truth stage-2 endpoints recovered 4/9 times
  ([18.9, 73.3]%). FM-003's success was not unique, but stage-2 distance below 5 mm is not
  sufficient. Stage-2 distance does not order the outcome. Recovered runs started 2.42–4.70 mm
  from the truth and failed runs 2.70–4.62 mm.
- **R2 (truth-free certificate): agrees 12/12.** No run was certified but not recovered, and
  none recovered without certification. **The test is weak**: every non-recovered run ended
  in a hard stop with a maximum residual of 0.135 or more, against a 0.003 limit. No run ended
  close to the gate, so the certificate separated easy cases only.
- **R3 (wrong low-loss basin): as predicted.** Start 399 (18.6 mm) stopped at stage 4 with a
  failed final audit, 3.3 mm RMS.
- **R4 (control): failed the prediction.** The contrast-4 loss winner (5.32 mm) stopped at
  release_M11, 0.94 mm RMS. CI-001 recovers this case from z1. Selecting the minimum
  stage-2 loss can lose a case that the fixed initialisation recovers.

## Mechanism

All eight failures, including the control, are the same numerical-gate stop and not a
converged wrong minimum. Six of the seven failed paired runs were within 1.8 mm RMS when they
stopped; 399 was at 3.3 mm. Of the seven paired stops, four came at the first band release (`release_M11`) and one at
`stage_4_undamped`. The control also stopped at `release_M11`. In the CI-001 policy a single unresolved trial step ends the whole run.
RB-001 already implemented an opt-in resolution response (reject the inaccurate candidate and
backtrack, or promote to N1024/2048). It removed all four immediate stops it was tested on, but
those trajectories were 5.5–23 mm from the truth and did not recover (0/4). These eight stops are a
different and better-placed population.

## Cost

| Quantity | Value |
|---|---:|
| Census (FM-003 Phase 1) | 56,100 units, 63.2 min |
| Mean suffix per paired candidate | 1,569 units, 87.4 s |
| Paired recoveries | 4 of 11 continued |
| Census cost per recovery | 14,025 units, 15.8 min |
| Loss-ordered sequential stop (first certified) | position 1 (start 289): 58,569 units, 65.7 min |

The sequential stop is trivial on this census: the loss winner happened to recover. The
loss-ordered list shows this was not guaranteed. The second and third candidates (82, 399)
both failed.

## Scope

Retrospective: the stage-2 truth distances were already known from FM-003 when the rule was
frozen. Noiseless synthetic damped data, development C only. No production default, FM-003
or CI-001 source or result changed. The CI-001 package-wide `verify` already fails on
`experiments/cleaned_interface/__init__.py`, which was edited in `99cc7173` before this
iteration. FM-003's and FM-004's own seals verify.

## Next (proposed, not run)

**FM-005: rerun the eight FM-004 numerical-refusal stops with RB-001's resolution response.**
Change one thing: the CI-001 hard stop becomes reject-and-backtrack, then promotion to
N1024/2048, as qualified in RB-001. The candidates, suffix and budgets stay unchanged. The
pre-registered prediction is that most of the six paired near-truth runs (82, 139, 431, 30,
383, 479) and the control recover. If so, the operative obstruction after a good stage 2 is
the numerical gate, not the basin, and the cost per paired recovery roughly halves. If they
still fail, the release stages need a different schedule. A blind fresh-seed census at
ρ ≥ 0.2 with a certified sequential stop should follow only after this.

Evidence: [summary](../../../../results/validation/cleaned_interfaces/FM-004/summary.json),
[seal](../../../../results/validation/cleaned_interfaces/FM-004/implementation.json),
[run log](../../../../results/validation/cleaned_interfaces/FM-004/run.log),
per-run records in `results/validation/cleaned_interfaces/FM-004/runs/`.
Reproduce: `python -m experiments.cleaned_interface.fm004 seal|run|report` with
`PYTHONPATH=solvers:.` in the EMNerf environment.
