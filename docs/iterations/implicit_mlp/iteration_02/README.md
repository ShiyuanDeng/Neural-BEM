# Iteration 02 — repaired wrong-start comparison

Date: 2026-09-08. **Results and possible fixes recorded; ChatGPT guide,
discussion and final review pending.**

The 12-pair repaired suite completes circle and star but fails recovery for
both. Circle ends at 1.069 mm boundary error, similar to its 1.038 mm baseline.
Star worsens from 26.833 to 37.368 mm, with collapsed lobe amplitude and a
conversion-refinement/search stop. Ellipse-to-circle exits before saving a
result bundle. The two completed inverses consume about 128 minutes of recorded
inverse time. These outcomes motivate the consultation in this folder.

| Stage | Document | State |
|---|---|---|
| 1 | [Results and diagnosis](01_results_and_diagnosis.md) | Full numerical comparison, runtime and failure evidence |
| 2 | [Possible fixes](02_possible_fixes.md) | Ranked pre-consultation options; not a received ChatGPT guide |
| 3 | [ChatGPT implementation guide](03_implementation_guides/01_chatgpt_guide.md) | Pending; contains the consultation prompt |
| 4 | [Codex discussion/review](04_discussion/01_codex_review.md) | Pending receipt of the guide |
| 5 | [Final review](05_final_review.md) | Pending consolidation of decisions and validation |

## Local context for consultation

- [Prior matched controls and observability](evidence/01_prior_controls_and_observability.md): full report, including physical/modal results and scaling caveats.
- [Frozen ellipse initialization audit](evidence/02_ellipse_initialization_audit.md): full report of the separate diagnostic and its limits.

Send the results, possible fixes and relevant local evidence to ChatGPT with
the prompt in the guide file. Save its actual response there with a date; use
numbered guide versions and discussion files for further exchanges. Finish by
consolidating the decisions in `05_final_review.md`. The complete written
context is here; another iteration is not required to understand the handoff.

## Run provenance

```bash
/home/drdeng/miniconda3/envs/EMNerf/bin/python run_implicit_mlp_wrong_start_suite.py \
  --output-root results/inverse/implicit_mlp/2026-09-08
```

This is the completed suite's command, not a request to rerun it. The
[suite manifest](../../../../results/inverse/implicit_mlp/2026-09-08/wrong_start_suite.json)
contains the exact per-case commands. The results report links the JSON,
trials and videos that substantiate its inline measurements.
