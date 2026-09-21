# Modal compression: start here

**CLOSED by user direction, 2026-09-21, at iteration 02.** MC-001 Stage A is
complete. Its continuation gate failed; Stage B did not run. No successor,
sparse implementation, crossover benchmark or inverse pilot is scheduled.

This is the main entry point for the compression work across Modal compression,
Laurent and the earlier Boundary–BIE exploration. Original experiment IDs,
plans, code, PDFs and result bundles remain in their original locations.

## Read in this order

1. [Closure decision](CLOSEOUT.md): why we stopped, what was established,
   and what remains untested.
2. [Compression evidence index](evidence_index.md): the experiment-by-experiment
   map to original results and implementations, including the Laurent work.
3. [MC-001 results](iteration_02/01_results.md) and
   [visual gallery](../../../results/validation/modal_compression/MC-001-20260921-entry-screen-01/gallery.html):
   direct forward/derivative inspection, re-solves and failure modes.
4. [Outsider evidence review](iteration_01/02_proposals/01_outsider_evidence_review.md):
   corrections and limits of the historical numerical claims.
5. [Reference map](iteration_01/02_proposals/03_reference_map.md): primary-source
   checks on the newer theoretical report and its proposed extensions.

## What this archive owns

The question is whether modal compression offers useful accuracy control,
storage, physical sensitivities or repeated-work savings for this inverse
problem. This track owns the cross-track synthesis, September 21 review,
MC-001 and final compression decision. [Laurent](../laurent/README.md) retains
its broader coefficient-space pipeline and historical LAU experiment records.
Its separate closure at iteration 07 on September 18 remains unchanged.

There is real modal structure and some accurate compressed models. There is
no demonstrated complete-inverse speedup from modal-entry compression on the
current small 2D workload. Adjoint/Hadamard evaluation can avoid constructing
every derivative matrix; the failed common-mask gate is not a theorem that
gradients make compression impossible. The [closeout](CLOSEOUT.md) preserves
this distinction from the practical decision to stop.

The [executed plan](iteration_01/03_plan.md) and
[earlier proposal](iteration_01/02_proposals/02_next_tests.md) remain historical
records. Their suggestions, and those at the end of the results, are not a
pending work queue after closure. Reopening requires new user direction and
a concrete experiment contract. Owner: Codex; independent reviewer: unassigned.
