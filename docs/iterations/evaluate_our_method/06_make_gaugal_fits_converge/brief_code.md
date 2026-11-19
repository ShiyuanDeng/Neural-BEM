# Brief for the code agent (`native-adapter`) — 19 November 2026

From the baseline coordinator (Claude, pane `w5:p1`). This is a new task. Your
native CSI adapter work is finished and closed.

Read first: [plan.md](plan.md), then
`experiments/gaugal_comparison/gaugal_arm.py`, `experiments/comparison/gaugal.py`
and `~/Gau-Gal/src/gaugal/paper2d/collocation.py`.

## Goal

GauGal recovered 0/20 on TG-002. The saved records suggest the fits never
converged. Add a `converged` variant that removes that fault. Be quick: the
user is waiting.

## What is known

- Inner solver: BiCGStab, tolerance 1e-4, cap 100 (`SolverControls`). 69–92%
  of solves hit the cap. Worst final residuals are 2–4% at contrast 4 and up
  to 53% at contrast 0.5.
- Outer loop: FISTA with TV, fixed step 0.05, 80 iterations, 400 s limit. On
  `kite__c4` the weighted mismatch was still falling at iteration 80.
- The lattice is 51 by 51, so 2,601 unknowns per frequency. An exact dense
  solve on the GPU should be cheap.
- GauGal has a `direct` solver, but it refuses the kernel-only FFT assembly
  the adapter uses, and the adapter passes an empty `dense_g`. The legacy
  note GS-001 fixed a similar stall with an exact Gaussian mass
  preconditioner in a different adaptation.

## Your work

1. Make the inner solves exact or converged in the adapter. Suggested: build
   the 2,601-square lattice matrix once per frequency and outer iteration by
   applying GauGal's own forward operator to the identity, then solve the
   forward and adjoint systems densely. Use another route if it is simpler
   and as exact. Record the true relative residual of each solve.
2. Replace the 80-iteration and 400 s stops, in the new variant only, by a
   rule fixed in advance on the data mismatch. Suggested: stop when the
   weighted mismatch falls by less than 1% over 50 iterations, with a cap of
   3,000 iterations. No stop on time: record the time and carry on. Also
   remove the parent's 600 s kill for this variant.
3. Wire it as `gaugal/converged_<data>_uc_fs` in
   `experiments/comparison/gaugal.py`. Keep lattice 51, width 0.7, TV weight
   0.5, step 0.05, limit 15. Keep the step size a setting.
4. Check, and nothing more: the gradient with exact solves matches a finite
   difference of the weighted mismatch on a few coefficients; the `default`
   variant's settings and code path are unchanged; one `kite__c4` clean fit
   runs end to end. Report its time per iteration.

## Rules

- Do not edit `~/Gau-Gal`, `experiments/comparison/scoring.py` or anything
  under `solvers/`. Your paths: `experiments/gaugal_comparison/gaugal_arm.py`,
  `experiments/comparison/gaugal.py`, the `gaugal` branch of
  `experiments/comparison/__main__.py` if the parent kill lives there, and
  `code_report.md` in this folder.
- `default` must stay bit-for-bit. Never choose a setting by looking at truth
  scores; use the data mismatch and solver residuals only.
- The other agent (`native-run`) is probing with scratch scripts under
  `results/_probes/`. It does not edit your files.
- No new branch or worktree. Commit with
  `git commit -m "..." -- <your paths>` and push. Take times from `date -u`.
- A question that changes the physics, the data or the method: ask me with
  `herdr agent prompt w5:p1 "native-adapter: ..."`. Otherwise decide and note it.
- When the variant runs, tell me the same way, in at most five lines: what
  changed, the gradient check, seconds per iteration, the commit.
- Terminal answers: at most three lines per paragraph, plain words.
