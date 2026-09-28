# SPD-014 review diagnostics (Claude, 2026-09-28)

These are independent checks behind the [review](../../../../docs/iterations/speedup/iteration_11/02_claude_review.md). The review found one latent defect: the exact-count claim fails below the round-off tolerance (R1). It did not modify SPD-014's code or evidence bundle.

| File | What it shows |
|---|---|
| [fuzz.py](fuzz.py) → [fuzz.json](fuzz.json) | 261 polygons × relative tolerances {0, 1e-12, 1e-6} = 783 reference-vs-spatial count comparisons. 757 have non-zero counts, and 310 of those used the pruned path. **2 mismatches, both at tolerance 0** (star polygons with subdivided straight edges). All 522 comparisons at non-zero tolerance agree |
| [guard_check.py](guard_check.py) → [guard_check.json](guard_check.json) | The proposed guard: dense fallback unless `cross_tolerance ≥ 8·eps·L_max·D`. It is applied to the same 783 comparisons without editing the solver: **all equal**. The guard fires only on the 261 zero-tolerance cases |

Reproduce from the repository root. The first line `guard_check.py` prints comes from re-generating the fuzz cases, and can be ignored.

```bash
PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$PY results/validation/speedup/SPD-014-review-20260928/fuzz.py /tmp/fuzz.json
$PY results/validation/speedup/SPD-014-review-20260928/guard_check.py /tmp/guard.json
```

The review also re-ran:

- **Frozen-manifest check:** `experiments.spd014_geometry.run.verify` on the SPD-014 bundle passes.
- **Tests:** 370 pass.
- **Headline numbers:** SPD-014's timings and pass flags, recomputed from its raw `geometry/`, `batches/`, `inverse/` and `video/` result files, match its closeout.
