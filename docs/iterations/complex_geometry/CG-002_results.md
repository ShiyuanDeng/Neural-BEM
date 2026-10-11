# CG-002 — fixed complex detours reach a nonreal measured-data root

2026-10-11. **Hypothesis refuted for the frozen route family: 0/3 positive
doglegs return to a real radius-family minimum at t=1.** All three complete
their parameter paths and satisfy the numerical stationarity/refinement gates.
The failure is endpoint reality, not failure to continue through the fold.

The instrument is the exact transmission disk developed and independently
qualified in [CG-001](CG-001_results.md): fixed center, complex radius, TG-002
circle observations at 1.5 GHz, contrast 13.3, and the prescribed 65 mm centered
start. The model intentionally cannot represent the displaced true circle.
No truth or alternate start enters any path.

## Result

The positive paths `[0, i*eta, 1+i*eta, 1]` for eta=.001,.01,.1 all reach

    q = 1.293675698042859 - 0.000488579883476 i
    R = 64.6837849021 mm - 0.0244289942 i mm,

at t=1. Their negative-height controls reach the exact conjugate endpoints.
The imaginary radius is approximately 48,900 times the declared reality
threshold. A small imaginary part cannot be silently projected away: that
would change the computed root and introduce an unregistered restart.

| Control | Measurement |
|---|---:|
| Positive routes returning real | 0 / 3 |
| Completed complex arms, including symmetry/half-step checks | 9 / 9 |
| Largest half-step endpoint discrepancy, dimensionless q | 4.45e-16 |
| Positive/negative endpoint conjugation discrepancy | 0 at stored precision |
| Maximum accepted-state scaled stationarity in all refined checks | 1.00e-11 |
| Maximum field/Hessian change at cutoff+12 | 0 at stored precision |

All 12 arms meet the registered numerical qualification checks. Complex paths
are refined at every accepted state; real controls at 65 evenly spaced states
plus the endpoint and most demanding stored pole/imaginary-geometry state.
Zero reported modal-refinement difference means agreement at floating-point
precision; it is not a mathematical zero-error certificate.

## Mechanism and real controls

The independent reviewer predicted that increasing dogleg height might leave
its winding around relevant critical values unchanged. Identical positive
endpoints across a 100-fold height change support this explanation. Negative
routes select the conjugate continuation. This is evidence about the tested
paths, not a proof of their global topology or a no-real-solution theorem.

Natural real-parameter continuation stops at the already qualified fold near
t=.64916724. Real pseudo-arclength was given sufficient exposure in both
initial directions (ds=.0002, 20,000-step allowance per direction):

- Increasing-t orientation passes the first fold, then stops from Newton
  failure at t=.003449893, q=1.293272102. Its final Fq≈−2.536e5 is nonsingular,
  and its pole margin is .00660. This is a numerical corrector limitation,
  not an established branch barrier. An untested explanation is that
  `|Fq|*ulp(q)≈5.6e-11` exceeds the `1e-11` corrector tolerance at scale one.
- The opposite orientation reaches the declared t=−2 domain boundary.

Neither real control produces a t=1 crossing, and neither establishes that
one cannot exist by another real path or a more robust corrector. Their
limits do not weaken the resolved observation that these complex doglegs
end nonreal.

## Decision and reproducibility

Close the fixed-dogleg experiment. Preserve CG-001's successful local
monodromy result. A worthwhile next theoretical/algorithmic question is a
truth-free rule for choosing winding sequences that move to a real minimum
at t=1; merely increasing detour height did not change the endpoint here.
General complex Fourier geometry and a full inverse comparison remain unrun.

Measured wall time including construction, all failed attempts, controls and
refinements: 23.49 s; peak process RSS is in the outcome receipt. Production
and refined instruments charged 57,306 and 6,776 frequency/radius jet
evaluations respectively. Each analytic jet includes the field and its first
three derivatives; these counts are not dense BEM solves. There is no runtime
comparison or speedup claim.

The [pre-registration](CG-002_plan.md), original failed runs, exact source/input
hashes and all compressed accepted/rejected trajectories are preserved.
The [combined figure and table](../../../results/validation/complex_geometry/report/README.md)
are generated read-only by `python -m experiments.benchmark.cg001_report`.
An independent scientific reviewer checked the saved endpoints and failure
interpretation. Focused tests, TG-002 seals and receipt validation passed.

[Raw outcome](../../../results/validation/complex_geometry/CG-002/run-01/outcome.json)
· [Manifest](../../../results/validation/complex_geometry/CG-002/run-01/manifest.json)
· [Read-only validation](../../../results/validation/complex_geometry/report/validation.json)
