# Prepare simulated TG-002 cases: results

Completed 17 November 2026. Three authorized MATLAB runs completed, with
no failed run: measured snapshots, finer-grid forward generation, and a
64-iteration timing probe. Their combined launcher wall time was
2570.65 s (42 min 51 s). No TG-002 campaign was started in this activity.
Only the frozen circle at relative permittivity 4 was generated and probed.

## A. Registered measured-cylinder scores

The numerical axes use x=radius*cos(angle), y=radius*sin(angle), first
array dimension x, second y. The right-handed registration from the former
sketch-right/sketch-up declaration is
`(x_numerical,y_numerical)=(y_sketch,-x_sketch)`. The nominal true centre
is **(0,+30) mm**, radius 15 mm, relative permittivity 3 +/-0.3.
Nothing was fitted to our recovered centroids or moved in the raw images.

[Frame reading and its limits](frame.md) records the database setup figure,
the shipped angle conversion and the independent positive-y sign check.
The [database introduction](https://doi.org/10.1088/0266-5611/17/6/301)
gives an approximately 30 mm displacement, not surveyed coordinates.
Its cross-section is unlabelled. The signed registration therefore also
uses section 4.2.1/Figure 6 of Belkebir and Tijhuis's
[same-file 2001 paper](https://www.fresnel.fr/perso/belkebir/Articles/Ip01_Belkebir.pdf),
whose domain is centred at y=+2.8 cm. That reconstructed domain centre is
not substituted for truth. The companion paper's approximate antenna
radii are listed in reverse order to the shipped driver; no settings
from it are imported. The numerical baseline remains 0.72 m transmitters,
0.76 m receivers, including the transmitter-only -2.5 degree correction.

Half-peak protocol-1 scores, recomputed from the three saved raw arrays:

| Method | Support mm2 | Centroid x,y mm | Mean epsilon_r | Set-difference / true area | Centroid error mm |
|---|---:|---|---:|---:|---:|
| MF-CC-CSI | 736.537 | 1.887,26.351 | 2.72927 | 35.123% | 4.108 |
| MR-CSI | 715.659 | 1.615,26.282 | 3.01211 | 34.223% | 4.054 |
| CSI | 566.504 | 1.838,26.530 | 3.28088 | 38.473% | 3.927 |

These spatial errors are against nominal experimental geometry; they
must not be confused with support-area bias alone (+4.2%,+1.2%,-19.9%).
All sensitivity scores at 0.3/0.7 are in
[registered_scores.json](../../../../results/csi/preparation/2026-11-17_frame/registered_scores.json).
The activity-02 files remain unchanged as history. No measured inversion
was rerun for this registration.

## B. Measured MF-CC-CSI snapshot run

Same measured file, 112-by-112 grid, 1.25 mm cells, 36 sources, eight
frequencies 1-8 GHz, back-propagation start, and 2048 iterations.
The owned driver enabled the native diary and used the function's native
every-64 raw `Mchi` history. `recflag` does not save contrast checkpoints
itself. Display masking was omitted. No numerical function was changed.

Run 22:16:18.946-22:54:34.522 UTC; native time **2285.737458 s**,
launcher wall **2295.575705 s**. The final raw complex array equals the
activity-02 final array exactly (maximum difference zero).

| Iterations | Support mm2 | Mean epsilon_r | Area difference from 2048 | Mean difference from 2048 |
|---:|---:|---:|---:|---:|
| 128 | 826.738 | 2.36369 | 12.247% | 13.395% |
| 256 | 785.394 | 2.49025 | 6.633% | 8.758% |
| 512 | 771.826 | 2.56841 | 4.791% | 5.894% |
| 1024 | 760.404 | 2.64475 | 3.240% | 3.097% |
| 2048 | 736.537 | 2.72927 | 0 | 0 |

**2048 is the smallest requested count meeting both 1% tests.** Mean
contrast here is epsilon_r, the benchmark's squared-wavenumber ratio.
The JSON also reports mean susceptibility and its differences: at 1024
the latter is 4.888% below its final value, so that definition would not
change the selected count either. This is stability relative to the
2048 image, not a new stopping rule or proof of convergence beyond 2048.

The images retain a compact circular support near positive y. The edge
sharpens and mean contrast increases; there is a faint outer-grid line.
The support remains below the nominal +30 mm centre. See
[raw snapshot images](figures/snapshots_contrasts.png),
[cost curve](figures/snapshots_cost.png), and
[scores and resources](../../../../results/csi/preparation/2026-11-17_snapshots/scores.json).

## C. One native-forward pipeline

[Pipeline notes](pipeline.md) identify the package routines and the exact
table/calibration/sign path for later BEM ingestion. There is no shipped
complete synthetic-case driver. Our owned assembly driver uses unchanged
native FDFD material averaging/matrix builders and the native receiver
kernel. It does not use our BEM forward. No upstream file was edited.

The frozen TG-002 circle has radius 50 mm, centroid
(18.021345,12.618682) mm after mapping the scene centre to the Fresnel
origin, and relative permittivity 4. The data grid is 332-by-332 at
0.625 mm; inversion is 166-by-166 at 1.25 mm. Both half-widths are
103.75 mm. Native dielectric averaging at Ez nodes is retained.

Run 22:55:10.373-22:55:52.845 UTC. Native forward generation took
**36.365080 s**, wrapper wall **42.471029 s**. The seven-column table has
14112 rows, preserving all eight frequencies and exactly the original
36-source,49-measurements-per-source mask. Maximum relative system
residual was **1.5755e-12**; the native true/background material-matrix
identity agreed within **1.3372e-16**. These checks do not replace the
later independent BEM forward check on this same frozen data file.

The local git-ignored data file is
`results/csi/preparation/2026-11-17_generate/synthetic_input.txt` (2298309 bytes).
SHA-256: `34ed9276fb6680d01ff6e7a7c26c8d19fb70fe5df4dbe1a81de39e025924cefe`.
The [manifest](../../../../results/csi/preparation/2026-11-17_generate/manifest.json)
also hashes the true nodal/Ez material arrays and regeneration command.

## D. 166-by-166 timing probe and resources

MF-CC-CSI only, same table/calibration/start and eight frequencies,
64 iterations. Run 22:56:30.112-23:00:22.714 UTC. Native time
**220.208547 s**, or **3.440759 s/iteration**; wrapper wall
**232.601124 s**. Eight compute threads were set in the wrapper.
Measured MATLAB CPU time during the native window was 1144.79 s,
equivalent to **5.199 CPU cores**. A process-tree check showed helper
CPU time negligible beside MATLAB. The host exposes 24 cores without SMT.

Three concurrent eight-thread fits are a reasonable CPU ceiling, not a
measured three-fit speedup. Native-loop host CPU use averaged 10.56 cores
under BRG overlap; memory bandwidth and other runs can affect rates.
Peak MATLAB RSS was 4.751 GiB; including descendants, 6.447 GiB.
Three such families plus the required 14 GiB reserve need at least
**33.34 GiB available before launch**, with additional headroom prudent.
If that headroom is absent, only two should be launched. This family-RSS
sum is conservative because some library pages can be shared.

| Run | Other MATLAB jobs observed while active | Peak MATLAB RSS GiB | Minimum available GiB | Minimum unused GiB |
|---|---|---:|---:|---:|
| Measured snapshots | 3-4 | 2.953 | 26.889 | 15.963 |
| Forward generation | 3 | 1.862 | 29.360 | 18.273 |
| Synthetic probe | 2-3 | 4.751 | 26.432 | 15.318 |

Completion polls also record one fewer job after our own process exits.
The 14 GiB reserve held throughout, including unused memory. The first
monitor stored main-process CPU/RSS; the later runs also stored family
RSS and host CPU. Times are indicative and must not be presented as
isolated final-comparison timings. All jobs used detached launchers.

The same native per-source calibration was exercised on the generated
table. Recomputed coefficients differed from `1/omega_normalized^2` by
at most **2.86e-14** relative; the native incident field differed from the
physical unit Green field by at most **9.92e-14** relative.
[Calibration CSV](../../../../results/csi/preparation/2026-11-17_probe/calibration.csv)
records all 288 source/frequency coefficients.

As a pipeline preview only, the 64-iteration circle has 5.694% area error,
mean epsilon_r 2.35081 (truth 4), and centroid error 1.483 mm. The image
has a clear off-centre circular edge and an underestimated interior.
This is not a table-C result. See [image](figures/probe_contrasts.png),
[cost](figures/probe_cost.png), and
[raw scores](../../../../results/csi/preparation/2026-11-17_probe/scores.json).

## E. Campaign cost and the new six-hour limit

The measured stability count is 2048, so the requested cost at that count
and at 2048 is identical. CC uses the measured synthetic rate above.
MR/CSI rates are extrapolated from their activity-02 ratios to CC:
0.972573 and 0.889785. Resulting estimates are 3.346387 and
3.061536 seconds/iteration. Only CC on the larger grid was actually timed.

| Methods, ten contrast-4 shapes | Native inverse hours | Serial total hours | Ideal three-worker lower bound hours | Three-worker scheduled total hours |
|---|---:|---:|---:|---:|
| MF-CC-CSI only, 2048 | 19.574 | 19.726 | 6.654 | **7.961** |
| All three, 2048 | 56.028 | 56.249 | 18.828 | 18.865 |

Totals include measured wrapper overhead per fit and 0.118 hours for ten
serial forward generations. Generation of the already prepared circle
can be reused, saving about 42 s. Three-worker schedules assume unchanged
per-fit rates and sufficient memory, so they are optimistic about
contention. MF-only has four batches (3+3+3+1), each full fit about
1.961 h. If only two fits fit in memory, it is slower still.
[Cost JSON](../../../../results/csi/preparation/2026-11-17_cost/campaign_cost.json)
includes every earlier observation, rates and assumptions. The earlier
linear cell model understated the measured larger-grid rate; shape,
contrast, sparse solves and overlap were not separated experimentally.

During this activity the coordinator conveyed the user's campaign go:
"okay for now keep only mf-cc-csi, and run them three at time".
The coordinator also set **6 h total**, with instructions to report an
over-budget probe before starting. Even perfect division by three gives
6.65 h, and the requested batches forecast **7.96 h**. **The campaign is
therefore not started under that limit.** Activity 04's plan records the
go and the cost conflict; no settings or iteration counts are cut.

## Evidence and changes

Protocol-1 region scoring is imported from the unchanged
`experiments/comparison/scoring.py`. All components and holes count;
support uses half the signed peak, with 0.3/0.7 sensitivities. Raw complex
unmasked contrasts retain numerical coordinates and allow rescoring.
No solvers or comparison code were edited. No new upstream patch was
needed; compatibility patches 0001/0002 remain in effect.

Compact payloads before manifest overhead: snapshot run 0.976 MB,
forward run 0.022 MB, probe 1.992 MB. Figures live in this activity's
`figures/`. Full histories, material arrays and the data table stay local
and ignored, with commands and SHA-256 in per-run manifests. Each run
was committed and pushed separately. MATLAB's software-graphics warning
is retained in the probe log; no run failed.

Open points are the nominal measured-position accuracy, the already open
MR-CSI/Figure-5 discrepancy, independent BEM/FDFD agreement, unmeasured
three-fit scaling, and the six-hour campaign budget. The next action
requires a coordinator decision on that budget; the baseline settings
remain fixed.
