# CI-SPD — GauGal speed and the cleaned BEM comparison

Opened 2026-10-05 at the user's request.

For parallel execution, see the [two-agent launch guide and ETAs](../OVERNIGHT_AGENT_TRACKS.md):
Agent 1 runs ON-001; Agent 2 runs ON-003. Sending the named launch command
authorizes that bounded plan; the guide itself starts no experiment.

CI-SPD is a standalone track under `docs/iterations/CI-SPD/`. Its comparison
and proposed follow-up plans live here; recorded evidence remains under `results/`.

**Agreed schedule (2026-10-05):** [continuation schedule](CONTINUATION_SCHEDULE.md)
records translation/scaling initialization, the unchanged existing frequency
ladder including its M/K progression, four additional all-frequency M/K
stages, and full configured release. This is a documented design; the
default policy remains unchanged. The opt-in [CS-001 implementation](CS-001_preparation.md)
is prepared and bounded checks pass; paired TG-002 fitting awaits specific
ID approval. Its initial-stage evidence is
in [GGB-004](GGB-004_results.md) and [GGB-005](GGB-005_results.md).

**Question:** Why is the released GauGal cylinder reconstruction fast, and
which measured costs explain its difference from our current cleaned modal
BEM implementation?

**ON-003 closed (2026-10-05):**
[the Ewald feasibility report](iteration_01/05_ON003_results.md) records
**ACCURACY_OR_RESOURCE_LIMITED**, a negative circle control at the registered
Fourier-grid ceiling. Full-field and derivative coverage remain explicitly
unrun; no inverse integration is qualified. Agent 2 supplied its final handoff.

**ON-001 closed, useful partial result:** [inverse results](../cleaned_interfaces/iteration_31/01_results.md)
confirm all 30 matched TG-002 pairs, B/E 26/30 with no additions/regressions;
median paired audited-output speedup 1.546x, p10 1.225x. E is retained as an
opt-in control. G/W closed screen-negative and F failed finite-trial qualification.
This is not a GauGal-parity claim; ON-002 remains independently owned.

**Outside review (2026-10-05):** [ON-001/002/003 review](../cleaned_interfaces/iteration_31/02_claude_review.md).
ON-003's circle errors track the Ewald truncation term exp(-tau q_max^2); only xi >= k* was
registered, which could not pass at the 256 grid. ON-002 was interrupted at 01:48 UTC with 0/12
adapter configurations converged. Its record was preserved unchanged in `7d50e3f8`.

**ON-002 resumed and closed (2026-10-05):** [resumed adapter results](iteration_02/02_resume_results.md)
record **ADAPTER_INCOMPLETE** after scale normalization and the declared
complex128 fallback: 0/25 resumed solve gates passed, including the 256-grid
weak control. No inverse, hybrid or timing-parity comparison was released.

**Proposed, awaiting approval (2026-10-05):** [GP-001](iteration_02/03_plan.md) remains
unrun: its amended adapter repair ladder, feasibility and parity contract is separate.
**EW-001 closed:** [smaller splits still fail; 46–48x contraction cost lower bound](iteration_03/05_results.md) corrects the Gaussian-tail pass prediction and closes the registered 2D line.

Read [the detailed comparison and explanation](01_results.md). It documents
the completed, approved GGB-001 pilot and the actual source paths used by its
two arms. The [evidence index](../../../results/validation/cleaned_interfaces/CI-SPD/README.md)
contains a compact aggregation and the comparison image; original run receipts,
arrays, failures, and source hashes remain in Gau-Gal's GGB-001 archive.

The completed GGB-001 comparison records evidence and implementation costs.
Related notes now include the
[GPU spline baseline proposal](GPU_SPLINE_FAIR_BASELINE.md)
and [verified modal runtime and geometry-check proposal](MODAL_RUNTIME_GEOMETRY_CHECK.md).
These are unimplemented proposals derived from existing evidence; no new
experiment was run. Their future qualification requires a pre-registered ID
and explicit user approval under the repository workflow.

**Overnight options, 2026-10-05:** the user requested an ambitious research
brief with conditional next steps. The [big-picture brief](../cleaned_interfaces/iteration_30/02_proposals/01_overnight_research_brief.md)
recommends [ON-001](../cleaned_interfaces/iteration_30/03_plan.md), an adaptive
BEM speed/recovery campaign with reach clipping and a conditional Gaussian map.
[ON-002](iteration_01/03_plan.md) is the alternative matched TG-002 GauGal
comparison and conditional hybrid. [ON-003](iteration_01/04_ON003_ewald_plan.md)
is separate Ewald-style Müller forward feasibility. The
[seven-idea integration review](../cleaned_interfaces/iteration_30/02_proposals/02_gaugal_restructuring_integration.md)
records the supplied report's mathematical corrections and the remaining roadmap.
The brief itself provided no launch authorization. Direct named launches later
approved ON-001 and ON-003; their actual evidence/status is linked above.
ON-002 remains independently owned with its own explicit launch and report.
