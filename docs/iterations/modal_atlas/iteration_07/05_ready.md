# MA-007: ready for the 18 research cases

**Executed 2026-10-13:** all 18 configurations returned and were pushed;
8 recovered. See [the three-question answers](06_research18_results.md).
The readiness text below records the queue before the user's launch instruction.

The runs answer three questions: what useful limits can be established for
F/M/K/Ku, what causes those limits, and which sequence works on this scene?

The user closed Phase A on 2026-10-13. Retain the existing baseline strategy and
its 114-cell response atlas in `phaseA-atlas-003`. Do not run further Phase A
experiments or repeat the baseline. Earlier attempts and failed checks stay
preserved. This closure follows the user's instruction; it does not relabel
unfinished work as successful.

The next launch contains these 18 nominal research configurations, all on the
same sealed `hook__c13.3` scene and centered 65 mm start:

| Order | Configuration | F / M / K / Ku caps |
|---:|---|---|
| 1 | G | 2.5 / 95 / 192 / 192 |
| 2 | F0 | 1.0 / 95 / 192 / 192 |
| 3 | M0 | 2.5 / 19 / 192 / 192 |
| 4 | K0 | 2.5 / 95 / 32 / 192 |
| 5 | U0 | 2.5 / 95 / 192 / 64 |
| 6 | F1 | 1.5 / 95 / 192 / 192 |
| 7 | M1 | 2.5 / 37 / 192 / 192 |
| 8 | K1 | 2.5 / 95 / 64 / 192 |
| 9 | U1 | 2.5 / 95 / 192 / 128 |
| 10 | G_E0 | G caps; historical rung exits |
| 11–18 | O1–O8 | C* determined by the frozen plan's rule from returned cap results |

The executable queue is `results/validation/modal_atlas/MA-007/research18-001/`.
Its manifest contains source/input hashes, the source archive, resolved schedule
previews, budgets, environment, and the baseline references. No research case
has started. `state.json` is `READY_AWAITING_GO` with launch authorization false.

O8 ends each decision slot at the saved winning branch endpoint. Lambda resets
to the existing default at each new slot. All branches and full-real monitor
calls count toward its work allowance; an incomplete contest cannot select a
winner. Every case uses the existing optimizer and CUDA geometry factory.

After the user says **go**, launch from this checkout with:

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m experiments.benchmark.ma007_matrix run --go
```

The runner saves every returned result, including failures, and commits/pushes
each case before proceeding. It does not select a truth-error iterate or promote
a repository default. The baseline is reused. Raw arrays remain on this machine;
new chunks use the verified local DATA volume with evidence-root links.

The 18 returned fits do not themselves establish every mechanism or ceiling.
Analyze their saved evidence and retain explicit limitations. Conditional work
in the frozen plan is not a research decision made by this readiness step.
