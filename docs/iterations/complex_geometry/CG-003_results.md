# CG-003 — 92 directed loops close on two nonreal roots

2026-10-11. **No real minimum returned: 0/92 discovery loops.** The search
exhausted its queue, rather than its time or loop budget. All 46 frozen loop
generators were applied to both discovered roots. Their observed actions
closed on the same nonreal conjugate pair: 90 identities and two swaps.

This is a completed negative test of the selected route family. It does
not establish that all complex paths fail. The instrument remains the
fixed-center TG-002 circle radius family, contrast 13.3 at 1.5 GHz.

## What was implemented and run

The [driver](../../../experiments/benchmark/cg003.py) recomputed the initial
complex root from the sole prescribed q0=1.3,t0=0 start, then performed a
FIFO search over endpoint roots at t=1. Each generator went up a fixed
complex stem, circled one previously detected real critical value, and
retraced the stem. Candidate order used distance to the current radius,
never measured loss or truth. New roots required half-step and reverse
checks before expansion. The [frozen plan](CG-003_plan.md) records the
routes, bounds, qualifications and stopping rules.

The [new continuation helpers](../../../solvers/bem_inverse/complex_paths.py)
also implement the real stationary graph `t(q)=A(q)/B(q)` directly. This
passes a simple fold without Newton correction. Both directions and half
radius steps were tested in the same real-coordinate domain used by the
complex search. No new numerical physics implementation was introduced;
all 207 originally qualified source hashes still matched before the run.

Reproduction uses a fresh output directory; the stored run is never overwritten:

```bash
PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.cg003 run \
  --output results/validation/complex_geometry/CG-003/<fresh-run>
```

For saved numbers only, with no forward evaluations:

```bash
python -m experiments.benchmark.cg003_report
```

## Measured results

| Quantity | Result |
|---|---:|
| Real minima reached at t=1 | **0 / 92 discovery loops** |
| Frozen generators × expanded roots | 46 × 2 |
| Distinct qualified t=1 roots | 2, both nonreal |
| Actions leaving the input root unchanged | 90 |
| Actions exchanging the pair | 2 |
| Largest endpoint distance to its matched root, q units | 2.61e-18 |
| Total arms, including controls and replays | 99, all numerically qualified |
| Stored states, including each arm's start | 93,161 |
| Rejected trial steps | 3,328, all in real controls |
| Maximum stored scaled stationarity | 1.00e-11 |
| Cutoff-refinement checks | 6,578 |
| Maximum field/Hessian cutoff difference | 0 at stored precision |
| Wall time including controls and verification | 153.01 s |
| Production / refinement frequency-radius jets | 413,695 / 12,216 |
| Peak process RSS | 95.35 MiB |

The endpoint radii are

    R_minus = 64.6837849021 - 0.0244289942 i mm,
    R_plus  = 64.6837849021 + 0.0244289942 i mm.

Their imaginary component is about 48,858 times the declared reality
tolerance. The only generator changing either root is centered at
`t=0.649167247036`, the original CG-001 fold. Its new-edge half-step error
is 1.52e-18 q, and reverse error is 2.23e-16 q. The other 45 generators
act as the identity on each of the two observed roots.

The initial real 65 mm radius has measured-data loss 0.7498858693 and
relative field residual 1.224651681 (122.465%). Neither returned root is
a real shape, so a physical endpoint loss or recovery score is not assigned.
No loss improvement is established. Since there was no real candidate,
the success-only full-ancestry/nodal endpoint confirmation was not triggered;
there were zero new nodal solves.

## Stronger real control

| Direction from q0 | Final radius, mm, base / half step | Maximum sampled t, half step | t=1 crossings, base / half |
|---|---:|---:|---:|
| Increasing radius | 65.2774088017 / 65.2774088035 | 0 | 0 / 0 |
| Decreasing radius | 64.6578791375 / 64.6578791383 | 0.649167245979 | 0 / 0 |

All four controls stop at the declared t=−2 boundary. Base/half radius
endpoints agree within 3.59e-11 and 1.68e-11 q, respectively. Final t values
are within 1.84e-6 of −2; their differences reflect the steep graph and
minimum radius increment, so tighter t-endpoint agreement is not claimed.
The decreasing-radius control passes the earlier CG-002 pseudo-arclength
failure at q≈1.293272102, t≈0.003449893. That failure was numerical; the
resolved real branch continues to the registered domain boundary.

This characterizes the sampled start-connected real component in the
declared window. It is not a theorem excluding other real roots, paths
outside that window, or structure missed between samples.

## Interpretation from theory

Let S be the two observed roots. The measured generator table contains
only the identity on S and its transposition. Under this observed action
model, every finite composition still maps S to S: composing permutations
of a two-element set cannot introduce a third element. Thus simply trying
more words made from these measured actions has no mechanism to reach a
real root. This is the finite permutation argument underlying the
[monodromy framework of Duff et al., §2.1](https://arxiv.org/pdf/1609.08722),
applied to our numerical transition table.

The qualification is essential: root matching used tolerance 1e-7, and
neither a global covering nor all critical values was certified. All
generators used the same upper attachment convention and were centered at
known **real** critical values. Complex critical values and different
attachment paths can induce other actions. The evidence supports closing
this route family; a further study would need a materially different
generator construction, not more repetitions of these transitions.
General complex Fourier geometry and benchmark recovery remain untested.

## Validation and evidence

The TG-002 seal check and 24 focused tests passed: 19 analytic continuation
tests plus five package-boundary tests. Mock orchestration checked success
and failure receipt paths before measurement. Independent post-run review
recomputed every real-step resolution guard, every generator's root mapping,
all qualification summaries and all 212 source snapshot hashes. Source
files remained unchanged during the experiment. The read-only report
validator also passed. Refinement agreement at floating-point precision
does not provide an analytic tail or interval certificate.

[Numeric report](../../../results/validation/complex_geometry/CG-003/run-01/report.md)
· [Raw outcome](../../../results/validation/complex_geometry/CG-003/run-01/outcome.json)
· [Validation](../../../results/validation/complex_geometry/CG-003/run-01/validation.json)
· [Source/input manifest](../../../results/validation/complex_geometry/CG-003/run-01/manifest.json)
· [Literature and derivation audit](LITERATURE_THEORY_AUDIT.md)
