# Prepare the five-frequency shared observations

Written 18 November 2026 before any run. Owner: csi-data.
User decision, 18 November 03:43 UTC: “Prepare and freeze the missing-frequency
 data, and give the same observations to both methods.” Frequencies are
0.5, 1, 1.5, 2, 2.5 GHz; all ten TG-002 shapes have relative permittivity 4.
No inverse fit is part of this activity.

Question: can the unchanged generator supply the missing frequencies while
reproducing the frozen observations and meeting the circle's 1% error limit?
Use the original 332 by 332 grid, 0.625 mm cells, domain, five-cell border,
dual-node material assignment and averaging, source calibration, receiver
kernel and frozen geometry. Use one parent frequency for the pair layout.
New drivers are beside generate_synthetic.m; the original and upstream
files are read only. The final 1 and 2 GHz lines retain exact parent bytes.

Budget: ten forward jobs, five frequencies each, circle first. Each uses
eight MATLAB compute threads and nice 10. Read resource_policy.json before
every launch (max_data_jobs defaults to 1 if missing). Run sequentially,
respect the launch memory reservations and 14 GiB floor. No time stop.
The circle must pass before any other shape starts. Stop on any failed check;
preserve failed evidence, publish no failed table and ask the coordinator.

Checks: verify every parent hash before use; reproduce the 1 and 2 GHz
fields to 1e-9 relative L2, including scattered fields and a maximum
pair-relative check; all five native solve residuals below 1e-9; finite
8820-by-7 output, 1764 pairs, 36 sources, 49 receivers per source, exact
parent pair order and ascending frequency per pair. Compare the circle
with the read-only exact_circle function at the frozen true radius,
centre and permittivity: relative L2 below 1% at each frequency, using both
table and exact-series normalizations. No parameter adjustment or fit.

Command (repository root):
```
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.prepare_five_frequency_data --shapes circle
```
Then the same command with the other nine names after --shapes, following
the circle report and push. Each successful table is written under
results/csi/tg002/2026-11-18_five_frequency_data/<shape>/forward/ with
synthetic_input.txt.sha256. Each shape has data.json, manifest.json,
checks.json, native summary and compressed log. Generated check rows stay
under generated/; full tables and material maps remain ignored locally.
Manifest records per-frequency provenance, parent and geometry hashes,
driver hashes and checked source hashes. Results and the shared data note
are in this activity. Commit and push compact evidence by owned paths after
each run, including failed runs; at least once after circle and at completion.
