# GGB-003 — Stage-one translation greatly improves case 8

Approved and completed 2026-10-05. **Exact translation fixes most of the
positioning error, but the complete inverse still fails its recovery criteria.**
This supports adding explicit translation to continuation. It does not yet
validate a decreasing-sensitivity schedule or justify changing the default.

## Matched comparison

Both arms use the byte-identical GGB-002 four-frequency observations, known
material, centred radius-0.35 m start, certified-spectral shape updates and
original acceptance/resolution rules. B is the original normal-only fit.
T alternates exact Cartesian translation and ordinary shape updates during
M3 only, then runs ordinary M7 and M11. Translation is capped at 18 mm per
axis and changes only Cartesian c0. There is no truth-guided direction or
artificial Jacobian multiplier. Both arms retain the same work/time limits.

| Endpoint measurement | Control B | Stage-one translation T |
|---|---:|---:|
| Centre error | 458.58 mm | **1.40 mm** |
| Equivalent radius; target 172.73 mm | 148.76 mm | 180.61 mm |
| Refined joint loss | 0.616564 | **0.0112442** |
| Fitted-frequency residuals | 110.83–111.28% | **13.94–16.17%** |
| Image SSIM | 0.888964 | **0.983228** |
| Image RRMSE | 0.067489 | **0.020963** |
| Contrast SNR | −2.36 dB | **8.89 dB** |
| Fit wall time | 4.447 s | 297.680 s |
| Endpoint audit wall time | 0.073 s | 0.062 s |
| Fit work units | 193 | 2625 |
| Noise-discrepancy recovery | No | No |
| Endpoint field-refinement gates | Pass | Pass |

The joint loss falls 98.18%. The fresh control reproduces all 16 archived
GGB-002 F4 states and its endpoint predictions bitwise, so the geometric
improvement is not a baseline change. These are single wall-time observations;
brief CPU video-qualification activity overlapped the run sequence. No other GPU compute
process was reported immediately before B. This is not a repeated timing
benchmark, and B's short time reflects early failure.

## What actually happened

T's M3 stage accepts 44 translations and 38 ordinary shape updates, reaches
approximately 10 mm centre error, then stops when neither block can decrease
the objective. M7 accepts 20 ordinary shape updates; M11 accepts 15 more.
The final boundary is correctly positioned and resembles the target, but
retains two thin protrusions. Accurate centroid and high SSIM alone conceal
that remaining shape defect.

M11 then proposes a nearly self-touching curve whose modal kernel expansion
requires more than 4000 Chebyshev terms (`beta/Lambda=1.52e-5`). The frozen
candidate-failure policy stops the fit. The last accepted endpoint is retained;
its maximum fitted-frequency field-refinement error is 1.35e-5, below 1e-4.
The failed candidate and its exception are retained separately.

All four data residuals remain above their approximately 5.49% noise targets;
the joint loss target is 0.00150961. The unused archived 0.4 GHz residual is
13.52%, also above its 5.50% target. **The endpoint is resolved under the field
check but is not recovered.** `COMPLETE` in the receipt means the driver and
audits finished; the optimizer outcome remains `NUMERICAL_FAILURE`.

## Where the time went

Translation blocks take **13.94 s**, 4.68% of total fit time. Ordinary shape
blocks and later stages take **283.39 s**, 95.20%. Within those operations,
shape trial construction takes **261.63 s**, 87.89% of total fit time,
including **260.32 s** of geometry certification. These are nested timers:
do not add certificate time to trial or block time.

Of 811 proposed candidates, 117 are accepted, 628 are refused for
self-intersection, 35 have unresolved projection, 30 fail the acceptance
margin and one fails physics. M3 alone spends 177.68 s in shape blocks versus
13.94 s in translation blocks. The treatment respects the original budgets:
M3 spends 2180/2600 work units; the entire fit spends 2625/8000 and does not
hit the 2400-second limit. Refused geometry still costs wall time even without
a charged field solve.

The new alternating controller rebuilds each block's objective/Jacobian and
therefore has avoidable evaluation overhead. Nevertheless, the measured
dominant cost is shape construction/certification, not the two translation
coordinates or the final field audit. Speed work should target repeated
inadmissible shape proposals while preserving the acceptance checks.

## Interpretation and next priority

The positioning hypothesis is strongly supported on this case. Keep explicit
translation available in early continuation. The next focused issue is shape
step control: stop forming thin protrusions and repeatedly attempting invalid
updates. A more translation-dominant initial phase is a plausible next test,
but this run does not establish that schedule or a specific sensitivity decay.
No additional experiment or parameter tuning was performed.

The historical GauGal case-8 image RRMSE is 0.01891 and optimization time
0.814 s; T reaches RRMSE 0.02096 in 297.68 s. We have closed much of the image
quality gap, but cannot claim competitive recovery or speed. GauGal used the
original single-frequency data and estimated material, whereas this BEM test
uses four frequencies and known material; this is not an equal-data/prior
comparison. See the [earlier audit](INVERSE_PIPELINE_AUDIT.md).

## Evidence and validation

- [Approved preregistration](GGB-003_plan.md).
- [Detailed receipts and per-frequency table](../../../results/validation/cleaned_interfaces/GGB-003/report.md).
- [Direct boundary comparison, SVG](../../../results/validation/cleaned_interfaces/GGB-003/boundary_comparison.svg).
- [Translation-arm boundary video](../../../results/validation/cleaned_interfaces/GGB-003/T/video/case8_stage1_translation_boundary.mp4): all 118 saved states, 65.5 s, 1280×800 at 12 fps, using the existing video encoder; no material-image rasterization or interpolated shapes.
- [Derived accounting and independent review](../../../results/validation/cleaned_interfaces/GGB-003/analysis.json).

105 package/adapter/controller tests passed. Full-panel translation derivatives
on CPU and CUDA agree with rebuilt translated fields within 1.431e-9 relative
column error. Independent review confirms all 44 translation steps preserve
every nonzero Cartesian coefficient exactly, translation is absent from M7/M11,
separate damping and shared budgets are respected, and saved endpoints match
accepted callbacks. Both arms' residuals and image metrics were recomputed
from saved artifacts. The first failed qualification and its source snapshot
are preserved. Direct boundary comparison and final video frame were visually
checked; encoding manifests verify every saved state appears.
