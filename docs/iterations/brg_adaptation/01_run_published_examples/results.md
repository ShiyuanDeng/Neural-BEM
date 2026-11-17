# BRG published examples: activity 01

Started 17 November 2026 with the coordinator's go. In progress; the full
117-frequency run is held for the step 5 physics checkpoint.

## Run record

| UTC date | Step | Result | Wall seconds | Evidence |
|---|---|---|---:|---|
| 2026-11-17 | Build in sandbox | Fortran compiled; MEX could not write MATLAB preferences | 3.52 | [log](../../../../results/brg/examples/build/matlab.log), [command](../../../../results/brg/examples/build/run.json) |

The failed build is retained. MATLAB needs access outside the sandbox for
preferences and online licensing. The retry succeeded with approved access;
the user subsequently enabled unrestricted access.

Build retry: all four MEX files built in 1.87 s;
[log](../../../../results/brg/examples/build_retry/matlab.log).

Wrapper: MATLAB uses eight compute threads, disables interactive pauses,
and exports open figures. Two script path substitutions are applied in
memory only; [patch](../../../../external/patches/brg/01-wrapper-script-paths.patch).
No numerical settings are changed.

## Suite and thread check

17 November: upstream `test_all.m` passed 3/3. Process wall time 12.08 s.
MATLAB R2026a started with one compute thread; wrapper set eight. Median of
three complex dense 2500-by-2500 solves: 0.717075 s at one thread, 0.195035 s
at eight (3.677x); relative residual 4.04e-12.
[Evidence](../../../../results/brg/examples/suite/matlab.log).
These setup timings may overlap CSI and are not final comparison timings.

## Transmission tests

17 November: 23.97 s process wall time. The derivative script completed all
seven modes and six step sizes; [errors](../../../../results/brg/examples/transmission/frechet_errors.json).
The shipped script has no pass assertion. The multi-component test then
crashed in `rla.get_fw_mats`, line 223: `src_info.L` is absent after
`geometries.get_multi_comp`. No physics patch was made for this separate
problem. [Failure log](../../../../results/brg/examples/transmission/matlab.log).

The full derivative workspace is 82 MB and stays local, with command and
SHA-256 in [manifest](../../../../results/brg/examples/transmission/manifest.json).
The compact errors and multi-component failure workspace are committed.

## Data-generation first attempt

17 November: the shipped star script stopped before generating data because
its initial `save` names undefined variable `lam`. This is unused for the
transmission example. The retry will remove only `lam` from that save call.
[Failure log](../../../../results/brg/examples/data/matlab.log).

## Shared-checkout note

Commit `abade42e8` also captured CSI files staged concurrently by the CSI
agent, although BRG staged only its own paths. The files were preserved and
pushed. Subsequent BRG commits use explicit path-limited `git commit --only`
to avoid this shared-index race.

## Data-generation retry

17 November: completed 17/17 frequencies, k=1 through 5, with 90 directions
and 90 receivers (8100 scattered-field entries per frequency).
Process wall time 11.77 s. Analytic error estimates range from
6.22e-07 to 2.72e-05;
[summary](../../../../results/brg/examples/data_retry/data_summary.json).
The original dissipative transmission parameters are unchanged. This star
example is not the clean equal-density cavity baseline.

The data file is committed. The full workspace exceeds 50 MB and stays
local with its command and checksum recorded. Only the output path and
undefined `lam` save were changed in memory;
[patch](../../../../external/patches/brg/02-remove-undefined-lam-save.patch),
[executed source](../../../../results/brg/examples/data_retry/executed_script.m).

## Low-frequency check: first attempt

17 November: 4.55 s wall time. The actual inverse path crashed before a
residual could be checked: `update_inverse_iterate` replaces `bc` with a
struct containing only `type` and `invtype`, then passes it to the
transmission derivative, which requires `transk`, `transa`, and `transb`.
[Log](../../../../results/brg/examples/low_frequency_unpatched/matlab.log).
The next check changes only that struct copy, then checks the stale-frequency
residual before applying the frequency fix. This is a second upstream bug.

## Low-frequency stale-wavenumber check

17 November: 19.30 s wall time. With only the derivative struct-copy fix,
one inverse step from the true cavity gives relative residuals 6.087825,
6.524013 and 5.198061 at k=1,1.25,1.5. The harness correctly fails its 1e-8
limit. [Measurements](../../../../results/brg/examples/low_frequency_stale/check.json).

