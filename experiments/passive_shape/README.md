# Passive material / radius ambiguity screen

See the [joint assessment](../../results/experiments/outsider_research_20260916/README.md). This tests a constructive counterexample to the idea that passivity alone identifies target size.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=solvers:.
python -m experiments.passive_shape.screen
python -m experiments.passive_shape.qualify
```

The forward calculation is a full Mie series for a 2D TM dielectric circle, with positive Debye parameters and the `exp(-i omega t)` convention. The alternative radius is fixed at 1.25 times the truth; four passive material parameters are fitted over 31 frequencies. Thirty midpoint frequencies are held out.

`qualify` independently checks selected responses against the existing 192-node Müller BEM through its low-level complex-wave API. It does not change or circumvent the high-level production material model: the experimental caller explicitly supplies complex wave numbers and the passive phasor convention. This check qualifies the experimental computation, not production lossy-material support.

The medium is homogeneous here, with no air–soil interface. Relative residual is the Frobenius norm over the full complex data array. A sub-1% residual is not a statistical indistinguishability claim under independent per-sample noise.
