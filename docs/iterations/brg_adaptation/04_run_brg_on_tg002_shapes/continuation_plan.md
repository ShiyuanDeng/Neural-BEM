# Complete the shipped-limit row after the old time cap

## Authority and question

Coordinator, 18 November 2026, about 01:24 UTC: let the old supervisor end
by itself; then continue `c_shape__c0.5` from its saved state as attempt 02
and run the six unstarted cross, cog and aphex_twin cases at both contrasts.
Report activity 04 only when all 20 shipped-limit cases are complete.

The user's rule is: "do not stop result-gerating terminal processes due
to time limit unless i say otherwise. if it stucks or goes wrong you should
still stop it. this is only about time limit". A stuck or faulty run may
be stopped after reporting the evidence, unless urgent. The old queue and
all files it loads remain untouched. New entry points implement this plan.

The original cap ended C-shape attempt 01 at 2026-11-18T01:25:31.829621 UTC,
return code 124, during frequency 35. Frequencies 1–34 and their exact
states are retained. Its two-second scoring allowance also expired; one
saved-output-only score was completed afterward, without a solver call.
Its partial area error is 0.0762351311; a final-curve residual sweep was
not reached. The supervisor cancelled six waiting cases and finishes after
hook at contrast 4. No agent stopped or restarted those processes.

## Settings, comparison and restart check

Keep every inverse and data setting from [the approved plan](plan.md),
including the shipped curvature limit 0.1/minimum band 20, known contrast,
37 frequencies, centred unit-disk start, eight MATLAB threads and patches
03/04. Only wall-time enforcement changes. No BEM work or tuning.

C-shape resumes the exact `state_034.mat`; frequencies 1–34 are loaded,
not recomputed. Preserve attempt 01, its logs and data, plus snapshots of
its partial summary, fit, score, settings, checks and manifest before
writing attempt 02. Its 37 data files are reused by SHA-256.
The six unstarted cases generate their data with the unchanged BRG forward
wrapper, then invert and score once. They retain those files for activity 05.

The saved-state check uses the completed star at contrast 4, frequency 20
before 21. All 13 saved state fields are finite. The endpoint coordinates
match the compact record exactly. Source comparison confirms uninterrupted
execution passes `src_info_out`, while restart loads that same complete
saved structure and passes it to the identical next-frequency call. The
inverse loop is unchanged except the elapsed-time stop. No next solve was
recomputed. Receipt: `results/brg/tg002_completion/2026-11-18/saved_state_restart_check.json`.

## Order and time targets

Start only after PID 727204's old supervisor exits and its lock is free.
Order: C-shape 0.5 continuation; cross 0.5, cross 4, cog 0.5, cog 4,
aphex_twin 0.5, aphex_twin 4. At most two BRG fits in total. Start activity
05 only after this queue ends and all 20 shipped-limit cases are complete.

One hour per case and five hours per new queue are reporting targets,
never automatic stops. Record overruns, tell the coordinator and continue.
The 14 GiB guard delays starts. The new runner contains no time-based kill.
Only a user-requested STOP asks active fits to end at a saved checkpoint;
no STOP is created on time or memory pressure. Faults are reported with
saved evidence before any manual intervention, unless urgent.

## Commands, outputs and success criteria

Use `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1` and the
`/home/drdeng/miniconda3/envs/EMNerf/bin/python` executable:

- `experiments/baselines/brg/run_tg002_control.py --row shipped --prepare`
- `experiments/baselines/brg/run_tg002_control.py --row shipped --campaign --detach`

Queue state, resources, source snapshots and stop files:
`results/brg/tg002_completion/2026-11-18/`. Per-case outputs remain in
`results/brg/tg002_shapes/2026-11-17/`; the old campaign receipt stays intact.
Figures remain in this activity's `figures/`, including the cut-attempt figure.
The new MATLAB and scoring entry points are `run_tg002_control_case.m` and
`score_tg002_control.py`. No file loaded by the old queue is changed.

Completion requires 20 scored cases, each with 37 inverse records, data
files, exact states and final-curve residuals. Keep finite-output checks,
raw geometry/material scores, terminal rejection counts, phase times,
failed-attempt time and total elapsed time. Inspect figures, commit and
push each finished batch by path, keeping about 5 MB per case. Preserve
failures and ask the coordinator about any change to numerical settings.

Preparation checks passed on 18 November before launch: both queue modes
were simulated past their time targets with at most two workers. The
shipped mode opens two workers; the control mode runs its pilot alone.
The saved-state comparison and Python syntax checks passed. No real process
was launched, stopped or restarted during these checks.
