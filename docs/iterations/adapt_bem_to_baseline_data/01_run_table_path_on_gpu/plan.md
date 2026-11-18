# Run the table path on the GPU

Date: 18 November 2026. Owner: `bem-gpu`. Solver lock held from launch.
The coordinator assigned this activity; solver edits wait for its explicit go.
Neither coordination file is edited here.

Coordinator review: GO on 18 November. All three clean pre-edit references
must finish first. Also approved: wording-only removal of "CPU" from the
three masked-table refusal messages in `forward_solvers/nodal_kress.py` and
`continuation/forward.py`. No other solver edit is allowed without a new
proposal. The complete diff must be reviewed before the solver commit.

## Question and scope

Can the existing plane-wave and unpaired point-source tables use CUDA A1
geometry and A2 assembly, with both full and masked measurements, while
preserving CPU table results and the paired TG-002 default fit?

Code inspection finds one execution guard in
`ModalMuller._table_acquisition`. Both `ModalGeometry` and
`DeviceModalGeometry` already supply the host `normal`, `WaveArrays` and
normal multipliers needed by A3. A4 factorization/fields and B7 derivatives
already run on the CPU after either assembly path. No new CUDA mathematics,
dataset branch, fitted constant, schedule or physics convention is proposed.

## Proposed edit, subject to coordinator review

- In `solvers/bem_inverse/forward_solvers/modal_muller.py`, remove only the
  table-mode requirement for `Execution(device='cpu')`, and remove the stale
  CPU-only field comment. Keep explicit table opt-in, supported acquisition
  checks, paired dispatch, device selection and OOM rules unchanged.
- Update `solvers/bem_inverse/README.md` and the explicit-table section of
  `docs/reference/inverse_information_chain.md` to describe CPU/CUDA/auto
  selection and the existing split between device A1–A2 and host A3/A4/B7.
- Replace the obsolete CPU-only refusal assertion in
  `pytest/bem_inverse/test_table_forward.py`. Add focused CPU/CUDA table
  agreement checks under `pytest/bem_inverse/`, including auto dispatch.

This is general acquisition support. The paired default exits the acquisition
check before the removed guard. The solver must contain no BRG or CSI names
or dataset-specific constants. Any additional solver edit requires a revised
proposal and the coordinator's go before writing it.

## Pre-edit references and settings

Copy `experiments/baselines/brg/check_default_regression.py` and
`compare_default_regression.py` into
`experiments/bem_on_baseline_data/gpu_table_path/`; never execute the originals.
Adapt only output paths, run labels/device selection, resource receipts and
the comparison needed to measure GPU repeatability. Preserve their stable
CPU record comparison and byte comparison of arrays.

Run one CPU reference and two independent GPU references before editing the
solver. Use only TG-002 `circle__c0.5`, `bem/default_clean_uc_fc`, one centred
65 mm start, modal Müller, slider, real data, recovered contrast, localization
none, no warm-up. Keep the copied reference's four frequency threads, with
BLAS/OMP limited to one thread each. Run fits sequentially, never in parallel.
CPU pins CUDA visibility off; GPU explicitly requests CUDA. Keep the native
120 s fit limit and 13,412 work-unit ceiling; no tuning or search.

The GPU baseline comparison records maximum absolute and relative differences
for every saved numeric array, contrast and residuals, plus stable decisions,
stage outcomes and work. The post-edit GPU differences from the first baseline
must not exceed the differences between the two pre-edit baselines. If that
envelope is zero, require exact equality. Report any changed outcome or
decision separately; do not widen limits after seeing the post-edit fit.

## Proofs after the go

1. Table checks: a translated, mildly noncircular Fourier curve, three
   illuminations and seven receivers; plane waves and unpaired point sources;
   full and irregular masked tables. Check identical shapes and C-order mask
   selection. Require CUDA diagnostics, no CPU fallback, and CPU/CUDA relative
   L2 difference below 1e-10 for predictions and B7 shape derivatives.
   Use the same prepared slider directions to isolate the forward backend.
   Also compare recovered-material finite-difference columns between devices.
   Existing complete-slider finite-difference tests remain in the suite.
