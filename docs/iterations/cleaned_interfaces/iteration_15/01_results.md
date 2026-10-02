# NU-007 results: stage 1 fails its bound gate; the campaign was not run

2026-10-02. Result of the [pre-registered plan](03_plan.md). The user replied "go".

## Decision

**Stopped at stage 1, as the plan requires.** The pre-check passed two of its three gates and failed
the third:

| Gate | Result |
|---|---|
| 1. Same decisions (status, reason, bit-identical candidates) | **pass**: 864/864 trials |
| 2. Same tier sequence for every curve | **pass**: 864/864 trials |
| 3. Increment and full bounds agree to ≤ 10⁻⁹ relative | **fail**: worst 1.5·10⁻⁵ |

The six-case campaign was not prepared or run, so device certificates are **not adopted**. NU-006
remains the current pipeline.

Certificate time in the pre-check fell from 1,520 s (host) to 151 s (device), 10× faster.

Record: [precheck.json](../../../../results/validation/cleaned_interfaces/NU-007-precheck/precheck.json).

## Why gate 3 failed (diagnostic, after the fact)

[`nu007_gap.py`](../../../../experiments/cleaned_interface/nu007_gap.py) replays the same 864 trials.
It records every one of the 3,824 bounds, host and device, with their absolute difference and each
bound's distance from 1.

| Quantity | Value |
|---|---|
| Largest absolute bound difference | 4.7·10⁻¹⁰ (an increment bound of 3.1·10⁴ on `hook` `fixed_M37`, 1.5·10⁻¹⁴ relative) |
| Largest difference in the certified lower bound λ | 1.7·10⁻¹³ |
| Bounds with relative difference > 10⁻⁹ | 477, all with host bound ≤ 9.9·10⁻⁵ |
| Largest difference relative to max(1, \|bound\|) | 6.0·10⁻¹² |
| Smallest distance of any bound from 1 | 6.4·10⁻³ |
| Bounds on different sides of 1 | 0 |

**Measurement.** The relative gaps occur only where the bound itself is tiny. Those are full-tier
bounds of order 10⁻⁸ on near-circular, low-band states (`wrong_circle` and `peanut` damped stages,
warmups). There the bound is mostly ρ plus the allowance, at the FFT round-off floor, and the two
FFT libraries round differently by about 10⁻¹⁴ in absolute terms.

**Interpretation.** A tier compares the bound with 1, so only an absolute difference near 1 can
change a decision. The worst such difference (6·10⁻¹²) is nine orders of magnitude smaller than the
smallest distance from 1 (6.4·10⁻³). Gate 3 measured the wrong quantity. That is a design error in
the plan, not a defect found in the port. This reading was formed after the failure, so it does not
change the stage-1 decision.

## Proposed next (not run)

**NU-007a:** NU-007 unchanged, with gate 3 replaced by
|bound_host − bound_device| ≤ 10⁻⁹ · max(1, |bound|) and the same side of 1 for every bound.
The scale matches the decision threshold. On the recorded trials it would pass at 6·10⁻¹², but it is
set after seeing these data, so it needs explicit approval. If approved: rerun the pre-check under
the new gate, then the six-case campaign with the plan's decision rule and predictions unchanged.
