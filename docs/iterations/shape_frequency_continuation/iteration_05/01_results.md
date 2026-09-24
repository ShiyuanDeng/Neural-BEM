# Iteration 05 — regression against the previous explicit Fourier inverse

2026-09-23. User-requested comparison, restricted to single objects first.

**The previous Cartesian Fourier inverse passes all six cases. Each of the
four new policies passes only circle-to-circle.** The old pipeline remains the
stronger recovery baseline on these fixtures. The new implementation's earlier
plane-wave examples did not establish parity on the existing paired-source
inverse problems.

**Subsequent diagnosis (SC-019):** the inherited 1% curvature-tail gate at
band 20 excludes the exact star, whose tail is 8.07%. Step halving alone
improves ellipse-to-star but does not recover it. The star failures below
therefore include an incompatible admissibility setting; they cannot support
an intrinsic inferiority claim about the normal-update representation or
adaptive continuation. See the [completed follow-up](../iteration_06/01_results.md).

## Evidence and protocol

[SC-018 results and boundary overlays](../../../../results/validation/shape_continuation/SC-018-legacy-single-object/README.md)
contain all 30 runs, including every unsuccessful recovery.
The [comparison protocol](../../../../results/validation/shape_continuation/SC-018-legacy-single-object/protocol.md)
records the inputs, declared differences, gates and reproduction command.

The six fixtures are the previous circle and five-lobed-star targets, each
started from the old circle, ellipse and star initializations. Every arm reads
the same independent observations, 24 paired point sources/receivers, known
material contrast 0.5, exact initial Cartesian K6 coefficients, training
frequencies 0.5/1.5/2.5 GHz and unused frequencies 0.25/1/2 GHz. These are fresh
matched runs of existing fixtures, not comparisons to previously saved timings.

The baseline retains the old cumulative-frequency finite-difference LM inverse,
its 150-update allocation and 2-mm modal step limit. New arms retain the SC-017
GN/SD filter-only optimizer, using single-frequency objectives. All receive
6000 single-frequency forward solves and 600 seconds, with probe costs charged.
Shared adaptations for the new arms are declared: minimum storage band 128,
advancement through the sparse measured frequency catalog, and a terminal
progress guard. No run exhausted its cap or raised an algorithm/evaluation
exception; all reached the highest supplied training frequency.

## Results

The practical recovery gate requires a continuous-boundary error upper bound
at most 1 mm, pooled training relative L2 at most 0.003, worst unused-frequency
relative L2 at most 0.05, and endpoint field refinement at most 1e-6.

| Arm | Cases passing | Inverse frequency solves per case |
|---|---:|---:|
| Previous Cartesian Fourier | 6/6 | 1663–3147 |
| New fixed schedule/band | 1/6 | 7–35 |
| New measured band | 1/6 | 34–251 |
| New measured frequency | 1/6 | 19–47 |
| New measured band and frequency | 1/6 | 34–251 |

Only circle-to-circle passes for the new arms. On that case the new fixed arm
uses 19 solves and attains worst held-out error 5.28e-8, versus 1663 solves and
1.98e-6 for the old baseline. This is a useful local efficiency result; the
failed cases' low solve counts are early stops, not speedups at equal accuracy.
Different resolutions, derivative methods and concurrent execution also prevent
treating solve counts or timings as equal-FLOP measurements.

Ellipse-to-star reproduces the earlier baseline's strong recovery: sampled
symmetric boundary error **2.79e-9 m**, versus **58.7 mm** for the new fixed arm
and **27.3 mm** for measured band/full. Worst held-out errors are respectively
**2.01e-7**, **1.84**, and **1.54**. Across all six legacy runs the sampled
boundary errors are 1.11–6.59 nm. These sampled values are not nanometre
certificates: the common conservative continuous-boundary bounds include a
roughly 19–31 micrometre sampling allowance.

The three-frequency catalog gives frequency selection no alternative at each
transition. Accordingly, fixed and frequency arms have identical endpoint
coefficients in every case, as do band and full. Frequency probes add cost but
cannot change the path here. This suite tests compatibility with the old data
and overall recovery, not the benefit of adaptive frequency selection on a
dense catalog.

## Checks and interpretation

The line-source bridge preserves physical amplitudes and paired sampling;
unmeasured cross-pairs are never supplied to the inverse. The independent
[bridge audit](../../../../results/validation/shape_continuation/SC-018-legacy-single-object/bridge_audit.json)
compares both exact targets at all six frequencies: worst field disagreement
is **3.86e-10**. On each of the three starts at all training frequencies, the
paired normal derivative agrees with a centered finite difference to at worst
**6.08e-9** for the tested direction. Every endpoint's N/2N field discrepancy
is below **1.35e-12**. The observed recovery failures therefore have no evidence
of a unit-conversion, pairing, tested-derivative or endpoint-resolution defect.

Validation: **104 continuation tests and 114 Kress/ordered-boundary tests pass**.
All source/input hashes agree with the frozen manifest; all 30 subprocesses
completed and all endpoints were scored. The
[verification record](../../../../results/validation/shape_continuation/SC-018-legacy-single-object/verification.json)
records those checks. Six earlier budget smoke runs also preserved scoreable
endpoints.

The new unsuccessful runs terminate through small-step or exhausted candidate
search reports, with substantial residuals and budget remaining. The saved
per-decision trajectories distinguish these stops from convergence. This
comparison does not isolate the cause: cumulative versus single-frequency
objectives, LM step control versus filter-only GN/SD, and the different shape
update spaces all change together. Calling this a harmonic-transport failure
alone would go beyond the evidence.

The next useful experiment is a controlled diagnosis of one failed noncircular
start, retaining this baseline and changing one of those ingredients at a time.
The immediate requirement is recovery parity before an improved adaptive
inverse claim. SC-015/016's fixed-geometry measurements remain evidence in
their own scope; SC-018 supplies negative evidence for the current recovery
policy. Topology, noise and unknown-material inversion were not run.

Implementation: [matched harness](../../../../experiments/shape_continuation/legacy_cases.py),
[point-source bridge tests](../../../../experiments/shape_continuation/test_point_sources.py).
Existing solver/inverse production defaults were not changed. No new branch
or worktree was created. No independent review is claimed.
