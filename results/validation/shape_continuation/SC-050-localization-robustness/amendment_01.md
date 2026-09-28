# Pre-localization domain amendment — 2026-09-28 03:02 UTC

Both original localization attempts aborted at the first grid circle
(0.28,0.28), radius 0.025 m, because a receiver lay inside it. No candidate
loss, location ranking, localized shape fit, or transfer result was obtained.
This is a search-harness domain omission, not evidence against localization.
The two failed attempts and the preliminary selection without localization
are retained under `pre_amendment/`; their original source archive is unchanged.

The corrected harness checks that every known source and receiver is exterior
to each candidate circle (analytic distance, 32 eps clearance). Inadmissible
circles are logged and assigned infinite search cost without a physical solve.
Numerically unqualified or refused forward evaluations are also logged and
excluded; no unqualified candidate can initialize reconstruction. The grid,
radii, frequencies, 12 refinement rounds, per-attempt budgets, success criteria,
and selection rule do not change. This is not a target-informed exclusion.

Only the two setup-aborted localization attempts are repeated. The other four
completed development controls are reused with their exact original receipts:
the amendment changes localization and source-chain verification only.
The preliminary selection is superseded before any transfer fitting.
There are now 20 recorded attempts including two setup failures, with at most
18 complete planned fits; add 2*(114 audit + 3 dispatched failed forward)
=234 physical units for the setup failures. Failed-batch work was omitted from
the initial exception summary, so this conservative reconstruction from the
three-frequency eager dispatch is stated separately. Corrected localization
charges batches before execution and records attempted units even on refusal.

Original manifests remain the first source version; an explicit amendment
entry records the new source archive and hashes. Original numerical outputs
are not overwritten. No core forward solver or optimization code is changed.
