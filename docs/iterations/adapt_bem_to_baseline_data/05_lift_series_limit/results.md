# Proposal feasibility evidence — no solver implementation

18 November 2026. `bem-gpu`; no solver lock held. This records the coordinator's
optional numerical probe allowance, not approval to implement the proposal.
The [one-page proposal](plan.md) still awaits the user's go/no-go.

## What ran

One CPU process, single-threaded BLAS, **2.958 s** numerical wall time out of
the 900 s allowance. Peak RSS **0.309 GiB**, minimum available host memory
**20.700 GiB**. No fit, full forward solve, solver edit or failure.
Start/end solver status was clean and every solver Python SHA-256 matched.
Source commit: `5d50a899a`; timestamp: 00:36:04 UTC.

[Probe script](../../../../experiments/bem_on_baseline_data/series_limit_proposal/probe.py)
and [raw results/provenance](../../../../results/bem/baseline_data/series_limit_proposal/2026-11-18/probe.json).
The exact command is in the plan and JSON. No bulk artifacts were produced.

The script reads the existing true star/cavity Fourier curves and receiver
layout solely for this experiment. It evaluates regular integer-order Bessel
waves and analytic speed-weighted normal flux at 1024, 2048 and 4096 parameter
points, transforms to coefficient window 256, and applies existing order scaling.
It synthesizes three plane-wave directions from these modal waves and compares
their retained coefficients with direct exponentials and analytic flux.

## Measurements

The legacy round-off threshold occurs at argument **17.667913** for 1e-9
and **24.746261** for 1e-6. At the true cavity's k=15, its estimate is
**139.2155**, so merely raising the threshold would discard its protection.

| Shape / exterior argument | Plane order | Graf order | 2048→4096 value error | 2048→4096 flux error | Plane synthesis value error at 4096 |
|---|---:|---:|---:|---:|---:|
| Star / 23.358 | 62 | 57 | 1.49e-15 | 1.43e-15 | 1.21e-15 |
| Cavity / 43.785 (k=15) | 95 | 88 | 1.94e-15 | 2.36e-15 | 1.41e-15 |
| Cavity / 45 | 97 | 89 | 2.40e-15 | 1.95e-15 | 1.45e-15 |
| Cavity / 65 (extra A3 stress check) | 129 | 118 | 3.40e-15 | 2.86e-15 | 2.09e-15 |

All errors are relative L2. Largest grid-doubling error over every measured
pair was **3.96e-15**; largest direct plane-value/flux comparison was **2.94e-15**.
These compare the retained coefficients; they are not a rigorous alias bound
or a comparison of complete scattered fields. The plane-wave reconstruction
check is independent of the regular-wave synthesis but uses the same sampled
curve. Point-source reconstruction and B7 were not tested in this proposal probe.

The receiver radius is about 10; the maximum coefficient-radius/distance
ratio is 0.29428 for the cavity, safely below the Graf separation refusal.
The existing order searches are far below their 1024 cap on these inputs.
Fitted curves nearer the receivers still need their own separation checks.

The incident plane-wave coefficients between mode 97 and mode 256 have
relative norm **1.2697e-3** for the true cavity at k=15. Between modes 193
and 256 the norm is **1.8129e-6**. These are partial high-mode norms normalized
by the retained window, not truncation-error bounds for solved traces.
They show why the current storage-derived trace cutoff of 96 cannot simply
be assumed sufficient. Increasing the FFT sample count alone does not change
the trace cutoff or fix operator-workspace truncation.

A separate **scalar A2** call used the conservative squared-diameter bound
`4*rho*rho`, exterior argument 45 and interior argument 65. Existing radial
construction passed at **degree 93**, **240 terms**, **64-bit significand**
working precision, and Neumann tail bound **9.29e-93**. Its reported coefficient
amplification was 9.87. This checks scalar coefficient generation only; it
does not qualify A2 geometry recurrences, window projection or matrix conditioning.

## Conclusion and limits

The proposed sampled A3 fallback is numerically plausible and inexpensive in
this small probe (largest 4096-point call: 0.748 s). Production integration,
alias/refusal rules, special-function extremes, point waves, derivatives and
the full operator still need the proposed proofs. No k=15 inverse result is
claimed. Boundary sampling is an explicit method trade-off for the user to
approve; the alternative preserves coefficient-only construction at a likely
larger arbitrary-precision cost.

If approved, the default-off switch would preserve the legacy default path.
The new route should use an independent accuracy check, allowing the legacy
threshold to return to 1e-9 for opted-in BRG calls. No current setting changed.

```text
Activity: adapt_bem_to_baseline_data/05_lift_series_limit, 18 November 2026
Runs: 1/1 standalone probe; wall time 0:00 (2.958 s)
Result: proposal written; measured grid/reconstruction errors below 4e-15.
Result: orders 97/89 at argument 45; scalar radial degree 93 at 45/65.
Failures: none; raw evidence at results/bem/baseline_data/series_limit_proposal/2026-11-18/probe.json.
Upstream patches: none
Changes to our code: standalone experiment probe only; no solver changes.
New unknowns: solved-trace/window convergence, alias guarantees and production cost.
Proposed next activity: implement only after user's go; needs user decision: sampling fallback versus coefficient-only alternative.
```

No solver lock is held. Work stops at this proposal.
