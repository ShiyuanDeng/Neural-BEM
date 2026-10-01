# NU-001 validation to run on the CUDA host

Status (2026-10-01): **all code is committed; only the 12 runs and the write-up remain.**
Plan and pre-registered decision rules:
[iteration 08 plan](../../../docs/iterations/cleaned_interfaces/iteration_08/03_plan.md).

## What is run

Six core configurations × two arms, from the prescribed original start, with
the unchanged CI-001 schedule, LM, clips and `nodal_kress` physics:

| Campaign | Arm | Update |
|---|---|---|
| `NU-001-A` | A | `NormalUpdate` — z + P_K[g_a N], exact affine trial and derivative |
| `NU-001-B` | B | `NormalUpdate(tangential=True)` — arm A plus the HLS tangential term |
| `CI-001` (archived, not rerun) | nodal | `ProjectedUpdate` |

Both campaign directories are already prepared and committed (frozen sources,
sealed augmentation copied from CI-001, `arm.json`). They contain no runs.

## Commands

From the repository root, on the RTX 5090 host:

```bash
git pull
conda activate EMNerf            # the CI-001 environment
./results/validation/cleaned_interfaces/NU-001-run.sh
```

The script:

1. runs the 12 cases one at a time (`device=auto`, 4 frequency threads,
   CI-001's settings), shortest first, A then B for each case;
2. writes `NU-001-{A,B}/comparison.{json,csv}` (frozen CI-001 gates);
3. writes `NU-001-drift/drift.json`, which applies the pre-registered rules
   against the archived CI-001 nodal runs and records the verdict under
   `decision`.

Logs go to `results/validation/cleaned_interfaces/NU-001-logs/`. A failed case
prints `FAILED <arm> <case>` to the terminal. Expected wall time is about
20–30 minutes (CI-001 took about 570 s for these six cases).

Keep `PARALLEL=1`, the default. The nodal Kress audit peaks at about 9 GB per
case with either update.

## Before pushing, check

- `NU-001-drift/drift.json` contains `decision` (it is omitted if any of the
  12 runs is missing).
- No `FAILED` line was printed, and every `NU-001-{A,B}/runs/<case>/result.json` exists.
- `verify` refuses a campaign whose frozen sources differ from the committed
  ones. Do not edit `experiments/` or `solvers/` before the run.

Then commit and push `NU-001-A/`, `NU-001-B/`, `NU-001-drift/` and
`NU-001-logs/`. The iteration-09 write-up (verdict, drift table, timing split)
follows from those files.

## Known before the run

On this cloud CPU host, `core__wrong_circle` arm A
([host check](NU-001-cpu-host-check/README.md)) reached the same endpoint as
nodal (RMS 7.58e-6 mm, residuals 5e-14), but its final audit failed the
per-column Jacobian gate. The failing columns (a37, b37, b36) have norms about
1e-14 of the largest column, so their production/refined relative error (4%)
is roundoff. The absolute error is 1.4e-15 of the largest column, as in the
nodal arm. The pre-registered rules count this as a mismatch. A post-hoc audit
with an absolute column floor will be reported separately and labelled as
such. The GPU run is expected to reproduce this case.

## Deviation from the plan's execution section

The plan specified this cloud CPU host. The runs move to the CUDA host because
it is about 17× faster; decisions are host-independent (see the host check).
The raised time caps (14400 s fit, 3600 s audit) stay in `ArmPolicy` and are
not binding on the GPU. Decision rules are unchanged.
