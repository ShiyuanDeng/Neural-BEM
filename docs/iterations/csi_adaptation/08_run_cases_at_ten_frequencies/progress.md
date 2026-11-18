# MF-CC-CSI fits at ten frequencies: live table

Updated 2026-11-18T20:21:46+00:00; state: running.

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

| kite | 256 | 12.059 | 32.058 / 41.282 | 3.4494 | 1.0262 | 1228.27 |
| kite | 512 | 11.244 | 22.938 / 39.719 | 3.6141 | 0.7304 | 2449.02 |
| kite | 1024 | 13.560 | 16.202 / 40.532 | 3.7450 | 0.5888 | 4895.17 |
| kite | 2048 | 13.760 | 12.764 / 39.558 | 3.8104 | 0.5785 | 9793.27 |

kite: completed, 2026-11-18T16:59:07+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/kite/outcome.json).

| asymmetric | 256 | 6.855 | 28.158 / 31.468 | 3.4829 | 0.1406 | 1231.55 |
| asymmetric | 512 | 7.860 | 19.054 / 33.927 | 3.6591 | 0.1937 | 2458.99 |
| asymmetric | 1024 | 8.303 | 14.003 / 31.821 | 3.7606 | 0.2021 | 4919.93 |
| asymmetric | 2048 | 7.240 | 11.423 / 26.734 | 3.8080 | 0.2011 | 9882.28 |

asymmetric: completed, 2026-11-18T17:29:42+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/asymmetric/outcome.json).

| cross | 256 | 9.762 | 27.621 / 33.610 | 3.4929 | 0.1704 | 1229.93 |
| cross | 512 | 11.394 | 17.116 / 39.704 | 3.6967 | 0.1695 | 2452.16 |
| cross | 1024 | 14.018 | 12.622 / 42.305 | 3.8088 | 0.1229 | 4905.95 |
| cross | 2048 | 11.725 | 12.176 / 38.966 | 3.8256 | 0.0515 | 9860.16 |

cross: completed, 2026-11-18T17:34:16+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/cross/outcome.json).

| cog | 256 | 16.955 | 32.186 / 25.931 | 3.4266 | 0.1989 | 1034.13 |
| cog | 512 | 16.435 | 24.665 / 24.269 | 3.5643 | 0.0754 | 2057.53 |
| cog | 1024 | 15.848 | 20.637 / 21.161 | 3.6472 | 0.0198 | 4117.82 |
| cog | 2048 | 14.859 | 18.080 / 18.239 | 3.7021 | 0.0129 | 8232.22 |

cog: completed, 2026-11-18T19:16:39+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/cog/outcome.json).

| c_shape | 256 | 7.939 | 27.912 / 41.291 | 3.4797 | 1.6963 | 1244.96 |
| c_shape | 512 | 14.817 | 17.071 / 45.939 | 3.6995 | 1.2149 | 2485.44 |
| c_shape | 1024 | 17.295 | 11.747 / 46.903 | 3.8256 | 0.8513 | 4970.04 |
| c_shape | 2048 | 15.939 | 10.316 / 44.803 | 3.8587 | 0.6404 | 9932.68 |

c_shape: completed, 2026-11-18T20:15:35+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/c_shape/outcome.json).

| peanut | 256 | 8.155 | 24.728 / 39.683 | 3.5465 | 0.1860 | 1266.71 |
| peanut | 512 | 10.327 | 17.091 / 39.099 | 3.7020 | 0.1362 | 2526.74 |
| peanut | 1024 | 8.002 | 14.148 / 31.802 | 3.7632 | 0.0771 | 5047.87 |
| peanut | 2048 | 5.472 | 12.151 / 24.543 | 3.7961 | 0.0461 | 10030.27 |

peanut: completed, 2026-11-18T20:21:45+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_ten_frequency/peanut/outcome.json).


Each data.json records the exact shared input path, SHA-256 and coordinator release.
Per-case manifests hash local bulk and committed checkpoints, costs, logs and resources.
Protocol 1 scoring is unchanged. Raw checkpoints use the final 2.5 GHz image.
The output-only numerical copy and upstream numerics are unchanged (patch 0003 reused).
The five-frequency and eight-frequency results are separate and untouched.
No BEM code or scoring code was edited. No input table was generated or written.
Failures are kept in each outcome and failure log; no automatic retry.
