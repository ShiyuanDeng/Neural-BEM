| State | K | M | Rank CPU / CUDA | Relative error | Curve difference (mm) | CPU s | CUDA s | Speedup | CUDA first use s | Passed |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| stage_1_damped | 8 | 3 | 33 / 33 | 3.7e-13 | 4.2e-14 | 0.0004 | 0.0018 | 0.2 | 0.279 | yes |
| release_M11 | 192 | 11 | 769 / 769 | 5.9e-11 | 5.0e-12 | 0.3079 | 0.0296 | 10.4 | 0.039 | yes |
| fixed_M67 | 192 | 67 | 769 / 769 | 4.8e-11 | 1.7e-12 | 0.3402 | 0.0346 | 9.8 | 0.035 | yes |

Median parts of a warmed preparation (s):

| State | Device | Sampling | Transfer | Dense rows and products | Solve |
|---|---|---:|---:|---:|---:|
| stage_1_damped | cpu | 0.0002 | 0.0000 | 0.0002 | 0.0001 |
| stage_1_damped | cuda | 0.0002 | 0.0001 | 0.0004 | 0.0011 |
| release_M11 | cpu | 0.0015 | 0.0000 | 0.2480 | 0.0581 |
| release_M11 | cuda | 0.0016 | 0.0002 | 0.0109 | 0.0169 |
| fixed_M67 | cpu | 0.0048 | 0.0000 | 0.2621 | 0.0733 |
| fixed_M67 | cuda | 0.0046 | 0.0007 | 0.0118 | 0.0174 |

CPU against CUDA, one bounded step (requested normal push peaking at 0.1 mm):

| State | Max normal move diff (m) | RMS normal move diff (m) | Speed-change spread diff | Speed ratio diff |
|---|---:|---:|---:|---:|
| stage_1_damped | 1.6e-17 | 4.6e-18 | 8.1e-18 | 0.0e+00 |
| release_M11 | 4.5e-16 | 1.8e-16 | 5.4e-15 | 2.2e-15 |
| fixed_M67 | 1.0e-16 | 1.1e-17 | 1.6e-17 | 2.4e-15 |
