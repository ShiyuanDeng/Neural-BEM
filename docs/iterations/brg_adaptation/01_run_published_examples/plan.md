# Run the published BRG examples

Questions: does the BRG package (inverse-obstacle-scattering2d) build and run
on this machine? Does its transmission inverse run on its own example?

This activity uses their code only. Our solver is not touched.

## Status

Started on 17 November 2026. The user asked the coordinator to open two agents
"to continue on csi and brg works respectively". The coordinator assigned
activity 01 to `brg`; this supersedes the earlier "not now".

Checkpoint reached on 17 November: build, suite and star generation complete;
transmission multi-component test failed. Corrected low-frequency checks
pass. The coordinator approved patches 03 and 04 and instructed the full
shipped-example run on 17 November. Preparing/resuming step 5 below.

Checkpoint instruction: complete steps 1–4 and a low-frequency check of the proposed
step 5 physics fix, then stop for the coordinator. Do not start the full
117-frequency run until the coordinator answers. Set eight MATLAB compute
threads in the wrapper and measure a dense solve at one and eight threads.
Save each full-run frequency separately and resume from the last saved one;
data generation plus inversion remains limited to four hours.

## User decisions (17 November 2026)

These come from the grilling session recorded in the
[legacy design record](../../../../../Neural_SDF_BEM_AD/docs/iterations/baselines/iteration_01/02_proposals/02_design_decisions.md).
The user split the work into two investigations, `csi_adaptation` and
`brg_adaptation`.

- Principle: "for fair comparison we should avoid changing their code and
  settings, we should instead adapt our code to their test cases."
- Settings: "first run example ones to confirm everything works, then use
  paper settings when we acc generate results for comparison." Code defaults
  apply only where the paper is silent. No tuning.
- Failures: "the agent is allowed to debug." Every change to upstream files is
  saved as a patch in `external/patches/brg/` and reported.
- No shared layer with CSI. This investigation owns
  `experiments/baselines/brg/` and `results/brg/`. Only
  [`external/sources.json`](../../../../external/sources.json) is shared.
- Stop after this activity and report for review.

## Investigation scope (later activities)

The user agreed these on 17 November 2026; they shape later activities, not
this one.

