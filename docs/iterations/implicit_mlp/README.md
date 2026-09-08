# Implicit-MLP research iterations

Each directory owns a complete consultation and review record. Iteration numbers
identify research cycles; dates and run IDs identify the underlying experiments.

| Iteration | Scope | Recorded state |
|---|---|---|
| [01](iteration_01/README.md) | September 7 failures and repairs; two guides and their reviews; September 8 matched controls and observability | Diagnostic cycle completed; neural recovery unresolved; final assessment recorded |
| [02](iteration_02/README.md) | September 8 wrong-start circle, ellipse and star comparison | Results and possible fixes recorded; ChatGPT guide, discussion and final review pending |

## Structure of every iteration

```text
iteration_NN/
  README.md
  01_results_and_diagnosis.md
  02_possible_fixes.md
  03_implementation_guides/
    01_chatgpt_guide.md
    02_chatgpt_revised_guide.md       # when another version is received
  04_discussion/
    01_codex_review.md
    02_claude_review.md              # when a second review is received
  05_final_review.md
  evidence/                         # supporting written reports and context
```

`01` states the experiment, actual numbers, runtime, failures and interpretation.
`02` separates possible fixes from established causes and supplies the questions
for ChatGPT. `03` preserves the guides received, in version order. `04` records
the discussions, objections and diagnostic replies. `05` consolidates the final
decisions, unresolved points and the handoff to the next experiment. It also
records implementation/validation outcomes when available.

For a consultation, send `01`, `02`, and any relevant local evidence reports.
The reader should not need another iteration or an external plans directory to
understand the case. Include the necessary prior findings in the new iteration;
references are for provenance and deeper verification.

Keep superseded guides and reviews as dated history. Add revisions instead of
silently replacing an earlier recommendation. Pending documents must say they
are pending; a template is not a received ChatGPT response or a completed review.

The next experiment starts a new numbered directory with its own results and
context. Avoid filenames such as `latest.md` or a `current` alias that changes
the meaning of old links.

## Evidence and implementation

All written information needed for the cycle lives in its iteration. The
`evidence/` files collect full supporting reports with their original scope and
source links. Raw JSON/CSV arrays, checkpoints, logs and videos retain their
recorded locations under `results/`; summaries include the important findings
directly, rather than just linking to those artifacts. Existing run commands and
source-hash provenance retain their historical meaning.

The [pipeline page](../../pipelines/implicit_mlp.md) documents implemented
behavior across iterations. It does not own the consultation or decision history.
