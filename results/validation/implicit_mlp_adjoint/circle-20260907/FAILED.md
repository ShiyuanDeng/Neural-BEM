# Incomplete early circle run

This 2026-09-07 attempt used `run_implicit_mlp_inverse.py --max-iterations 20
--num-pairs 8 --num-nodes 64 --no-gate --output-dir
results/validation/implicit_mlp_adjoint/circle-20260907`.

The optimizer performed 20 accepted updates and wrote `kress_model.pt`, then
report generation raised `NameError: name 'overwrite' is not defined` in
`_write_neural_checkpoint`: an overwrite-cleanup block had been misplaced there.
Metrics and a complete report were not written. This is a partial execution,
not a completed benchmark or a recovery pass.

The driver bug was repaired and its overwrite/checkpoint regressions passed.
The subsequent [60-update-budget circle run](../circle-verified-20260907/summary.md)
completed all artifacts and retains its failed recovery gates.
