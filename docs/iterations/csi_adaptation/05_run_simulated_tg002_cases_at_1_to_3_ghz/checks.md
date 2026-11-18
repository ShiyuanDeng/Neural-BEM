# Launcher checks before the first run

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
