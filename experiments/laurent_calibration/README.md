# Calibration-quotient Laurent feasibility experiment

Standalone research code for the information-geometry experiment authorized on
2026-09-16. No production solver or previous iteration contract is changed.

The experiment asks whether calibration-aware acquisition design makes Laurent
shape harmonics easier to estimate than generic multioffset acquisition. Every
non-oracle arm uses the same full nonlinear joint shape/material/Tx/Rx-gain
inverse. Acquisition count, per-antenna usage, graph cycle dimension, and binned
physical offsets are matched. A design assuming known calibration is another
control, while supplying true gains gives an oracle reference.

The implementation reuses `modal_muller_research`'s compiled scattering maps and
reciprocal shape derivatives. Numerical data come from a separate, refined full
boundary solve. The scope is one 2-D lossless object in a homogeneous background
with a surface-style acquisition; realistic layered GPR and antenna models are
outside this initial test.

Run from the repository root:

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest -q experiments/laurent_calibration/test_calibration.py
/home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_calibration.run --stage all
MPLCONFIGDIR=/tmp/laurent-calibration-mpl /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.laurent_calibration.analyze
```

Read the [measured report](../../results/experiments/laurent_calibration_20260916/report.md)
and [raw summary](../../results/experiments/laurent_calibration_20260916/summary.json).

Files:

- `model.py`: Laurent chart, matched forward/Jacobian, independent oracle, gain model, joint inverse.
- `design.py`: nuisance projections and constrained acquisition design.
- `run.py`: numerical qualification, design, independent data, paired recovery experiments.
- `analyze.py`: fresh recovered-state validation, paired statistics, plots, and report.
- `test_calibration.py`: six mathematical/numerical correctness checks.