Ranked explanations before the frequency patch: (1) stale transmission
wavenumbers, predicted to vanish after synchronizing both with each k;
(2) a misread `bc.q`, predicted to persist unless its meaning changes;
(3) a field normalization error, predicted to persist with correct k.
Only (1) is changed next. The derivative patch preserves the input physics
struct; it does not change any parameter.

## Corrected-frequency exact-fit diagnostic crash

17 November: 4.32 s wall time. Updating both wavenumbers makes the exact
true-shape data residual zero. The shipped steepest-descent code computes
a zero-over-zero step before testing its residual stop; NaN geometry reaches
`curve_resampler.mexa64`, which segfaults.
[Redacted log](../../../../results/brg/examples/low_frequency_fixed/matlab.log).
No optimizer or MEX patch is proposed at this checkpoint.

The diagnostic is revised to start from the shipped unit disk and compare
one RLA step with a direct single-frequency inverse call supplied the correct
wavenumbers. This tests the actual frequency-loop boundary without the
exact-fit corner case. Both calls keep the same data and optimizer settings.

## Unit-disk diagnostic, stale frequencies

17 November: the direct reference residuals after one step were 1.324969,
2.096010 and 1.889293. RLA with stale [45,30] gave 4.668302, 4.697863 and
3.964944, with relative curve differences 0.59655, 0.27016 and 0.25518.
The intended assertion fails at all three frequencies.
[Evidence](../../../../results/brg/examples/low_frequency_stale_disk/check.json).

## Checkpoint result: corrected unit-disk calls

17 November: k=1,1.25,1.5 all pass. RLA and the direct reference produce
identical residuals and identical curves (differences exactly zero in the
saved double-precision results).
[Measurements](../../../../results/brg/examples/low_frequency_fixed_disk/check.json).
This confirms frequency plumbing and the derivative argument fix. It is
not a full reconstruction or a check at high frequencies.

The minimal physics fix is three lines in `rla_inverse_solver`: at every
transmission frequency with `bc.q`, reset `bc.transk` to `[bc.q*kh kh]`.
The additional one-line fix copies `bc` into the derivative call instead
of dropping its transmission fields. See
[patch 04](../../../../external/patches/brg/04-update-transmission-wavenumbers.patch) and
[patch 03](../../../../external/patches/brg/03-preserve-transmission-derivative-parameters.patch).

Source and paper agree that a fixed known material has both wavenumbers
scale with frequency. The driver's `bc.q=1.5` is the interior/exterior
wavenumber ratio; its squared ratio is 2.25 and susceptibility is 1.25.
The proposed update restores the same material used to generate its data.
This is an inference from the public source and the paper, not evidence of
how the authors repaired their unpublished drivers.
[Paper: equation 1, Remark 1.1 and section 4.1](https://arxiv.org/html/2210.11607).

The stale state is actually both interior 45 and exterior 30; the incident
wave still uses the current `kh`. Loading data in a fresh run leaves
`bc.transk` absent, rather than stale. The fix covers both cases when `bc.q`
is supplied. Drivers without `bc.q` retain their explicit transmission data.

In the [information chain](../../../reference/inverse_information_chain.md),
this is the BRG counterpart of A2–A4 frequency consistency and B7 derivative
inputs. These external BRG calls are not on our default BEM inverse path.
No `solvers/` or shared comparison code changed.

## Pending decision and limits

Stopped at the coordinator's requested checkpoint. The full 117-frequency
run has not started; Figure 7 has not been compared. Activity 01 remains
incomplete because the multi-component test failed and step 5 is pending.

After the coordinator's answer, finish the wrapper to checkpoint each data
and inverse frequency, restore the last curve on resume, and enforce a
cumulative four-hour data-plus-inverse budget. Keep the shipped single
unit-disk start, steepest descent and 100 iterations; no paper-setting
substitutions in activity 01. Use seven solver arguments; the optional
[driver patch](../../../../external/patches/brg/05-remove-obsolete-driver-argument.patch)
removes its unused eighth argument.

The multi-component missing-perimeter failure and exact-fit zero-gradient
MEX crash remain unresolved. Neither is hidden by a success claim.
The shipped derivative test shows roughly quadratic remainder decay in
all seven modes, ending between 7.07e-13 and 4.99e-12; this does not validate
its derivatives independently at unequal density.

All process timings and commands are in
[run summary](../../../../results/brg/examples/run_summary.json).
Timing overlap with CSI is permitted for activity 01; final comparison
timing must run alone. Two workspaces above 50 MB remain local with their
checksums, and all committed artifacts stay below 50 MB.

[Data and convention handoff](data_handoff.md).
[Patch status and reproduction](../../../../external/patches/brg/README.md).
