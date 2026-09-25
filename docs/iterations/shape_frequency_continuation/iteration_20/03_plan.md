# SC-039 — raw boundary data along every saved trajectory

2026-09-25. Owner: Claude (Opus 5.5). Independent reviewer: unassigned.
**Approval status: APPROVED.** The user asked to "rebuild atlas for different
trajectories on different scenes and different algos", then said "i just want
all the data on those trajectories and later build whatever atlas we want",
asked that the M>9 runs count, and replied "yes" to the proposed trajectory
and shot list. Existing checkout and branch; no new branch or worktree.

## Purpose

Collect data, not an atlas. The existing atlas (SC-026) differentiates with
respect to arclength normal harmonics. The user's definition differentiates
with respect to the stored boundary's Cartesian Fourier coefficients, with its
parametrization fixed. Both, and any other coordinates, are contractions of the
same boundary kernel (`forward.shape_jacobian`):

`J[s, r, c] = (ki^2 - k^2) sum_x w(x) u_s(x) v_r(x) h(x, c)`

where u_s and v_r are the forward and reciprocal boundary traces, w the
arclength weights and h the normal velocity of coordinate c. Storing u, v and
the node geometry at each state makes every later first-order atlas a matrix
product with no field solves. Nothing here selects, fits or scores an update.

## Trajectories

Every accepted state of these saved runs, each followed from the common start
circle (branches include their parent's prefix):

| ID | Run | Cases |
|---|---|---|
| A | Original hybrid, SC-029 baseline (K=192, M 3/5/7/9, 4 cumulative frequencies) | all six |
| B | SC-035 low state band (K 8/12/16/20, then K=192 release) | star, C, kite, peanut |
| C | SC-035 K=192 centred control | star, C, kite, peanut |
| D | SC-036 ray path | star, C, kite, peanut |
| E | SC-037 wider ladder (K 8/16/32/64/192), branching from B after stage 1 | star, C, kite, peanut |
| F | SC-038 released M (11/15/19, all 19 frequencies), branching from B's stage 4. Kite follows the selected 768/1536-node M=15 replay and the M=19 completion; its stopped 512-node M=15 attempt is a separate branch | C, kite |
| G | SC-038 M=9 control, and kite's unchanged 768/1536 replay | C, kite |
| H | SPD-L, SC-034 arm L (Cartesian K 4/6/8/10, polar-angle parameter), including stage checkpoints absent from a hard-stopped trajectory log | all six |

Where a run's recorded endpoint (result or checkpoint) is not its last history
row, as after a wall-limit hard stop, it is appended. Consecutive repeats of a
state at stage boundaries are removed. A "shot" is a distinct stored curve
(coefficients padded to K=192; the parametrization is part of the key), so a
state shared by branches is computed once and indexed by every trajectory.
The six true shapes are separate, evaluation-only reference shots.

## What each shot stores

At all 19 catalog frequencies (0.25–2.5 GHz, not only those a run was using),
on 512 and 1024 nodes, and additionally 768/1536 where a run itself used them:

- node parameter t, points, normals, arclength weights, curvature, speed;
- forward traces (Dirichlet and Neumann) for the 24 sources and reciprocal
  traces for the 24 receivers, exactly as `shape_jacobian` computes them;
- the full 24x24 source-receiver prediction (the paired data are its diagonal),
  forward and reciprocal system residuals, and 512/1024 prediction agreement;
- per trajectory step: stage, iteration, M, stored K, the run's active
  frequencies and grid, its saved loss and source-file hashes.

Arrays are uncompressed `.npz`, excluded from Git; the manifest, per-shot
records with array hashes, logs and this plan are tracked.

## Pilot gate (before the full collection)

Six diverse shots: the start circle, the collapsed hybrid peanut, the sharp
SC-035 kite, the SC-038 C endpoint, the 768-node SC-038 kite endpoint and a
hard-stopped SPD-L C. Pass only if, at 0.25, 1.375 and 2.5 GHz on 512 nodes:

1. the paired prediction equals a fresh `solve` bitwise;
2. contracting the stored traces reproduces `shape_jacobian` within 1e-12
   relative, for normal harmonics M=19, Cartesian coefficients |p|<=24 and the
   full 24x24 Jacobian at M=9;
3. each LM-run shot's loss, rebuilt from stored predictions with that stage's
   weights and floor on its own grid, matches the saved history loss within 1e-12.

On failure, fix the collector and rerun the pilot; do not relax a gate.

## Budget

One forward and one reciprocal solve per shot, frequency and grid: at most
about 35,000 of each (867 distinct shots, 15 of them with dense grids, plus 6 true shapes; recorded in `dispatch.json`), with
10 single-thread workers. No wall-clock ceiling beyond the machine's; the
collection resumes shot by shot after an interruption. Disk: about 45 MB per
base shot, about 40 GB in total, against 245 GB free.

## Not included

SC-029's other strategy arms, SC-031/032 metric arms, SPD-008 and rejected
trial candidates. Atlas construction, interpretation and any successor
experiment come later and are not authorized by this plan.
