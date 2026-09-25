# SC-039 — raw boundary data along every saved trajectory

**COMPLETE, 2026-09-25.** 867 trajectory shots and 6 truth references, no failures;
every integrity check passes. Owner: Claude (Opus 5.5); independent reviewer unassigned.
[Plan](../../../../docs/iterations/shape_frequency_continuation/iteration_20/03_plan.md).

This is data for building atlases later, not an atlas. At every distinct
accepted state ("shot") of 34 saved inverse trajectories, and at all 19
catalog frequencies (0.25–2.5 GHz) on 512 and 1024 nodes, it stores what any
first-order shape atlas needs. Any coordinate choice is then a matrix product
with no field solves:

`J[s, r, c] = (ki^2 - k^2) sum_x w(x) u_s(x) v_r(x) h(x, c)`

where u_s and v_r are the stored forward and reciprocal boundary traces, w the
arclength weights and h the normal velocity that coordinate c produces:

- Cartesian coefficient c_p of the stored curve (parametrization fixed):
  h = Re(conj(n) e^{ipt}), and the same with i e^{ipt};
- arclength normal harmonic m (the SC-026 atlas and the update band M):
  h = cos(m s), sin(m s);
- anything else (radial modes, conformal modes, a projected construction)
  through its own h.

## Trajectories and shots

Accepted states per trajectory, each counted from the common start circle
(branches include their parent's prefix). `*` marks a run that ended on a hard
stop; its last accepted state is included.

| Trajectory | Run | States per case |
|---|---|---|
| A_hybrid | Original hybrid, SC-029 baseline (K=192, M 3/5/7/9) | circle 11, star 19, C 81, kite 57, peanut 64, hook 24 |
| B_state_band | SC-035 low state band (K 8/12/16/20, then 192) | star 19, C 22, kite 81, peanut 22 |
| C_state_band_high | SC-035 K=192 centred control | star 19, C 10*, kite 13*, peanut 28* |
| D_ray | SC-036 ray path | star 18, C 69, kite 13, peanut 89 |
| E_wider_ladder | SC-037 (K 8/16/32/64/192), from B after stage 1 | star 19, C 21, kite 73, peanut 22 |
| F_released_m | SC-038 M 11/15/19 on 19 frequencies, from B after stage 4; kite via the 768-node M=15 replay and M=19 completion | C 30, kite 78* |
| F_released_m_512_attempt | SC-038 kite's stopped 512-node M=15 attempt | kite 64* |
| G_fixed_m9 | SC-038 M=9 control on 19 frequencies | C 25, kite 62 |
| G_fixed_m9_dense_replay | its unchanged 768/1536 replay | kite 62 |
| H_spd_l | SPD-L, SC-034 arm L (Cartesian K 4/6/8/10, polar-angle parameter) | circle 6, star 14, C 8*, kite 50*, peanut 8, hook 8* |

That is 34 trajectories, 1,209 trajectory steps and 867 distinct shots; 15
kite shots also carry 768/1536-node data.

A shot is a distinct stored curve; its parametrization is part of its key.
States shared by branches (the start circle, SC-035's stage-one and stage-four
states that SC-037/038 branch from) are stored once and listed under every
trajectory that visits them. Where a run's recorded endpoint is not its last
history row (a wall-limit or hard stop), it is included. The six true shapes
are stored separately under `truth/` and are evaluation only.

## What each shot file holds

`shots/<key>.npz` (not in Git; `shots/<key>.json` records its SHA-256):

| Array | Shape | Meaning |
|---|---|---|
| `coefficients` | (2K+1,) | the stored curve, package units (0.05 m), modes −K..K |
| `parameters_N`, `points_N`, `normals_N`, `weights_N`, `curvatures_N`, `speeds_N` | (N, …) | node geometry on grid N |
| `traces_N` | (19, 2N, 24) | forward Dirichlet (rows :N) and Neumann (N:) traces, per source |
| `reciprocal_N` | (19, 2N, 24) | the same for each receiver, as `shape_jacobian` solves them |
| `prediction_N` | (19, 24, 24) | full source × receiver prediction; the paired data are its diagonal |
| `wavenumbers`, `interior_wavenumbers`, `frequencies_hz`, `contrast`, `length_unit_m`, `center_m` | | constants |

N is 512 and 1024 for every shot, plus 768 and 1536 for the 15 kite shots
that SC-038 itself solved at 768 nodes. Each `shots/<key>.json` also records
the solve residuals, the 512/1024 prediction agreement at every frequency,
timings, and every (trajectory, step) that visits the shot.
`manifest.json` lists each trajectory's steps in order with the stage, the
run's M, stored K, active frequencies, grid and saved loss.

## Checks

**Pilot** ([pilot.json](pilot.json)), on six diverse shots at 0.25, 1.375
and 2.5 GHz: contracting the stored traces reproduces `shape_jacobian` within
9.6e-16 relative for normal harmonics M=19, Cartesian coefficients |p|<=24 and
the full 24x24 Jacobian; paired predictions equal fresh solves bitwise; and
every saved LM loss is rebuilt exactly from the stored predictions.

**Full collection** ([verification.json](verification.json), [verify.py](verify.py)):
all 873 array files are present, match their recorded SHA-256 and come from one
collector version. All **1,114 saved LM-run losses** along the trajectories
(A–G, on each run's own grid, with its stage weights and floor) are rebuilt
**bitwise** from the stored predictions, so every shot is the state that run
actually evaluated. SPD-L's 93 saved losses come from SPD's own solver; they
agree to median 3.8e-14 relative, and the five larger relative differences
are at exactly recovered states whose losses are 1e-24 to 1e-11 (absolute
differences at most 4e-21). Worst forward and reciprocal solve residuals are
5.6e-14.

Resolution indicator: 821 shots agree between 512 and 1024 nodes within 1e-7
at all 19 frequencies. The other 46 are exactly the known difficult states:
the K=192 control's hard-stopped peanut (18 shots), kite (9; worst 2.4e-5) and
C (6), and 13 shots on SC-038's kite path, which its run solved at 768 nodes. Use their
1024-node (or 768/1536) data, and check any basis at two grids. Per-shot
values are in `verification.json` and each shot record.

Cost: 33,744 forward and 33,744 reciprocal solves, 12 single-thread workers,
1 h 48 min (12:18–14:06), 40.6 GB of arrays (not in Git).

## Using it

```python
from experiments.shape_continuation import trajectory_atlas as ta
shot = ta.load('results/validation/shape_continuation/SC-039-trajectory-atlas-data/shots/<key>.npz')
h, orders = ta.cartesian_velocities(shot, 512, band=24)   # or ta.normal_velocities(shot, 512, 19)
J = ta.jacobian(shot, frequency=18, nodes=512, velocities=h)  # (24 pairs, directions)
J_full = ta.jacobian(shot, 18, 512, h, paired=False)          # (24, 24, directions)
```

Compare the 512- and 1024-node Jacobians of a basis to decide which of its
columns are resolved at that state. Normalizing rows by the observed data,
as `lm_backend.normalize` does, needs `ast.catalog_only(case)`.

Reproduce (EMNerf, repository root; the collector resumes shot by shot and
reuses a stored shot only if the same collector version produced it):

```bash
OPENBLAS_NUM_THREADS=1 PYTHONPATH=solvers:. python -m experiments.shape_continuation.trajectory_atlas pilot
OPENBLAS_NUM_THREADS=1 PYTHONPATH=solvers:. python -m experiments.shape_continuation.trajectory_atlas collect --workers 12
```

No atlas, fit, update or score is computed here. The six cases are
development data; this bundle makes no claim about any method.
