# Launcher checks before the first run

## Current time-target rule checked, 18 November 01:28 UTC

The user's rephrased 01:24 rule supersedes the earlier time-stop logic.
The real-folder dry run again passed with writes and process creation
forbidden. It reports a six-hour informational target and still refuses
the active old launcher. No MATLAB process was started or signalled.

An updated temporary fake-worker run changed the target to a tiny value
after launch. All ten cases completed in order despite passing it; the
target-exceeded event was logged and the forecast did not stop the run.
An explicit resume after passing the target kept the original start and
never reran or overwrote finished launches. A mock termination function
was never called because of time. Separate mock-only checks confirmed
that urgent memory protection and explicit STOP still reach the intended
stop control. The real old campaign and its workers were untouched.

The held eight-frequency resume was also checked in a temporary folder
with its original start thirteen hours earlier and a twelve-hour target.
It ran all seven fake remaining cases, recorded the overrun, never called
time termination and kept the original state file. It remains unlaunched.

## Earlier preparation checks

18 November 2026, 01:04–01:06 UTC. No MATLAB was launched by these checks.

Real-folder --dry-run passed with write-mode file opens and subprocess
creation forbidden. It lists all ten cases, frequencies 1/2/3 GHz and
the initial six-hour limit. It refuses the still-running old launcher,
its unfinished state and pending first-batch outcomes. It does not create
the new results folder or modify any old campaign file.

A temporary fake-worker check ran the controller without MATLAB or git
mutations: ten cases in the agreed batch order; an intentionally high
first-batch forecast was recorded without stopping; changing the temporary
budget text from 6 to 7 was read and logged; explicit resume kept the
original start time and never reran or overwrote existing launch records;
an interrupted worker's snapshots were preserved; STOP was kept and
blocked further start. The real initial budget remains six hours.

A temporary real-data check copied only truth metadata into temporary
folders and read the three frozen parent tables. Native driver copies
contained fre=1:3 and 2048 iterations, with only MF-CC-CSI. Exact byte-row
subsets matched the parent arrays and had 5292 rows, 1764 per frequency,
with the same mask/pair order. Parent and expected selected-file hashes
are recorded in data_note.md. No BEM/scoring/upstream code was edited.

Commands use PYTHONPATH=solvers:., OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1 and EMNerf Python -B. Code also passed git diff --check.
The callback's raw-array equality check is reused unchanged from activity
04; the low-band launcher checks four counts, finite arrays, selected
frequencies and the 3 GHz raw-image reference when each fit exits.
