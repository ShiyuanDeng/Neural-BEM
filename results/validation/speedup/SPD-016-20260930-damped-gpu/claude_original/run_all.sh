#!/bin/bash
cd /home/drdeng/Neural_SDF_BEM_AD
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. MPLCONFIGDIR=/tmp/claude-1001/mpl SC_FREQUENCY_THREADS=4
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
S=/tmp/claude-1001/-home-drdeng-Neural-SDF-BEM-AD/f576359c-aee4-4e71-b4e0-25acd8cc8a37/scratchpad/spd_probe
for spec in "accelerated 0.5 shifted_star" "baseline 0.5 shifted_star" "accelerated 13.3 new_asymmetric" "baseline 13.3 new_asymmetric"; do
  set -- $spec
  $PY -u $S/replay_d.py $1 $2 $3 $S/runs > $S/runs/$1_$2_$3.log 2>&1
  grep SUMMARY $S/runs/$1_$2_$3.log
done
echo ALLDONE
