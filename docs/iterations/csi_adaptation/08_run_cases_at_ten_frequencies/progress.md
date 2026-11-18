# MF-CC-CSI fits at ten frequencies: live table

Updated 2026-11-18T14:49:36+00:00; state: running.

Frequencies: 0.25 to 2.5 GHz in 0.25 GHz steps. Ten shapes at permittivity 4.
2048 iterations; 166 by 166 cells at 1.25 mm; native back-propagation; eight threads.
One centred start. Times are shared-machine measurements, with no time stop.
Half the signed peak is the main score; 0.3 and 0.7 give sensitivity.

| Shape | Iterations | Area error % (0.5) | Area error % (0.3 / 0.7) | Mean permittivity | Centre error mm | Native s |
|---|---:|---:|---:|---:|---:|---:|
| star | 256 | 8.893 | 33.778 / 29.496 | 3.3942 | 0.0248 | 1219.99 |
| star | 512 | 5.757 | 24.248 / 28.415 | 3.5695 | 0.1330 | 2484.54 |
| star | 1024 | 6.624 | 16.223 / 31.350 | 3.7253 | 0.1252 | 5015.13 |
| star | 2048 | 6.600 | 12.324 / 28.386 | 3.7970 | 0.0944 | 10019.82 |

star: completed, 2026-11-18T14:44:40+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/star/outcome.json).

| hook | 256 | 7.399 | 34.962 / 36.658 | 3.3545 | 1.5475 | 1022.39 |
| hook | 512 | 9.642 | 21.097 / 41.826 | 3.6064 | 1.2258 | 2040.71 |
| hook | 1024 | 14.454 | 12.920 / 43.685 | 3.7830 | 0.9340 | 4075.35 |
| hook | 2048 | 16.219 | 8.958 / 43.560 | 3.8793 | 0.6924 | 8133.55 |

hook: completed, 2026-11-18T14:15:34+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/hook/outcome.json).

| circle | 256 | 6.605 | 30.954 / 18.347 | 3.4329 | 0.0548 | 1273.10 |
| circle | 512 | 1.485 | 21.957 / 19.334 | 3.6028 | 0.0605 | 2535.65 |
| circle | 1024 | 2.018 | 15.068 / 19.648 | 3.7373 | 0.0774 | 5062.33 |
| circle | 2048 | 3.458 | 10.668 / 18.467 | 3.8232 | 0.0553 | 10043.41 |

circle: completed, 2026-11-18T14:49:36+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/circle/outcome.json).


Each data.json records the exact shared input path, SHA-256 and coordinator release.
Per-case manifests hash local bulk and committed checkpoints, costs, logs and resources.
Protocol 1 scoring is unchanged. Raw checkpoints use the final 2.5 GHz image.
The output-only numerical copy and upstream numerics are unchanged (patch 0003 reused).
The five-frequency and eight-frequency results are separate and untouched.
No BEM code or scoring code was edited. No input table was generated or written.
Failures are kept in each outcome and failure log; no automatic retry.