2. Run one post-edit CPU default fit and compare all saved arrays byte for
   byte and all stable records using the copied BRG comparison logic.
3. Run one post-edit GPU default fit and apply the measured pre-edit envelope.
4. Run the existing `pytest/bem_inverse` suite with CUDA visible; retain the
   pre-edit CPU suite receipt produced by the copied reference. Failures and
   skips are recorded, not hidden. No unrelated broader suite is planned.

If CPU/GPU tables disagree, stop and inspect before any further solver change.
If the default result changes beyond its required comparison, stop and report
to the coordinator. It owns escalation to the user.

## Run budget and resources

Five default fits total: CPU before/after, GPU before twice/after once.
One pre-edit CPU suite, one post-edit CUDA-visible suite, plus the focused
table checks. Limit all checks to one hour total; each process has a one-hour
outer ceiling, with the fit's smaller 120 s limit retained. No baseline-data
inverse fits belong to this activity.

Before starting, inspect available memory and reserve estimated peak usage
so at least 16 GiB remains. Initially budget 4 GiB for one small reference
process; replace that estimate with measured first-run peak plus margin.
Record idle CPU capacity, host peak RSS and GPU memory. A process-group guard
stops only this activity's child group if available host memory falls below
14 GiB. Record commit hash, solver dirty status at start/end, command,
timestamps, return code and resource peak for every run. Fits launched while
the solver is dirty are checks only and are not reported comparison results.

## Commands and evidence locations

Python: `/home/drdeng/miniconda3/envs/EMNerf/bin/python`, from repository root.
All commands use `PYTHONPATH=solvers:.`, `OMP_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`.

Planned copied-driver interface:

```text
python experiments/bem_on_baseline_data/gpu_table_path/check_default_regression.py cpu_before --device cpu --suite
python experiments/bem_on_baseline_data/gpu_table_path/check_default_regression.py gpu_before_1 --device cuda
python experiments/bem_on_baseline_data/gpu_table_path/check_default_regression.py gpu_before_2 --device cuda
python experiments/bem_on_baseline_data/gpu_table_path/compare_default_regression.py gpu-repeatability
python -m pytest pytest/bem_inverse/test_table_gpu.py -q
python experiments/bem_on_baseline_data/gpu_table_path/check_default_regression.py cpu_after --device cpu
python experiments/bem_on_baseline_data/gpu_table_path/check_default_regression.py gpu_after --device cuda
python experiments/bem_on_baseline_data/gpu_table_path/compare_default_regression.py after
python -m pytest pytest/bem_inverse -q
```

Use the guarded wrapper for actual execution. Raw evidence goes under
`results/bem/baseline_data/gpu_table_path/2026-11-18/`, with one immutable
directory per run purpose. Preserve bulky arrays/logs locally with SHA-256
manifests; tracked evidence stays below about 5 MB per run. No report figure
is needed unless a failure needs one; figures would go in this activity's
`figures/` directory. Record findings and failures in `results.md`.

Wrapper: `python experiments/bem_on_baseline_data/gpu_table_path/guarded_run.py
<run_label> -- <command_above>`. It writes command, resources, provenance and
the captured log inside that run directory. For table checks, set
`BEM_GPU_TABLE_EVIDENCE` to the run directory to retain per-case errors.

## Review and handover

Before any solver edit, stop in the pane with the exact proposal and wait
for the coordinator's go. Pre-edit references may run while waiting. Announce
when solver files become dirty. Keep the edit window short for the other
agents' CPU fits. Show the complete diff after checks and before the solver
commit; wait for the coordinator's review. Commit and push only owned paths,
preserving all shared changes and failed evidence. Announce the committed
solver state, finish `results.md`, use the required report block, then release
the solver lock. No branches, worktrees or coordination-file edits.
