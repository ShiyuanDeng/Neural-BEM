# Iteration 01 — failure analysis, repairs and acquisition controls

Scope: September 7–8, 2026. **Completed diagnostic cycle; general neural recovery
remains unresolved.** This folder contains the original guides and discussions,
the measured context that motivated them, and the final assessment after the
matched controls. The numbering was assigned retrospectively; reconstructed
summaries are identified as such.

The initial three 12-pair neural inverses all failed recovery. Targeted repairs
improved star pretraining, removed a demonstrated circle fallback limitation,
and exposed conversion errors. Subsequent higher-resolution runs still failed
recovery. The guide/review cycle then tested whether acquisition information
was missing: the five-parameter star recovered with eight pairs and the original
band, while the tested 21-mode two-frequency Jacobian had full rank. Multistatic
readout improved conditioning; neither result established full-MLP recovery.

| Read order | Document | Role |
|---|---|---|
| 1 | [Results and diagnosis](01_results_and_diagnosis.md) | Numerical context for the consultation |
| 2 | [Possible fixes](02_possible_fixes.md) | Evidence-ranked options and alternatives |
| 3 | [Initial ChatGPT guide](03_implementation_guides/01_chatgpt_guide.md) | Original five-phase proposal, retained with its historical claims |
| 4 | [Codex review](04_discussion/01_codex_review.md) and [Claude review](04_discussion/02_claude_review.md) | Corrections to stopping diagnosis, acquisition and experimental ordering |
| 5 | [Revised ChatGPT guide](03_implementation_guides/02_chatgpt_revised_guide.md) | A–H sequence incorporating the reviews |
| 6 | [Final review](05_final_review.md) | Measured A–E outcomes, decisions and remaining limits |

## Complete supporting reports

- [Failure audit](evidence/01_failure_audit.md): fallback, pretraining and raw/converted geometry.
- [Validated repairs](evidence/02_validated_repairs.md): adopted changes and rejected prototypes.
- [Full repair reruns](evidence/03_repair_reruns.md): circle/star bandwidth comparisons.
- [Checkpoint review](evidence/04_checkpoint_review.md): the additional acceptable star fallback.
- [Controls and observability](evidence/05_controls_and_observability.md): full A–E results, spectra, validation and costs.

These are full written reports collected locally, with links to their original
run artifacts. The [next iteration](../iteration_02/README.md) records the later
12-pair wrong-start suite and begins a separate consultation.
