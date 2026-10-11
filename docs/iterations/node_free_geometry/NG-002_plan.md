# NG 002 targeted nonlinear construction and certificate evaluation

2026-10-11. Pre-registration after the complete NG-001 baseline and before
new numerical runs. User authorizes experiments without another approval.
The existing branch is retained. Two independent component interventions;
no inverse run, maintained selector or default change.

NG-001 constructs 163/279 coarse moves accurately, certifies 57/279 and
proves 15/31 bases. Eighty coarse refusals are binomial range/degree limits;
all 304 unresolved trial proofs exhaust five seconds. These are the specific
mechanisms to test, rather than a new shape representation.

## A: inverse-root polynomial iteration

Use the [Newton derivation](NG-001_newton_derivation.md). Initialize with
c=gamma*mean(S), gamma a power of two giving c>=2*the positive range upper
bound. Choose at least eight iterations from e<-1e-14 via
e_new=e²(3+e)/4, maximum 64. Differentiate the actual finite grouping and
crops, including dc=gamma*dmean(S). Select the positive inverse-root branch.
Keep every NG-001 full speed/phase residual tolerance unchanged.

Replay all 279 exact frozen moves against the NG-001 saved qualified refined
references. Hash those files. First test the same coarse/fine bands as
NG-001, isolating the scalar proposer. Then, only for unresolved pairs,
double the working band up to coarse B<=2048 and fine 2B<=4096. Every failed
attempt and its cost stays charged. Permit at most 20 seconds per move,
checked between attempts; one running attempt may exceed that boundary.
The working-band discrepancy and both reference accuracy gates remain
1e-5 and 1e-7 times the base mean speed. Unqualified references do not rank.
No accuracy tolerance is relaxed and no coefficient pruning is introduced.

The iteration is the one changed construction allowed by NG-001; bandwidth
escalation distinguishes scalar convergence from unresolved Fourier tails.
Report fixed-band versus escalated counts separately. A construction-only
success is not a certified geometry update or an inverse success.

Complete tangents use all five diagnostic states and their three fixed
directions. NG-001 saved the comparator errors but omitted the independent
analytic derivative arrays; recompute analytic quadrature at 2N and 4N.
Compare with its refinement, the saved current complete tangent, and self differences at
1e-7 and 5e-8 m. Retain the 1e-3 gate and 1e-5 diagnostic. Include source
hashes of tangent references. Recompute analytic controls at bands
256,512,1024,2048,4096, stopping at the first qualified base constructor;
compare base arclength projection against N16384 quadrature. The regular
quadratic a=.49 is a conditioning control, not an admissible offset claim.

Prediction: the range/degree limitation disappears when the range is positive
and nonlinear tails fit the band. Near-arclength states may cost more because
the original binomial degree was already low. Residual, phase and positive
range refusals can remain. Count those separately; scalar convergence does
not establish a cropped-series theorem.

## B: directed interval Horner jets

Replace per-mode interval exponentials at each Taylor anchor by one directed
interval exp(i*theta), positive/negative Laurent Horner recurrences and a
parallel derivative polynomial. All coefficients, Taylor radii, omitted-tail
norms, arc coverage, separation and monotone projections retain directed
arithmetic. This changes evaluation cost and enclosure width, not the proof
criterion. Bind reusable certificates to a hash of the exact coefficient
curve and refuse mismatched reuse. Reject nonfinite/invalid coefficient input.

Re-certify all 31 exact NG-001 base curves with the same 30 digits, five-second,
20,000-pair and depth-18 budgets. Compare count, elapsed time and bounds with
the frozen original receipts. Repeat the known circle/ellipse/quadratic
controls: no cusp or crossing may be accepted. This base-only replay does
not establish complete-trial speed or validity rates for the Newton moves.

## Evidence and stopping

One worker, single BLAS/OpenMP threads, fresh directory, source snapshots and
hashes, incremental receipts and failure traceback. Patch all FourierCurve
sampling/fitting entry points to fail during new-engine calls. Zero physics
calls. Do not edit measured sources while running. Validate report completeness
and focused tests, then commit and push code, documentation and all evidence.
Stop after these two mechanisms have been decided; further work needs a
specific unresolved scientific question. No end-to-end performance claim:
the current implementation is reused as frozen numerical evidence, not timed
again in this targeted component replay.
