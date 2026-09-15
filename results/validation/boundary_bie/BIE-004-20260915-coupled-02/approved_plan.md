# BIE-004 — bounded multi-interface analytic derivative

- Approval: **APPROVED**, user's 2026-09-15 instruction to continue BIE after
  explicitly discussing concurrent BIE-004 and topology work.
- Execution: **IN PROGRESS**.
- Owner/reviewer: Codex / self-review; independent reviewer unassigned.
- Working branch: existing `feature/ordered-boundary-nystrom`; no new checkout.
- Production numerical files are read-only. New experiment implementation,
  tests, artifacts and BIE-only documentation are the write scope.

## Fixed scientific contract

Differentiate `A U=B`, `Y=C U` for the actual coupled Kress system:
`A dU=dB-dA U`, `dY=dC U+C dU`. Reuse one LU for all source and directional
batches at each base frequency. All source quadrature weights are already in
A and C. Keep the direct unsquared system and production ordering/signs.

Only shape directions are supported here: fixed source positions/strengths,
receivers, materials, frequency, native grids, periods, component identities,
topology and kernel branches. No material/source derivatives or optimizer
integration. Reuse existing self-operator derivative routines unchanged; add
smooth directed cross-block differentiation in experiment-local code. Count
skipped unchanged self/cross blocks and all recomputation explicitly.

## Frozen stages

1. **Wiring and operator validation.** Algebra/geometry unit tests plus a
   single-interface reduction control against the existing analytic routine.
   Two-component circle/noncircular fixtures with unequal node counts and native
   periods; individual and common translations, and a shape direction. Check
   dA/dB/dC and paired dY against central differences at 1e-5 and 5e-6 physical
   amplitudes. Preserve all four trace interactions and both directed cross
   interactions. Common translation must leave A invariant to roundoff while
   individual translation changes its cross blocks.
2. **Saved-state fixed-topology qualification.** Two coefficient-exact K=9
   Cartesian states: TOP-018 COMMON and TOP-022's terminal state frozen in
   TOP-023 `inputs.json`. Reuse TOP-018's 24-pair acquisition, exterior epsr=6,
   interior epsr=3 and 1e-6 source strength. Use only 0.5 and 1.25 GHz development
   frequencies. Base nodes=256, refined nodes=512 per component; geometry
   validation resolution=1024, original clearance=0.010 m and radius floor=.008 m.
   No fitting, inversion or new geometry choice.
3. **Full Jacobian.** At 1.25 GHz and 256 nodes, compute all 34 gauge-coordinate
   columns for both states. Compare with gauge-retracted central FD at 1e-5;
   also record the optimizer's existing 1e-4 step on the selected columns.
   The basis is fixed, exactly the production orthonormal coefficient basis;
   record per-direction RMS and maximum physical displacement. The residual
   map is the production `normalized_complex_residual` with fixed TOP-018
   training observations for COMMON and TOP-023 training observations for the
   terminal state, selecting the declared frequency columns and unit weights.
4. **Refinement/Taylor.** For both scenes, use first-component translation,
   last basis row (second component high mode), and a seed-20260915 mixed
   direction. Check at both frequencies and both resolutions. Compare analytic
   dY to FD at 1e-5/5e-6. At 1.25 GHz the mixed-direction Taylor amplitudes are
   1e-4, 5e-5, 2.5e-5 and 1.25e-5 metres of coefficient step. The same retraction
   path is used throughout. At most this one declared refinement ladder.
5. **Cost comparison, only after accuracy passes.** Three paired fresh builds
   of the terminal-state full Jacobian at 1.25 GHz/256 nodes, analytic versus
   gauge-retracted central FD at 1e-5. Alternate arm order; discovery provides
   common warm-up. Include geometry/retraction, assembly, primal and derivative
   work, LU, tangent solves, receiver evaluation and primal consistency checks.
   Record total measured wall time, component timings, RSS and counters. Run
   each pair without another numerical benchmark; defer timing if another
   numerical job is active. Diagnostic-only operation counts remain valid.

## Predeclared gates

- Analytic primal reassembly agrees with stored A/B/C to relative 2e-11.
- Scaled blockwise operator FD errors <=1e-4; zero derivative blocks use an
  absolute roundoff bound scaled by the base operator and FD amplitude.
- Paired directional-data error <=1e-4 against the finer FD probe, with
  a fixed source-scale floor `1e-12*norm(paired incident)/ell`.
- Full residual Jacobian relative Frobenius and worst observable column error
  <=1e-4 against the 1e-5 central FD matrix. This is a sampled numerical check,
  not an exact certificate from finite differences.
- Forward reference discrepancy <=2e-7; sampled analytic sensitivity refinement
  discrepancy <=2e-5. Same tiers as BIE-002, not readiness for every inverse tolerance.
- Saved gauge/retraction displacement error <=1e-10 m per declared probe;
  failure blocks claims about the optimizer's coordinates. Radius and clearance
  feasibility refusals remain explicit, never zero derivatives.
- Taylor ratios approach 4 under halving; require at least two successive ratios
  in [3.5,4.5], above the reference/roundoff floor.
- Operational promotion screen: >=1.3x median setup-inclusive full-Jacobian
  speedup with nonoverlapping three-pair ranges, no accuracy loss and fewer
  factorizations. A slower implementation closes negative or cost-inconclusive.

## Hard global budget and stopping

Maximum **800 full-system assembly equivalents**, conservatively charging one
for every analytic directional recomputation (actual self/cross work separately
reported); **300 directional-operator calls**, **600 factorizations**, **1000
RHS batches**, **1800 seconds numerical execution**, **8 GiB peak RSS** with
planned live arrays below 4 GiB. All physical tests and timing repeats count.
Reserve before operations, checkpoint after stages. Stream derivatives; do not
cache 34 dense dA matrices. Documentation time and waiting for topology's timing
window do not replenish numerical budgets. Record attempts, failures and reuse.

At most one bounded implementation correction after a wiring failure; preserve
the original evidence and rerun affected controls only. Do not expand the
algorithm, cases, tolerances or ladder to rescue a scientific failure. Stop a
dependent stage on failed gates, source drift, feasibility or budget. No shared
production edits, inverse or successor are automatically released.

## Closeout

Fresh `results/validation/boundary_bie/BIE-004-*` bundle: frozen plan/inputs,
source/environment manifest, work ledger, operator/JVP/Jacobian/refinement/Taylor
and timing metrics, commands, tests, failures and short verdict. Results open
iteration 03 only after measurements exist. Recommend one concrete next action
from the evidence; implementation is not a recovery claim.
