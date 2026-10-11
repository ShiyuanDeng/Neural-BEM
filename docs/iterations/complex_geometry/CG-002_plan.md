# CG-002 — does a fixed complex detour return to measured-data stationarity?

2026-10-11. Pre-registered before execution, following completed/pushed CG-001.
User's Track 12 research authorization covers this focused extension. The
independent scientific reviewer checked the endpoint contract, path family,
real-control exposure and interpretation. Root remains implementation owner.

**Question.** Can a finite complex data-homotopy path carry the prescribed
centered start to a real minimum of the actual measured-data objective at t=1?
CG-001 proved local sheet exchange, but its real endpoints were at t<1 and
the sampled real attachment to another fold left the declared t domain.

Use exactly the already selected development instrument: TG-002 circle,
contrast 13.3, real 1.5 GHz, fixed-center complex radius q, q0=1.3 (65 mm).
This is a radius-family component study with deliberate center mismatch,
not a TG-002 recovery comparison. No truth, added observations, grid-search
initializer or alternate starting shape is allowed.

## Frozen arms and interpretation

- Natural real parameter path [0,1], max step .004.
- Real pseudo-arclength in both initial directions, starting from the same
  q0,t0; ds=.0002 and 20,000 accepted steps each (arc allowance 4.0),
  t restricted to [-2,3]. This is enough arc length to expose the first fold,
  unlike CG-001's original short control. Every t=1 crossing is detected;
  correct to t=1 from its already tracked bracket, never an unrelated root.
  Domain or budget exhaustion is a tested-resource limit, not nonexistence.
- Complex doglegs [0, i*eta, 1+i*eta, 1] for eta=.001,.01,.1 and their negative
  conjugates. Positive eta arms are the three development routes; negatives
  are symmetry controls, not three independent discoveries.
- Repeat the three positive arms at half maximum step (.002). This gives
  12 arms in total. No adaptive choice of height, root or winning loss.

Use the unchanged qualified complex-radius model, mirror system, full Newton
derivatives and path guards. Require t=1, |Im(q)|<=1e-8, scaled |F|<=1e-8,
finite valid real disk geometry, and Fq>1e-6 agreeing in sign under cutoff+12.
Stationary maxima and complex endpoints are reported separately. Do not discard
Im(q), polish from its real part, or select an endpoint by truth or data loss.

Refine every complex-path accepted state, and 65 regularly spaced real-control
states plus its endpoint/minimum-pole-margin state. Check field error<=1e-8,
scaled stationarity<=1e-8 and endpoint agreement under half steps<=1e-7.
Any real t=1 endpoint also receives independent N512/N1024 nodal field checks
against the exact disk to 1e-8. Numerical qualification is separate from
whether a path returns real. Charge all setup, failed steps, checks and arms.

Hypothesis: at least one fixed dogleg returns to a real radius-family minimum
at t=1. A contrary result for all three qualified routes refutes this bounded
route family, not complex-geometry continuation. The reviewer's alternative
prediction is that all positive heights preserve the same winding and end
on one nonreal sheet, while negatives reach its conjugate. Agreement across
heights supports that explanation but is not a global monodromy proof.

One CPU process, one BLAS thread, five-minute measured wall budget. Preserve
raw paths (compressed JSON), all endpoint classifications, failed states,
source/input hashes, counters and actual wall time. Do not rerun the full
CG-001 physics qualification if all qualified numerical hashes match.
The script is `experiments/benchmark/cg002.py`; it imports the isolated
instrument and leaves numerical code unchanged. Validate, commit/push and
verify remote/current status after this run, including any negative outcome.

Close on completion of these arms. A higher-dimensional geometry experiment
or a search over winding sequences is a distinct future question.
