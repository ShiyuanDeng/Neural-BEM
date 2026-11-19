# Make the GauGal fits converge — plan, 19 November 2026

Written 14:35 UTC. Follows [the untuned GauGal reference](../03_record_untuned_gaugal_reference/results.md),
which recovered 0/20.

## User's words

- "did you investigate why gaugal have 0/20 recoveries?" The answer was no.
- "you go check this with subagents. try to be quick"
- "fix it if you can"

So the user chose: check the cause, use subagents, be quick, and fix GauGal if
possible. The rest below is the coordinator's choice.

## What the saved records already show

Read from the 50 saved `fit.json` files, with no new run:

- Every fit stopped at the 80-iteration limit.
- 69–92% of the inner field solves hit their 100-iteration cap without
  reaching the 1e-4 tolerance. Each capped solve costs the full 100
  iterations, about 4 s per outer iteration.
- At contrast 4 the weighted data mismatch on `kite` fell only from 19.0 to
  13.5 in 80 iterations and was still falling. At contrast 0.5 it fell from
  19.0 to 0.025.
- Noisy and clean scores agree to a few tenths of a percent.

Working guess: the fits were cut off long before they converged, and the
failing inner solves made each iteration slow and its gradient inexact.

## Questions

1. Do exact inner solves and a run to convergence bring the contrast-4 data
   mismatch down to the level seen at contrast 0.5?
2. Does a converged fit then recover the shapes (area error at most 5%)?
3. What does a converged fit cost per case?

## Settings

- Data, cases, start and scoring: unchanged TG-002, contrasts 0.5 and 4,
  19 real frequencies at once, recovered contrast, protocol version 1.
- Kept from the reference: lattice 51, width 0.7, TV weight 0.5,
  susceptibility limit 15, lower limit −0.9.
- Changed: inner solves made exact or converged; the fit runs until the data
  mismatch stops falling, with no time stop.
- The step size stays 0.05 unless a larger one is shown to be stable on the
  data mismatch alone.
- Every choice is made from the data mismatch and solver convergence. Truth
  scores are read only after a setting is fixed. No grid search on truth.
- The `default` variant must stay bit-for-bit as it is. The new variant is
  `converged`. `~/Gau-Gal` is not edited.

## Comparisons

- New `gaugal/converged_clean_uc_fs` against the saved
  `gaugal/default_clean_uc_fs`, on the 20 cases at contrasts 0.5 and 4.
- If time allows, `gaugal/converged_n1d0_uc_fs` against the saved noisy run.
- BEM rows are reused, not rerun.

## Success criteria

- Cause confirmed if the `kite__c4` per-frequency mismatch falls well below
  the saved 58–101% once the solves converge and the fit runs on.
- Fix accepted if all 20 clean fits end on the stop rule with converged
  inner solves. The recovery count is reported whatever it is.
- If the mismatch converges and the shapes still miss, that is the answer:
  the limit is the method's image, not our settings.

## Run budget

- Probe: at most six fits on `kite__c4` and `kite__c0.5`.
- Then 20 clean fits, then 20 noisy fits. Time one case before quoting a
  total. Two GauGal fits may share the GPU.

## Who does what

Two Codex panes in this Herdr tab, both already open with full access:

- `native-adapter` (hard code): the `converged` variant. Brief: [brief_code.md](brief_code.md).
- `native-run` (runs): the probe, then the 20-case runs. Brief: [brief_runs.md](brief_runs.md).

## Commands and outputs

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY -m experiments.comparison run gaugal/converged_clean_uc_fs
$PY -m experiments.comparison run gaugal/converged_n1d0_uc_fs
```

- Probe outputs: `results/_probes/gaugal_convergence/2026-11-19/`.
- Fits and scores: `results/gaugal/converged_clean_uc_fs/` and
  `results/gaugal/converged_n1d0_uc_fs/`.
- Reports: `code_report.md`, `run_report.md` and `results.md` in this folder.
