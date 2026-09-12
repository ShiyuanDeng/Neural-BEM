# Independent TOP-009 evidence audit

Codex reviewed experiment tip `ab10e40` on 2026-09-12. The
[review and proposed next diagnostic](../../../../docs/iterations/topology/iteration_07/02_proposals/01_independent_review.md)
give the interpretation and the promotion-counter fix.

[Evidence audit](evidence_audit.json) reads saved JSON and records input/source
hashes; it runs no solver or reconstruction. It finds 13 loss-change stops and
one iteration-limit stop across the 14 retained rungs, and a final relative
training error of 8.7878e-5 despite 11.849 mm boundary error. Those records do
not certify a local minimum or unique recovery.

Reproduce into a fresh file from the repository root:

```bash
python results/validation/topology/TOP-009-20260912-review/audit_saved_evidence.py \
  --output /tmp/top009-evidence-audit.json
```

The output refuses overwrite. Current source hashes may differ after subsequent
changes; the saved experiment inputs should retain their recorded hashes.

The promotion-counter repair passed 108 focused tests with
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
PYTHONPATH=solvers`, using `/home/drdeng/miniconda3/envs/EMNerf/bin/python -m
pytest -q` on these files under `pytest/sdf_inverse/`:

- `test_bandwidth_promotion.py`
- `test_feasible_finite_differences.py`
- `test_refined_feasibility_guard.py`
- `test_topology_controller.py`
- `test_topology_allocation.py`
- `test_selective_topology_refinement.py`
- `test_topology_scene_benchmark.py`
- `test_cartesian_fourier_topology.py`
- `test_radial_topology.py`
