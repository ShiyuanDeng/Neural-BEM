# TOP-001 review — 2026-09-11

The best-one-per-(event kind, component count) refinement rule is still present
in the B0 source. **Accept TOP-001 with the amendments below.** The user's
2026-09-11 request to take Track A as far as possible authorizes implementation
and bounded experiments in this session; it supersedes the older requirement
to ask again using an exact experiment-ID phrase. This is not an independent
review: Codex owns both this review and the implementation. Independent reviewer:
unassigned.

1. **Accept the allocation experiment.** Preserve A (one candidate, three LM
   iterations), compare B (two, three each) and C (two, one each). An LM call
   constructs an initial Jacobian and another after every accepted step; for
   equal dimensions, two one-step calls therefore have the same nominal FD
   evaluation cost as one three-step call. Backtracking, early termination and
   differing candidate dimensions can break that equality. Report measured
   costs and never label an over-budget C result compute-matched.
2. **Amend the historical controls.** The radial reference manifest actually
   records `maximum_candidates_per_type=12`; Cartesian records 48. First
   reproduce each recorded event with its own manifest. Then run the comparison
   with cap 48 in both charts, explicitly recording this difference from the
   historical radial run. The original brief's assertion that both used 48 is
   incorrect. Saved pre-event states also differ between charts, so comparisons
   are paired *within* each chart, not a pure chart-effect experiment.
3. **Accept replay, with a precise entry point.** Bypass only the first fixed
   optimization on the saved `before split` frame. Keep later fixed optimizations,
   topology passes and acceptance unchanged. Recomputing the initial optimizer
   would silently move the frozen state and invalidate the replay.
4. **Accept instrumentation.** Count uncached objective evaluations and completed
   forward evaluations separately; TD field calls and their frequency solves
   are separate. Include production, refinement, TD, acceptance and final audit
   stages. Failed geometry and cache hits must not become completed BIE solves.
5. **Amend qualification.** Add evaluation-only 1.5/2.5-GHz independent cylinder
   holdout observations, never used to optimize or select candidates. Geometry
   uses symmetric nearest-boundary distances at 512 samples per component,
   reporting sampled Hausdorff and RMS distance divided by truth radius.
6. **Amend rejection taxonomy.** Eligible losers are `eligible_not_selected`,
   not geometry/objective failures. Unrecognized errors remain `unclassified`
   with their original strings; audit that bucket before closeout. A failed
   polish that falls back to its raw candidate is a diagnostic, not an event
   rejection.
7. **Defer TOP-002** (trigger changes) until allocation costs are measured.
   **Defer TOP-003** (candidate construction) to the next cycle if raw ranking
   remains unstable or the useful coarse family lies outside the top two.
   **Defer TOP-004** (acceptance/stopping changes) to avoid confounding this
   experiment; truth geometry may only qualify results, never accept an event.
   **Defer 3DGS-inspired policies** until a specific mechanism and comparison
   contract exist. No external literature claim is needed for this experiment.

Shared changes declared before implementation: optional allocation and frozen
replay controls plus work reporting in `topology_controller.py`; metrics and
source provenance in `run_fourier_topology_controller.py`; passive accounting
hooks in `radial_topology.py`. Geometry state, physical objective, candidate
generator, optimizer mathematics and BIE solver interfaces remain fixed.
