# Start here: modal structure before a solver rewrite

**Package:** BIE-DIAGNOSTICS-20260915-v1  
**Status:** PROPOSED — NOT APPROVED FOR EXECUTION  
**Execution:** NOT STARTED  
**Primary proposed contract:** BIE-002, using the existing reserved prototype ID  
**Owner / independent reviewer:** unassigned / unassigned

## Purpose

Determine whether useful structure actually exists before building a new solver architecture. The primary question is:

> Can Fourier field coordinates or structured mode coupling reduce the cost of accurate boundary-field and shape-sensitivity calculations beyond a properly tuned nodal Kress baseline?

The secondary question, explicitly deferred, is whether a local geometry-dependent operator approximation offers value beyond ordinary tangent predictions or existing-factorization reuse.

This is not an instruction to eliminate all boundary sampling, develop both ideas at once, or rehabilitate the implicit MLP. A negative or inconclusive diagnostic is an acceptable result.

## What is and is not selected

| Work | Disposition |
|---|---|
| Read/profiling design and current-source reconciliation | Required before execution |
| Fixed-geometry modal field reduction and nontrivial-block structure diagnostic | Proposed BIE-002 |
| Use existing supported analytic operator derivatives in that diagnostic | In scope after BIE-002 approval |
| Optional finite-difference/Taylor probes for verification | Validation only; not a proposed gradient backend |
| A new multi-interface derivative implementation | Deferred; existing BIE-004 territory |
| Direct coefficient-only assembly, new singular quadrature, new field basis | Deferred until evidence supports one named successor |
| Local operator-expansion experiments | Separate deferred contract; not released by BIE-002 |
| Inverse integration, topology changes, accuracy-policy changes | Out of scope |

A simple modal reduction can fail while a different structured operator representation remains possible. Record that distinction; neither force a success nor claim to have refuted all spectral BIE methods.

## Read in this order

1. [Scientific decision](01_SCIENTIFIC_DECISION.md).
2. [BIE-002 contract and mathematics](02_BIE002_MODAL_DIAGNOSTIC.md).
3. [Validation, cost accounting and stopping rules](04_VALIDATION_COST_AND_STOP_RULES.md).
4. [Repository handoff](05_REPOSITORY_HANDOFF.md).
5. [Evidence and focused reading](06_READING_AND_EVIDENCE.md).
6. [Codex prompts](07_CODEX_PROMPTS.md).

[Idea 3](03_IDEA3_DEFERRED_DIAGNOSTIC.md) is background for interpreting results, not an instruction to implement it now.

## Placement and workflow

The archive adds this folder:

`docs/iterations/boundary_bie/iteration_01/02_proposals/02_modal_reuse_diagnostic_pack/`

Keep the original `01_boundary_bie_research_brief.md`. Do not overwrite a review or plan that appeared after this packet was prepared. If proposal number 02 is now occupied, use the next available number and repair local links; do not renumber history.

After review, consolidate the agreed BIE-002 contract in iteration 01's `03_plan.md`, with explicit approval and execution statuses. Do not claim BIE-001 was numerically executed: it is the older desk-study selection proposal. Reconcile its disposition explicitly in the handoff.

Only completed diagnostic results open the next cycle. Do not create `iteration_02/01_results.md` before results exist. Experimental artifacts belong under a fresh `results/validation/boundary_bie/` bundle, not inside this proposal packet.

## Execution boundary

Repository rules inspected for this package require named-ID approval and the existing checkout `/home/drdeng/Neural_SDF_BEM_AD` on `feature/ordered-boundary-nystrom`. New branches/worktrees require separate user approval. There must be no simultaneous numerical-code writers in that checkout.

Once the user explicitly approves BIE-002, execute this one bounded diagnostic, preserving production behavior. Do not turn closeout into automatic authorization for an inverse run, BIE-004, idea 3, or another round of algorithm invention.