- Cases: examples 1–3 of [arXiv 2210.11607](https://arxiv.org/abs/2210.11607),
  seven runs:
  1. glider at ratios 0.33 and 10;
  2. 35-term star at 0.9, with full data and with limited data;
  3. cavity at ratios 0.9 and 2.

  Example 4 (three stars) is out, because our inverse fits one curve.
- Their code is not run on TG-002.
- Clean data first; noise only after the clean results are reviewed.
- Our method gets exactly the data BRG gets and chooses its own frequency
  schedule within it. It is given the known contrast, as BRG is.
- Our forward solver is checked on each true shape before any inversion.
- Score: set-difference area over true area (the paper's measure), contrast
  error and wall time.
- Extending `solvers/bem_inverse/` for their data (a full sources × receivers
  table and plane waves) comes later in this investigation. The user did not
  fix the order relative to CSI.

Note for later: the drivers for the paper's examples are not public. The
repository, its branches and `mrachh/rla-monograph-tests` have no glider or
35-term star script. The paper cases will be rebuilt from the paper's text.

## Setup

- Checkout: `~/neural_bem_external/inverse-obstacle-scattering2d` at `bda24bd`.
- gfortran 11.4 and gcc 11.4 are installed. MATLAB R2026a, run as
  `matlab -batch`. One MATLAB process. No GPU.
- Build: the README's `make install` target does not exist. The target is
  `make matlab`. MATLAB's `mex` is not on `PATH`, so pass it explicitly:
  `make matlab MEX=/usr/local/MATLAB/R2026a/bin/mex`.

## Steps

1. **Build.** `make matlab` as above, then `startup.m`.
2. **Test suite.** `tests/test_all.m`, which should print 3 out of 3 tests passed.
3. **Transmission tests.** `tests/test_frechet_ders_trans.m` and
   `tests/test_transmission_multi.m`.
4. **Data generation example.**
   `examples/data_generation_scripts/starn_transmission_tensor_data.m`.
5. **Transmission inverse example.** `tests/driver_charlie_transmission.m`:
   - cavity shape, interior wavenumber = 1.5 × exterior, so ratio 2.25;
   - k from 1 to 30 in steps of 0.25 (117 frequencies);
   - 10k directions × 10k receivers at radius 10;
   - steepest descent, at most 100 iterations per frequency, unit-disk start.

   Compare by eye with the paper's Figure 7 (the same cavity at ratios 0.9 and
   2). There the obstacle solver fails to resolve the cavity.

Known problems in step 5, to debug and record:

- `ifgenerate = 0` expects a saved data file that is not shipped. Generate it
  first with `ifgenerate = 1`.
- The script runs `../inverse-obstacle-scattering2d/startup.m` and writes data
  to `./`. The wrapper sets the paths and points outputs at `results/brg/`.
- It calls `rla.rla_inverse_solver` with 8 arguments; the solver takes 7.
- The interior wavenumber `bc.transk` is set only while generating data. The
  inversion keeps its last value (k = 30) at every frequency, and nothing in
  `src/+rla/` updates it. Find out how the authors handled this. Report it
  before trusting any inversion result, since it changes the physics.

A wrapper in `experiments/baselines/brg/` runs each script, saves the
workspace outputs (curves, residuals, timings) and every open figure.

```bash
cd ~/neural_bem_external/inverse-obstacle-scattering2d
make matlab MEX=/usr/local/MATLAB/R2026a/bin/mex 2>&1 | tee <repo>/results/brg/examples/build.log
matlab -batch "run('<repo>/experiments/baselines/brg/run_example.m')" 2>&1 | tee <repo>/results/brg/examples/<step>/matlab.log
```

## Success criteria

- The build and steps 2–4 finish without error, and the tests pass.
- Step 5 runs through all 117 frequencies with the interior wavenumber
  matching each frequency. Its residual history and final curve are saved.
- The step 5 result agrees with Figure 7 of the paper by eye.
- Any patch is small, saved and explained.

## Run limits

- Build and steps 2–4: expected minutes. Stop and report if any takes over
  30 min.
- Step 5: data generation plus inversion, at most 4 h wall time. If the limit
  is reached, save progress and report how far it got.

## Outputs

- Code: `experiments/baselines/brg/`.
- Raw outputs and logs: `results/brg/examples/<step>/`.
- Report figures: `docs/iterations/brg_adaptation/01_run_published_examples/figures/`.
- Patches: `external/patches/brg/`.
- After running: `results.md` here, then commit and push.

## Checkpoint commands and checks

Run each stage with `python experiments/baselines/brg/run_stage.py STAGE`,
where STAGE is `build`, `suite`, `transmission`, `data`,
`low_frequency_unpatched`, then `low_frequency_fixed`. Failed attempts are
kept in separate folders. MATLAB and MEX need approved sandbox access.

The physics check uses the shipped cavity at k = 1, 1.25, 1.5, its 500-point
minimum and ceil(10k) angles/receivers. One inverse step from the exact true
shape isolates frequency handling: require relative residual below 1e-8.
The unpatched run starts with stale [45,30], exactly as after generation.
This is a diagnostic, not a reconstruction result or a change of baseline
settings. A fixed run must use the same harness and inputs.

Diagnostic refinement, 17 November: the exact-true-shape test exposed an
unrelated zero-gradient MEX crash after the frequency fix. Repeat at k=1,
1.25,1.5 from the shipped unit disk, one iteration, comparing the RLA output
to a direct correctly parameterized single-frequency call. Require residual
and curve differences below 1e-10. Retain the prior failed diagnostic.

## Coordinator decision: full shipped example, 17 November

The coordinator approved patches 03 and 04 after reviewing the pinned
source and both upstream branches. Their review: `bc.q` is set by the driver
and otherwise unread in `src/+rla/`; the driver says `transk` changes at
every frequency and generates data with `[kh*bc.q kh]`. Patch 04 repeats
that operation in the frequency loop. Patch 03 passes the fields already
read by the transmission derivative and changes no other boundary type.
Neither `issue-computefields-trans-bug` nor `devel-impedance` has an
alternative fix to copy. This is the coordinator's review.

Run `python experiments/baselines/brg/run_full.py`. It invokes
`run_shipped_cavity.m` with eight compute threads, the shipped settings and
a seven-argument solver call. Generate the full data set before inversion,
as in the driver. Save each completed frequency atomically. Resume from
the last saved exact curve state; do not repeat completed frequencies.

The four-hour limit covers all attempts' MATLAB process wall time, including
data generation, inversion and saving. A hard process timeout enforces the
remaining budget. An interrupted frequency is repeated on resume only if
there is budget left. This is the shipped example, never a table B result.

Outputs: `results/brg/examples/shipped_cavity_full/` holds compact curves,
residual histories, iteration counts, exit flags, timings, JSON and commands.
Its ignored `local/` holds data, exact continuation states and full logs.
Commit bulk-file commands and SHA-256 values, not bulk arrays. Commit about
5 MB at most for this run; retain everything previously pushed unchanged.
The comparison figure goes under this activity's `figures/shipped_cavity_full/`.

At the end report the driver's unnormalized symmetric-difference area and
the normalized area error separately, with the true/recovered cavity figure.
CSI may overlap, so timings remain indicative. Use path-limited commits
because the Git index is shared.

While step 5 runs, draft activity 02 for the paper's examples 1–3, seven
runs as requested. Give exact shapes, reachable settings and every gap.
Do not run activity 02.
