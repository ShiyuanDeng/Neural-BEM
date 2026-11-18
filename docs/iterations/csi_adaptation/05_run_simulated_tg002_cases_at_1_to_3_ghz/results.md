# Frozen data ready; inverse runs held

18 November 2026. All fit launches are held for the user's review of the
current eight-frequency circle/kite/peanut batch and a new coordinator go
with a frequency list. No activity-05 inverse has started. The directory
name records the earlier 1–3 GHz plan; no band is currently selected.

The seven requested forward-only tables were generated, one MATLAB at a
time, with the original unmodified generator and frozen TG-002 truth.
All 29 source hashes recorded by the old campaign still match. The three
existing inputs were copied by exact hash, giving ten frozen parents at
`results/csi/tg002/2026-11-18_low_band_data/{shape}/forward/synthetic_input.txt`.
Each has a SHA-256 sidecar. Full inputs and material/geometry maps remain
local and ignored; compact metadata/logs were pushed after every case.

The [BEM data note](data_note.md) lists every full parent path/hash and the
initial 1–3 GHz subset path/hash. The parent format keeps eight GHz rows
interleaved per pair: for frequency f, one-based rows are 8*j+f for
j=0..1763. The initial BEM subset is f=1,2,3 (5292 rows). Parent line
bytes, pair order and mask are unchanged; fields use exp(+j omega t),
so the BEM side conjugates once. Every parent remains available for a
different explicit frequency choice. The note does not authorize a fit.

The seven new forward jobs used 385.145 s summed wrapper wall time.
Peak family RSS was 2.259 GiB; minimum available memory was 17.060 GiB,
above the 14 GiB reserve. All returned zero. Each table has 14112 finite
seven-column rows; native solve residuals were below 1e-9. Native threads
stayed eight. The new workers inherited nice 10, giving the existing
batch 1 CPU scheduling priority. No old worker was signalled, no old
campaign output directory was created, and no inverse iterations ran.

Command: `PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
/home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m
experiments.baselines.csi.prepare_low_band_data`. Exact commands, source
hashes, resources, native forward summaries and timestamps are under
[the frozen data root](../../../../results/csi/tg002/2026-11-18_low_band_data/prefetch.json).
The final freeze push was `8d4c6123d`; individual generated-case pushes
and the note were already published before it.

The prepared inverse launcher now verifies and reuses every table by
SHA-256, with no data-generation path. A single explicit `--frequencies`
list controls native frequency blocks, initial back-propagation, objective
averages/update sums, first-frequency conductivity scaling and last-frequency
raw-image reference. No default band exists; resume refuses a changed
list. Temporary checks passed for both 1–4 and 1–5 GHz, including row
counts 7056 and 8820, native driver lists, 2048 iterations and metadata.
No MATLAB was started by these checks. Time remains an informational
target; passing it never stops a fit. The memory guard remains available.

The old batch finished naturally at 02:00 UTC and its final push is
`bff0fd4a8`. Its [review pack](../04_run_simulated_tg002_cases/review_pack.md)
contains all snapshot/sensitivity scores, costs, timings and the figure.
Pending: wait for the new go and frequency list. BEM still checks each true shape against
these exact tables. No upstream numerical patch, solver edit or scoring
change was made for this preparation.
