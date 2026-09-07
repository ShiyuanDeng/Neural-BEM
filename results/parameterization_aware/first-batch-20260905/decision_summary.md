# Supplemental bandwidth decision from frozen C1/C2 measurements

This view adds the brief's lower-usable-bandwidth criterion. It reruns no extraction, fitting, oracle or BEM solve and changes no measured artifact.

The original matched-work findings are preserved: 0 ordered-label case/arm comparisons exceed the declared 10% work reduction threshold. The table separately identifies lower usable bandwidth at the same declared geometry/field gates, without an observed increase in BEM node count or raw matrix condition. A bounded bandwidth benefit is not a general runtime or reconstruction claim.

| Case | Arm | B minimum usable K / N | Candidate K / N | Lower K without increased N or condition |
|---|---|---|---|---:|
| circle | skip-arclength | 1 / 32 | 1 / 32 | False |
| circle | ordered-label-unregularized | 1 / 32 | 1 / 32 | False |
| circle | ordered-label-penalized | 1 / 32 | 1 / 32 | False |
| ellipse | skip-arclength | 16 / 32 | 16 / 32 | False |
| ellipse | ordered-label-unregularized | 16 / 32 | 1 / 32 | True |
| ellipse | ordered-label-penalized | 16 / 32 | 1 / 32 | True |
| star | skip-arclength | none in bounded ladder | none in bounded ladder | False |
| star | ordered-label-unregularized | none in bounded ladder | 8 / 64 | False |
| star | ordered-label-penalized | none in bounded ladder | 8 / 64 | False |
| nonstar | skip-arclength | none in bounded ladder | none in bounded ladder | False |
| nonstar | ordered-label-unregularized | none in bounded ladder | 8 / 128 | False |
| nonstar | ordered-label-penalized | none in bounded ladder | none in bounded ladder | False |

Minimum usable bandwidth is evaluated only on this bounded K/N ladder. When B has no qualifying row, there is no matched-accuracy B work or conditioning comparison; the candidate's success is reported without treating the unqualified baseline as an equal-accuracy competitor.

A lower usable bandwidth is separate from a measured speed advantage. The node and raw matrix-condition ratios are retained explicitly; no production default is promoted.

Postprocessing command: `/home/drdeng/miniconda3/envs/EMNerf/bin/python /home/drdeng/Neural_SDF_BEM_AD/run_parameterization_aware_comparison.py --output results/parameterization_aware/first-batch-20260905 --summarize-existing`.

The supplemental JSON records input/source hashes, exact N and matrix-condition ratios, and the original timing decisions.
