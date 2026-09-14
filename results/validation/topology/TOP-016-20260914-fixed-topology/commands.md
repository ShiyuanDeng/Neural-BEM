# Recorded commands

Initial checkout `/home/drdeng/Neural_SDF_BEM_AD`, clean branch `feature/ordered-boundary-nystrom`:

```bash
git pull --ff-only
git worktree add -b track/topology-TOP-016 /home/drdeng/Neural-BEM-TOP-016 HEAD
```

The pull fast-forwarded `9acae6b` to `d3bbdae`, adding only `neural_bem_TOP016_handoff.zip`. The archive was inspected and extracted to `/tmp/neural-bem-TOP016-89b938ig`; its three new `docs/` paths were checked for collisions and copied into the experiment worktree. START_HERE.md was read as the user-adopted handoff and not installed as another repository document.

Numerical execution and tests use `/home/drdeng/miniconda3/envs/EMNerf/bin/python`, with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`, from the experiment worktree:

```bash
python -m pytest -q pytest/sdf_inverse/test_top016_preflight.py
python -u run_top016_preflight.py --output results/validation/topology/TOP-016-20260914-fixed-topology/phase0
python -m pytest -q pytest/sdf_inverse/test_top016_preflight.py pytest/sdf_inverse/test_top016_screen.py
python -u run_top016_screen.py --phase0 results/validation/topology/TOP-016-20260914-fixed-topology/phase0 --output results/validation/topology/TOP-016-20260914-fixed-topology/phase1
```

The first eight tests passed before Phase 0; twelve tests passed before the information screen. Both test sets use zero physical solves. Per-stage manifests record source hashes and actual argument vectors. The Phase-0 source snapshot is saved at `phase0/driver.py`; numerical sources were not modified during either worker.

Main trials then ran at concurrency two, single-thread BLAS, each through:

```bash
python -u run_top016_pilot.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology --scene <far-two-stars|central-ellipse-star|merge> --arm <S|F>
```

The session environment changed after the main terminal artifacts were saved. The parent-orchestrator file was missing; `main_execution.json` was rebuilt from all six finished metrics with unavailable exit codes null. No main trial was repeated. A requested worktree move was cancelled before execution; the worktree remains in its original location. Full filesystem access was restored before remaining work.

Neither principal main endpoint qualified, so the two approved local controls ran at concurrency two:

```bash
python -u run_top016_pilot.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology --scene far-two-stars --arm S --local
python -u run_top016_pilot.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology --scene far-two-stars --arm F --local
python summarize_top016.py --bundle results/validation/topology/TOP-016-20260914-fixed-topology
```

The local-control exit codes are retained in `local_execution.json`. The summary rebuild reads saved JSON only and performs no forward solve.

Final focused validation (31 passed; zero physical solves):

```bash
python -m pytest -q pytest/sdf_inverse/test_top016_preflight.py pytest/sdf_inverse/test_top016_screen.py pytest/sdf_inverse/test_top016_optimizer_hooks.py pytest/sdf_inverse/test_top016_pilot.py pytest/sdf_inverse/test_feasible_finite_differences.py
git diff --check
```

Final read-only checks verified every trial's numerical-source hashes, original state and observation hashes, v1/v2 specification hashes, current document links, and stage/wall caps. Work is committed on `track/topology-TOP-016`; no push or merge is authorized by this handoff.
