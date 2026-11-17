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
