# Seven MF-CC-CSI fits at five frequencies

Updated 2026-11-18T05:29:04+00:00; state: running.

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


Each data.json records the exact shared input path, SHA-256 and coordinator release.
Per-case manifests hash local bulk and committed checkpoints, costs, logs and resources.
Protocol 1 scoring is unchanged. Raw checkpoints use the final 2.5 GHz image.
The output-only numerical copy and upstream numerics are unchanged (patch 0003 reused).
Circle, kite and peanut remain separate eight-frequency results and are untouched.
No BEM code or scoring code was edited. No input table was generated or written.
Failures are kept in each outcome and failure log; no automatic retry.
