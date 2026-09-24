# Independent SC-026 audit and controlled sensitivity reanalysis

The [audit](audit.json) independently checks the twelve dense-file hashes,
twelve source-input hashes, all 1,286 curve keys, 2,066 occurrence records,
finite cell arrays and loss algebra. Recomputed SC-022 G/g discrepancies
are <=4.5e-16. Original inputs and outputs are unchanged.

The 1,875 recorded step occurrences reduce to 1,280 unique transitions.
Of these, 24 meet the original truth-assisted pathological-sharpening
definition, all in stage 1. Counts by case: circle 6, star 0, C 13,
kite 0, peanut 4, hook 1. The definition is not a complete failure detector.
Average next-frequency gradient agreement across case-level fractions is
98.0%, rather than treating all repeated states as independent evidence.

**Coverage limitation:** 967/1,286 states have normal-ray coverage below
99%; the lowest is 50.7%. A subsequent no-solve
[sensitivity reanalysis](sensitivity.json) retains only coverage >=99%
and misalignment <=5%, and uses exactly the four original or nine proposed
training frequencies, rather than every intervening atlas frequency.

232 states meet that filter (circle 39, star 55, C 15, kite 1, peanut 58,
hook 64). All 57 states in the original 0.1–1 mm distance bin remain.
For these 57 states:

| Declared model | Original four, through 1.25 GHz | Extended nine, through 2.5 GHz |
|---|---:|---:|
| 0.1-mm RMS move, sigma=0.001 per real normalized component | 1.02% | 91.18% |
| 1-mm RMS move, same component sigma | 25.49% | 97.82% |

Entries are median shares of normal-ray error projected into generalized
Jacobian eigen-directions above the declared threshold. They support the
frequency-extension hypothesis under the stated model. They are **not**
measured noise levels, confidence bounds, joint harmonic identifiability,
or proof that an optimizer recovers the boundary. Retaining only one kite
state prevents interpreting this filtered analysis as evidence across its
whole trajectory. The later P=48 refinement failure also limits a blanket
numerical qualification claim for the dense atlas at rough states.

The recovery settings were frozen before this supplemental reanalysis;
these truth-assisted numbers never enter fitting or choose an iterate.

Reproduce from the repository root:

```bash
export PYTHONPATH=solvers:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY results/validation/shape_continuation/SC-026-independent-audit/audit.py
$PY results/validation/shape_continuation/SC-026-independent-audit/sensitivity.py
```
