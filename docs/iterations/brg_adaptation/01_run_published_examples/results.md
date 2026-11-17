# BRG published examples: activity 01

Started 17 November 2026 with the coordinator's go. In progress; the full
117-frequency run is held for the step 5 physics checkpoint.

## Run record

| UTC date | Step | Result | Wall seconds | Evidence |
|---|---|---|---:|---|
| 2026-11-17 | Build in sandbox | Fortran compiled; MEX could not write MATLAB preferences | 3.52 | [log](../../../../results/brg/examples/build/matlab.log), [command](../../../../results/brg/examples/build/run.json) |

The failed build is retained. MATLAB needs access outside the sandbox for
preferences and online licensing. The retry will request that access.

| 2026-11-17 | Build with approved access | All four MEX files built | 1.87 | [log](../../../../results/brg/examples/build_retry/matlab.log) |

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
