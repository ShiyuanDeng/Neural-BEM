# Topology iteration 02 — allocation results

Opened 2026-09-11 by the completed TOP-001 experiment and its declared
exploratory/qualification extensions. [Measured report](../../../../results/validation/topology/TOP-001-20260911-comparison/report.md).

The 60-run A/B/C comparison does not justify raw top-two refinement. It misses
the third-ranked circular seed in the Cartesian split and spends more total
work. The 20-run E follow-up (three × one) makes every Cartesian split replay
accurate to below 30 nm, at 4,696 summed BIE solves versus A's 6,567, but raises
radial costs. On five full Cartesian controller cases, E fails the death
training comparison and raises summed work 4,655→4,766. It remains opt-in.

The historical radial reference did not reproduce at B0; the experiment stopped
and diagnosed that failure, then qualified new, unmodified `345038a` references.
This is an additional provenance limitation of the original research brief.
All final comparisons use paired data/states and source hashes; 527 inverse
tests pass, and an independent actual-solve observer agrees with the ledger.

Next question: can the shortlist retain the baseline winner while adding the
lowest-dimensional candidate only when that winner is more complex? This is
an allocation mechanism. It does not require changing construction, triggers,
acceptance, the physical solver, or geometry representation. TOP-002–TOP-004
remain deferred; the proposed selective follow-up receives a separate contract.
