#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:.
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q \
  experiments/cleaned_interface/test_interface.py \
  experiments/cleaned_interface/test_audit_streaming.py \
  experiments/exploratory_continuation/test_maintained_adapter.py \
  experiments/fresnel/test_multipole_sources.py \
  experiments/initialization_followup/test_full_matrix.py \
  experiments/stopping_floor/test_continuation.py \
  pytest/sdf_inverse/test_topology_scene_benchmark.py \
  experiments/atlas/test_jacobian_spectrum.py \
  experiments/ibim3d/test_sphere.py \
  experiments/fresnel/test_fresnel2001.py \
  experiments/algoim/test_algoim.py \
  experiments/exploratory_continuation/test_controls.py \
  experiments/halfspace/test_sommerfeld.py \
  pytest/gpr_bem_kress/test_polarization.py \
  pytest/gprmax_ref/test_time_domain_synthesis.py \
  pytest/gpr_bem_kress/test_isolation_and_api.py \
  pytest/gpr_bem_kress/test_muller_forward.py \
  2>&1 | tee results/exploration-followup-20261002/tests.log
