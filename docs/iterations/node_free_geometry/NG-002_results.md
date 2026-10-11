# NG 002 inverse-root iteration and interval Horner results

2026-10-11. [Plan](NG-002_plan.md), [derivation](NG-001_newton_derivation.md),
[numeric evidence](../../../results/validation/node_free_geometry/NG-002/run-01/report.json).
The 31-state, 279-move component replay completed in 112.18 s, using frozen
current-control references from NG-001. Zero physics calls; no inverse or
default changes. Measured sources are unchanged and all sampling guards pass.

| Construction result | NG-001 binomial | NG-002 Newton |
|---|---:|---:|
| Original coarse working bands | 163/279 | 170/279 |
| Both bands, with allowed escalation | Not tested | 178/279 |
| Original successful constructions lost | — | 0 |
| Qualified constructions passing 1e-5 and 1e-7 gates | 163 | 178 |
| Maximum coefficient-sum discrepancy | 1.115e-5 nm | 1.115e-5 nm |

Newton gains seven original-band constructions and bandwidth escalation gains
eight further qualified pairs. Tiny moves improve to 93/93, 1 mm moves to
71/93 and 6 mm moves to 14/93. All 178 references are qualified; maximum
relative coefficient discrepancy is 1.832e-13 and maximum coarse/fine
discrepancy is 7.627e-15. This is construction, not geometry acceptance:
admissibility of these newly produced moves was not replayed.

All 15 complete tangent directions pass in both bands (30 comparisons), with
maximum relative error 6.766e-13 against newly recomputed refined analytic
quadrature. Maximum self finite-difference discrepancy is 2.254e-9. Reference
refinement is at most 1.139e-12. No full-Jacobian cost claim is made.

The regular quadratic at a=.49 requires B2048 and matches independent N16384
base quadrature to coefficient-sum discrepancy 1.002e-15 m. The original
scalar expansion exceeded its 512-degree budget. Its speed ratio is 99;
this supports inverse-root iteration over a long mean-centred binomial series.
The cusp never constructs. The regular crossing can construct, as expected
for an arclength map, but the independent verifier never accepts it.

| Directed base proof, same five-second budget | Original exponential jets | Laurent Horner jets |
|---|---:|---:|
| Valid bases | 15/31 | 31/31 |
| Total proof time | 103.56 s | 52.27 s |
| Median proof time | 5.000 s | 1.774 s |
| Maximum proof time | 5.018 s | 4.112 s |

All analytic controls retain the expected positive/unresolved decisions.
Reusable bounds now carry an exact coefficient hash; mismatched reuse is
refused. This fixes proof provenance independently of evaluation speed.
Horner retains directed arithmetic and whole-domain coverage. Its roughly
twofold total base-proof cost reduction does not establish complete-trial
speedup. The expensive moved/candidate roles have not been timed again.

The important remaining limitation is now exposed: all 26 high-band bases
fail at B3072 on the fixed 1e-8 uniform phase residual bound. Thus 100 final
move failures are recorded as a finer base-construction failure, often
masking an earlier moved-speed residual. This is an approximation/rounding
budget failure, not an invalid-boundary finding. Retaining an existing
success at the original bands does not solve it. Full receipts distinguish
the failed base from each failed moved curve.

The maintained package passes 187 tests in 63.25 s, including both scalar
constructors and wrong-curve certificate reuse. Evidence validation checks
snapshot hashes, 279 unique moves, 31 proof rows, completion, sampling guards
and zero physics calls. The result partially supports the scalar-proposer
hypothesis and supports the interval-evaluation hypothesis. The node-free
engine remains an isolated research instrument. A further study must address
the phase-bound budget and positive-range bootstrap with an explicit
mathematical error criterion; simply weakening a tolerance would not resolve
the recorded mechanism.
