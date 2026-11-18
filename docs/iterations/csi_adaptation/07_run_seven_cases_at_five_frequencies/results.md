# Seven MF-CC-CSI fits at five frequencies

Updated 2026-11-18T06:51:22+00:00; state: running.

Frequencies: 0.5, 1, 1.5, 2, 2.5 GHz. Seven shapes at permittivity 4.
2048 iterations; 166 by 166 cells at 1.25 mm; native back-propagation; eight threads.
One centred start. Times are shared-machine measurements, with no time stop.
Half the signed peak is the main score; 0.3 and 0.7 give sensitivity.

| Shape | Iterations | Area error % (0.5) | Area error % (0.3 / 0.7) | Mean permittivity | Centre error mm | Native s |
|---|---:|---:|---:|---:|---:|---:|
| star | 256 | 8.736 | 35.970 / 40.651 | 3.3567 | 0.4383 | 552.14 |
| star | 512 | 5.682 | 27.967 / 31.685 | 3.5000 | 0.0451 | 1122.95 |
| star | 1024 | 4.022 | 22.252 / 21.651 | 3.6006 | 0.1315 | 2265.96 |
| star | 2048 | 3.716 | 16.049 / 19.271 | 3.7121 | 0.1164 | 4746.28 |

star: completed, 2026-11-18T05:22:22+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_five_frequency/star/outcome.json).

| asymmetric | 256 | 7.273 | 30.813 / 32.510 | 3.4435 | 0.2885 | 596.80 |
| asymmetric | 512 | 7.872 | 21.573 / 33.889 | 3.6171 | 0.3604 | 1220.18 |
| asymmetric | 1024 | 7.821 | 16.352 / 31.261 | 3.7200 | 0.3487 | 2464.69 |
| asymmetric | 2048 | 6.673 | 13.224 / 26.235 | 3.7760 | 0.2969 | 5023.79 |

asymmetric: completed, 2026-11-18T05:29:03+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_five_frequency/asymmetric/outcome.json).

| c_shape | 256 | 9.526 | 27.722 / 40.995 | 3.4829 | 1.7841 | 628.65 |
| c_shape | 512 | 14.380 | 17.649 / 45.315 | 3.6884 | 1.2813 | 1251.82 |
| c_shape | 1024 | 17.109 | 12.403 / 46.686 | 3.8115 | 0.8901 | 2497.85 |
| c_shape | 2048 | 16.034 | 10.908 / 45.107 | 3.8484 | 0.6773 | 5050.57 |

c_shape: completed, 2026-11-18T05:35:31+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_five_frequency/c_shape/outcome.json).

| hook | 256 | 8.046 | 36.040 / 37.626 | 3.3420 | 1.5693 | 645.44 |
| hook | 512 | 10.540 | 21.748 / 43.783 | 3.5953 | 1.2843 | 1261.67 |
| hook | 1024 | 15.295 | 13.473 / 45.632 | 3.7728 | 0.9916 | 2494.19 |
| hook | 2048 | 16.516 | 9.623 / 44.651 | 3.8657 | 0.7073 | 4957.90 |

hook: completed, 2026-11-18T06:46:17+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_five_frequency/hook/outcome.json).

| cross | 256 | 11.969 | 26.343 / 34.110 | 3.5008 | 0.2921 | 630.86 |
| cross | 512 | 13.170 | 16.203 / 41.060 | 3.7096 | 0.2643 | 1245.99 |
| cross | 1024 | 14.865 | 12.699 / 43.635 | 3.8144 | 0.1988 | 2471.63 |
| cross | 2048 | 11.970 | 12.550 / 39.278 | 3.8255 | 0.1123 | 4923.65 |

cross: completed, 2026-11-18T06:51:22+00:00. [Evidence](../../../../results/csi/tg002/2026-11-18_five_frequency/cross/outcome.json).


Each data.json records the exact shared input path, SHA-256 and coordinator release.
Per-case manifests hash local bulk and committed checkpoints, costs, logs and resources.
Protocol 1 scoring is unchanged. Raw checkpoints use the final 2.5 GHz image.
The output-only numerical copy and upstream numerics are unchanged (patch 0003 reused).
Circle, kite and peanut remain separate eight-frequency results and are untouched.
No BEM code or scoring code was edited. No input table was generated or written.
Failures are kept in each outcome and failure log; no automatic retry.
