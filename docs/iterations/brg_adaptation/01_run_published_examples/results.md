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
