# Relaxed-BIE experiments

RB-001 continues the four FM-002 real-prefix failures under unchanged accuracy
and recovery gates. The research contract and current status are in
[`docs/iterations/relaxed_bie/`](../../docs/iterations/relaxed_bie/README.md).
Numerical optimization and resume belong to `solvers/bem_inverse/`; this
package owns archived input selection, evidence gates and truth scoring.

The [completed RB-001 bundle](../../results/validation/relaxed_bie/RB-001/README.md)
reproduces all four stops and removes each immediate obstruction by both fixed
diagnostics. All continued endpoints pass the finer audit; full and paired
recovery remain 0/4 within the retained quotas/time. The ordinary damped
default remains unchanged. Qualification passed 506 tests.

Use the EMNerf environment, `PYTHONPATH=solvers:.`, and one BLAS/OpenMP thread:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
RB_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
"$RB_PY" -m experiments.relaxed_bie.rb001 stage-a
"$RB_PY" -m experiments.relaxed_bie.continuation qualify
"$RB_PY" -m experiments.relaxed_bie.continuation continue
"$RB_PY" -m experiments.relaxed_bie.report
"$RB_PY" -m experiments.relaxed_bie.report --verify
```

Stage A independently replays the archived and current optimizer, verifies
trajectory/field agreement, and tests the original proposal at N1024/2048 and
remaining half steps at N512/1024. A separate phase seal records the completed
resolution/resume implementation before qualification and continuation. These
commands refuse previous or incomplete output directories; preserve failures
instead of rerunning over them. FM-002 archives and all observations remain
unchanged.

The continuation checkpoint restores the last accepted linearization, next
LM damping, iteration, refined cache, global work/time, stage quota and policy
queue. Rejected-proposal fields from Stage A are diagnostic overhead, not free
continuation solves. Future frontier decisions are recomputed; decisions
already made before the checkpoint remain part of the resumed policy state.

Resolution promotion is opt-in. Once promoted, ordinary fitting and its next
stages retain N1024/2048 with one frequency worker. Both the original and
promoted endpoint audits are recorded. No truth error steers a trial, a band
release, or the returned endpoint.

Resolved numerical pairs are recorded in each stage row and promotion event;
the original operation descriptions remain the baseline policy plan. Phase
archives retain their sealed implementation/plan bytes; current execution
status is in the track handoff and iteration-02 closeout. Final verification
refuses changed sealed artifacts instead of replacing their hashes.
