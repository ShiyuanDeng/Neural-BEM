# TOP-001 candidate-refinement allocation

60 / 60 comparison replays complete. See `suite_metrics.json` for every paired comparison.

A: best one × 3 LM steps. B: best two × 3. C: best two × 1. Candidate cap 48 in both charts.

| Chart | Arm | Magnitude | Seed | Train L2 | Holdout L2 | Hausdorff (µm) | BIE frequency solves |
|---|---|---:|---:|---:|---:|---:|---:|
| cartesian | [A](comparison/cartesian/A/m0-s0/metrics.json) | 0 | None | 6.8734e-06 | 0.0096843 | 175.211 | 1109 |
| cartesian | [A](comparison/cartesian/A/m0.0001-s11/metrics.json) | 0.0001 | 11 | 6.8734e-06 | 0.0096843 | 175.211 | 1109 |
| cartesian | [A](comparison/cartesian/A/m0.0001-s29/metrics.json) | 0.0001 | 29 | 6.8734e-06 | 0.0096843 | 175.211 | 1109 |
| cartesian | [A](comparison/cartesian/A/m0.0001-s47/metrics.json) | 0.0001 | 47 | 6.8734e-06 | 0.0096843 | 175.211 | 1109 |
| cartesian | [A](comparison/cartesian/A/m0.001-s11/metrics.json) | 0.001 | 11 | 6.8734e-06 | 0.0096843 | 175.211 | 1018 |
| cartesian | [A](comparison/cartesian/A/m0.001-s29/metrics.json) | 0.001 | 29 | 7.1628e-07 | 3.1779e-06 | 0.0256124 | 277 |
| cartesian | [A](comparison/cartesian/A/m0.001-s47/metrics.json) | 0.001 | 47 | 6.9296e-07 | 2.7762e-06 | 0.0241955 | 277 |
| cartesian | [A](comparison/cartesian/A/m0.01-s11/metrics.json) | 0.01 | 11 | 7.4417e-07 | 3.2729e-06 | 0.0308031 | 184 |
| cartesian | [A](comparison/cartesian/A/m0.01-s29/metrics.json) | 0.01 | 29 | 6.5426e-07 | 2.8979e-06 | 0.0248769 | 194 |
| cartesian | [A](comparison/cartesian/A/m0.01-s47/metrics.json) | 0.01 | 47 | 6.2418e-07 | 2.5053e-06 | 0.021589 | 181 |
| cartesian | [B](comparison/cartesian/B/m0-s0/metrics.json) | 0 | None | 7.1256e-06 | 0.011021 | 175.453 | 1538 |
| cartesian | [B](comparison/cartesian/B/m0.0001-s11/metrics.json) | 0.0001 | 11 | 7.1256e-06 | 0.011021 | 175.453 | 1538 |
| cartesian | [B](comparison/cartesian/B/m0.0001-s29/metrics.json) | 0.0001 | 29 | 7.1256e-06 | 0.011021 | 175.453 | 1538 |
| cartesian | [B](comparison/cartesian/B/m0.0001-s47/metrics.json) | 0.0001 | 47 | 7.1256e-06 | 0.011021 | 175.453 | 1538 |
| cartesian | [B](comparison/cartesian/B/m0.001-s11/metrics.json) | 0.001 | 11 | 7.1256e-06 | 0.011021 | 175.453 | 1386 |
| cartesian | [B](comparison/cartesian/B/m0.001-s29/metrics.json) | 0.001 | 29 | 7.1628e-07 | 3.1779e-06 | 0.0256124 | 482 |
| cartesian | [B](comparison/cartesian/B/m0.001-s47/metrics.json) | 0.001 | 47 | 6.9296e-07 | 2.7762e-06 | 0.0241955 | 482 |
| cartesian | [B](comparison/cartesian/B/m0.01-s11/metrics.json) | 0.01 | 11 | 7.4417e-07 | 2.9738e-06 | 0.0308031 | 236 |
| cartesian | [B](comparison/cartesian/B/m0.01-s29/metrics.json) | 0.01 | 29 | 6.5426e-07 | 2.8979e-06 | 0.0248769 | 570 |
| cartesian | [B](comparison/cartesian/B/m0.01-s47/metrics.json) | 0.01 | 47 | 6.2418e-07 | 2.5053e-06 | 0.021589 | 325 |
| cartesian | [C](comparison/cartesian/C/m0-s0/metrics.json) | 0 | None | 4.7049e-06 | 0.0083401 | 126.339 | 1238 |
| cartesian | [C](comparison/cartesian/C/m0.0001-s11/metrics.json) | 0.0001 | 11 | 4.7049e-06 | 0.0083401 | 126.339 | 1238 |
| cartesian | [C](comparison/cartesian/C/m0.0001-s29/metrics.json) | 0.0001 | 29 | 4.7049e-06 | 0.0083401 | 126.339 | 1238 |
| cartesian | [C](comparison/cartesian/C/m0.0001-s47/metrics.json) | 0.0001 | 47 | 4.7049e-06 | 0.0083401 | 126.339 | 1238 |
| cartesian | [C](comparison/cartesian/C/m0.001-s11/metrics.json) | 0.001 | 11 | 4.7049e-06 | 0.0083401 | 126.339 | 1148 |
| cartesian | [C](comparison/cartesian/C/m0.001-s29/metrics.json) | 0.001 | 29 | 6.6415e-07 | 2.4125e-06 | 0.0247719 | 294 |
| cartesian | [C](comparison/cartesian/C/m0.001-s47/metrics.json) | 0.001 | 47 | 6.4382e-07 | 2.3353e-06 | 0.023522 | 294 |
| cartesian | [C](comparison/cartesian/C/m0.01-s11/metrics.json) | 0.01 | 11 | 6.8683e-07 | 2.6978e-06 | 0.0295544 | 168 |
| cartesian | [C](comparison/cartesian/C/m0.01-s29/metrics.json) | 0.01 | 29 | 6.0954e-07 | 2.3744e-06 | 0.0239973 | 332 |
| cartesian | [C](comparison/cartesian/C/m0.01-s47/metrics.json) | 0.01 | 47 | 5.8467e-07 | 2.1127e-06 | 0.0211747 | 220 |
| radial | [A](comparison/radial/A/m0-s0/metrics.json) | 0 | None | 6.7758e-07 | 3.0109e-06 | 0.0232979 | 277 |
| radial | [A](comparison/radial/A/m0.0001-s11/metrics.json) | 0.0001 | 11 | 6.7758e-07 | 3.0109e-06 | 0.0232979 | 277 |
| radial | [A](comparison/radial/A/m0.0001-s29/metrics.json) | 0.0001 | 29 | 6.7758e-07 | 3.0109e-06 | 0.0232979 | 277 |
| radial | [A](comparison/radial/A/m0.0001-s47/metrics.json) | 0.0001 | 47 | 6.7758e-07 | 3.0109e-06 | 0.0232979 | 277 |
| radial | [A](comparison/radial/A/m0.001-s11/metrics.json) | 0.001 | 11 | 7.1508e-07 | 3.1754e-06 | 0.0255521 | 279 |
| radial | [A](comparison/radial/A/m0.001-s29/metrics.json) | 0.001 | 29 | 7.5114e-07 | 3.3342e-06 | 0.0258503 | 277 |
| radial | [A](comparison/radial/A/m0.001-s47/metrics.json) | 0.001 | 47 | 7.5114e-07 | 3.3342e-06 | 0.0258503 | 279 |
| radial | [A](comparison/radial/A/m0.01-s11/metrics.json) | 0.01 | 11 | 5.0766e-07 | 2.217e-06 | 0.0186049 | 271 |
| radial | [A](comparison/radial/A/m0.01-s29/metrics.json) | 0.01 | 29 | 8.6304e-07 | 3.4347e-06 | 0.0337487 | 184 |
| radial | [A](comparison/radial/A/m0.01-s47/metrics.json) | 0.01 | 47 | 7.063e-07 | 3.1147e-06 | 0.0285006 | 243 |
| radial | [B](comparison/radial/B/m0-s0/metrics.json) | 0 | None | 6.7758e-07 | 2.7167e-06 | 0.0232979 | 482 |
| radial | [B](comparison/radial/B/m0.0001-s11/metrics.json) | 0.0001 | 11 | 6.7758e-07 | 2.7167e-06 | 0.0232979 | 482 |
| radial | [B](comparison/radial/B/m0.0001-s29/metrics.json) | 0.0001 | 29 | 6.7758e-07 | 2.7167e-06 | 0.0232979 | 482 |
| radial | [B](comparison/radial/B/m0.0001-s47/metrics.json) | 0.0001 | 47 | 6.7758e-07 | 2.7167e-06 | 0.0232979 | 482 |
| radial | [B](comparison/radial/B/m0.001-s11/metrics.json) | 0.001 | 11 | 7.1508e-07 | 3.1754e-06 | 0.0255521 | 486 |
| radial | [B](comparison/radial/B/m0.001-s29/metrics.json) | 0.001 | 29 | 7.5114e-07 | 3.008e-06 | 0.0258503 | 482 |
| radial | [B](comparison/radial/B/m0.001-s47/metrics.json) | 0.001 | 47 | 7.5114e-07 | 3.008e-06 | 0.0258503 | 486 |
| radial | [B](comparison/radial/B/m0.01-s11/metrics.json) | 0.01 | 11 | 5.0766e-07 | 2.217e-06 | 0.0186049 | 610 |
| radial | [B](comparison/radial/B/m0.01-s29/metrics.json) | 0.01 | 29 | 8.6304e-07 | 3.4347e-06 | 0.0337487 | 236 |
| radial | [B](comparison/radial/B/m0.01-s47/metrics.json) | 0.01 | 47 | 7.063e-07 | 3.1147e-06 | 0.0285006 | 358 |
| radial | [C](comparison/radial/C/m0-s0/metrics.json) | 0 | None | 6.2981e-07 | 2.4628e-06 | 0.0227478 | 294 |
| radial | [C](comparison/radial/C/m0.0001-s11/metrics.json) | 0.0001 | 11 | 6.2981e-07 | 2.4628e-06 | 0.0227478 | 294 |
| radial | [C](comparison/radial/C/m0.0001-s29/metrics.json) | 0.0001 | 29 | 6.2981e-07 | 2.4628e-06 | 0.0227478 | 294 |
| radial | [C](comparison/radial/C/m0.0001-s47/metrics.json) | 0.0001 | 47 | 6.2981e-07 | 2.4628e-06 | 0.0227478 | 294 |
| radial | [C](comparison/radial/C/m0.001-s11/metrics.json) | 0.001 | 11 | 6.6247e-07 | 2.4076e-06 | 0.024711 | 298 |
| radial | [C](comparison/radial/C/m0.001-s29/metrics.json) | 0.001 | 29 | 6.9385e-07 | 2.5255e-06 | 0.0250622 | 294 |
| radial | [C](comparison/radial/C/m0.001-s47/metrics.json) | 0.001 | 47 | 6.9385e-07 | 2.5255e-06 | 0.0250622 | 298 |
| radial | [C](comparison/radial/C/m0.01-s11/metrics.json) | 0.01 | 11 | 4.7255e-07 | 1.7898e-06 | 0.0175082 | 368 |
| radial | [C](comparison/radial/C/m0.01-s29/metrics.json) | 0.01 | 29 | 7.8989e-07 | 2.8898e-06 | 0.0322303 | 168 |
| radial | [C](comparison/radial/C/m0.01-s47/metrics.json) | 0.01 | 47 | 6.5262e-07 | 2.5564e-06 | 0.0274717 | 250 |

Work counts exclude final audits and the independent oracle. BIE counts combine completed
objective frequency solves and TD frequency solves (the latter have twice the source RHSs).
Objective calls rejected before a completed BIE prediction remain in `evaluation_count`.
Counts are not weighted for different component/node counts. No controlled wall-time claim.
