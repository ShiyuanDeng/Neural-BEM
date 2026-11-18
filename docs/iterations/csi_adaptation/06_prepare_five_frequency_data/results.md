# Five-frequency data results

All ten tables are frozen. Runs: 2026-11-18T03:59:27Z to 2026-11-18T04:04:30Z.
User choice: 0.5, 1, 1.5, 2 and 2.5 GHz on the same observations for both methods.
No inverse fit ran in this activity. No failure or stopped job occurred.

The original generator, old tables, frozen truth and upstream files were read only.
The new driver changes only template construction, the frequency list and its printed frequency format.
Settings: relative permittivity 4, 332 × 332 nodes, 0.625 mm cells, original domain and five-cell border;
unchanged dual-node material sampling/averaging, physical Green source, calibration and receiver kernel.
Each final table has 8820 finite seven-column rows and the parent pair order and 49-per-source mask.
At 1 and 2 GHz, generated total, incident and scattered fields reproduce every parent value exactly;
relative L2 and maximum pair-relative differences are zero. Final files retain the parent line bytes.

| Shape | Max native residual | Reproduction error | MATLAB wall (s) |
|---|---:|---:|---:|
| circle | 4.2928296e-12 | 0 | 28.189 |
| kite | 3.0493032e-12 | 0 | 20.505 |
| peanut | 3.7562502e-12 | 0 | 23.066 |
| star | 4.2414201e-12 | 0 | 31.293 |
| asymmetric | 4.1598552e-12 | 0 | 27.672 |
| c_shape | 3.9093542e-12 | 0 | 29.243 |
| hook | 3.3631694e-12 | 0 | 26.149 |
| cross | 4.0986237e-12 | 0 | 27.253 |
| cog | 4.2941818e-12 | 0 | 29.829 |
| aphex_twin | 2.4051245e-12 | 0 | 22.606 |

Circle comparison at the frozen true radius, centre and permittivity, without fitting:

| GHz | Relative L2 / table (%) | Relative L2 / exact (%) |
|---:|---:|---:|
| 0.5 | 0.44203362 | 0.44397601 |
| 1 | 0.17232596 | 0.17237011 |
| 1.5 | 0.13467985 | 0.13462665 |
| 2 | 0.12604902 | 0.12599062 |
| 2.5 | 0.17672086 | 0.17656380 |

All five errors are below 1%. The 0.5 GHz result passes at 0.444% using the exact-series norm.
The unchanged grid and border therefore pass the required circle check in this band.
This does not replace the BEM side’s true-shape checks for the other nine shapes.

Ten sequential MATLAB jobs used 265.805 s summed wall time; first-to-last elapsed time was 303 s.
Peak job-family RSS was 2.265 GiB; minimum available memory was 27.339 GiB, above 14 GiB.
Eight compute threads and nice 10 were recorded for every job. The resource policy was reread before every launch;
each launch record contains that policy and memory sample. No time limit or inverse launcher was used.

Commands (repository root):
```bash
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.prepare_five_frequency_data --shapes circle
PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /home/drdeng/miniconda3/envs/EMNerf/bin/python -B -m experiments.baselines.csi.prepare_five_frequency_data --shapes kite peanut star asymmetric c_shape hook cross cog aphex_twin
```

The [data note](data_note.md) gives all ten absolute table paths and SHA-256 values, row layout, sign convention and per-shape checks.
The [summary](../../../../results/csi/tg002/2026-11-18_five_frequency_data/summary.json) records timings, resources and hashes.
Each shape folder holds manifest.json, checks.json, sources.json and generated/ native summary, launch record and compressed log.
Full final and generated tables and material maps remain local and git-ignored. Compact evidence was pushed after each shape.
Circle was pushed in 81f232f15; the tenth table was pushed in d2dd1807e.

```text
Activity: csi_adaptation/06_prepare_five_frequency_data, 18 November 2026
Runs: 10/10; wall time 0:05 (265.805 s summed MATLAB, 303 s elapsed)
Result: 10 frozen tables; 8820 rows each; all 1/2 GHz reproduction errors zero.
Result: native residuals at most 4.29418e-12; circle errors below 1% at all five frequencies.
Failures: none; compressed logs in each shape’s generated/matlab.log.gz.
Upstream patches: none
Changes to our code: new generate_five_frequency_data.m and prepare_five_frequency_data.py only.
New unknowns: BEM true-shape checks are owned and reported by the BEM side.
Proposed next activity: consume these frozen tables in the assigned checks/fits; needs user decision: none
```
