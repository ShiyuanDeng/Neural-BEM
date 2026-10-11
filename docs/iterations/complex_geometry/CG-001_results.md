# CG-001 — qualified physical fold transport

2026-10-11. **Supported component mechanism; no inverse advantage established.**

An exact transmission disk with a genuinely complex radius can be transported
around a numerically qualified fold of a TG-002 data objective and returned to
a different valid real stationary radius. One loop exchanged a minimum and
maximum of the interpolated objective; two loops restored the original root
within 7.64e-14 in dimensionless radius. Upper/lower half loops instead ended
at nonreal conjugate radii. Real pseudo-arclength also passed the fold.

The fixed-center radius chart intentionally cannot represent the displaced
TG-002 circle. This is neither unrestricted geometry recovery nor a benchmark
score. All paths use measured observations and the prescribed centered start;
truth never enters the instrument or path selection.

## Evidence chain

1. [Run 01](CG-001_run01.md): all real physics checks passed; finite-difference
   reference steps failed three complex derivative checks. Failed evidence
   committed/pushed before the single bounded reference correction.
2. [Run 02](CG-001_run02.md): independent Cauchy and smaller finite-difference
   checks passed, eight frozen objectives yielded 134 detected qualified folds
   in t∈[0,1], and the selected physical loops passed all transport checks.
   The real control's 200 steps could not reach the fold; its overall
   `UNQUALIFIED_TRANSPORT` status is preserved.
3. [Run 03](../../../results/validation/complex_geometry/CG-001/run-03/completion.json):
   the preregistered quota completion used the unchanged equations, start and
   step length for 6000 steps. It exactly reproduced the first 200 states,
   crossed the fold, and ended on the opposite-Hessian branch. The combined
   result is `QUALIFIED_LOCAL_MONODROMY`.

The selected fold is contrast 13.3, 1.5 GHz, radius 64.700127606 mm and
t=0.649167247036. It is connected to the centered 65 mm start without a grid
search. At the loop's common real parameter t=0.637598234, the Hessian changes
from +3751.70 to −9453.63. The normalization is relative observed-data norm
and radius measured in 50 mm units; these numbers are coordinate-dependent.

The returned maximum has a slightly higher interpolated-data loss. Its
measured-data loss at t=1 is lower, but it is not established as stationary
there. Transporting a stationary branch is not equivalent to minimizing the
desired measured-data loss.

The [post-run literature/theory audit](LITERATURE_THEORY_AUDIT.md) supplies
an exact local fold factorization and a derived loss-barrier check. The
observed/predicted barrier ratios are 1.01748 and 1.00867 for the original
and half-radius loops, consistent with the predicted relative O(tf−t)
correction. This added arithmetic diagnostic uses saved losses only and is
not a new preregistered gate. The finite modal sum is numerically qualified;
neither an exact fold enclosure nor an infinite-series tail bound is claimed.

## Real comparison and conditional exploration

The completed real pseudo-arclength control ends at q=1.2938012177,
t=0.6262785054, with Hessian −15493.65 and scaled stationarity 4.12e-14.
Its accepted states passed cutoff refinement. Thus the natural-parameter
stall is a coordinate singularity that real continuation can also handle.

The already registered adjacent-fold probe was attempted after the control
passed. Its sampled real t(q) attachment left the declared finite homotopy
domain or crossed a B=0 discontinuity, yielding `BRANCH_DOMAIN_REFUSAL`.
No second local loop was executed. This is a limit of the tested attachment,
not evidence that complex paths cannot connect those sheets.

## Decision and next discriminating question

Close CG-001 and retain the demonstrated uniform-complex-scaling mechanism.
General complex Fourier geometry and singular BIE quadrature remain untested.
The primary literature supports local analyticity under stated assumptions,
not a global successful return theorem; see the [derivation](DERIVATION.md)
and [assumption-by-assumption literature audit](LITERATURE_THEORY_AUDIT.md).

A focused extension is justified by the nonreal half-loop endpoints and
failed real adjacent-fold attachment: test fixed complex data paths all the
way to t=1 and require a real stationary endpoint there. This asks whether
the local transport can deliver a minimum of the actual measured-data loss,
rather than merely a root of an interpolated problem. It is a separate
pre-registered component experiment, not an inverse campaign.

Total measured run times were 63.63 + 103.54 + 9.43 = 176.60 seconds, including
failed qualifications, construction, census, all failed steps and refinements.
Peak process RSS was under 473 MiB. Preparation/review time is additional;
concurrent unrelated research makes these unsuitable speed-comparison data.

Independent theory and implementation reviewers checked the mirror system,
analytic jets, fold conditions, controls and interpretation. The run-03 quota
extension was reviewed as a resource correction, with run-02 evidence retained.

[Full raw run 02](../../../results/validation/complex_geometry/CG-001/run-02/README.md)
· [Run 03 outcome](../../../results/validation/complex_geometry/CG-001/run-03/outcome.json)
