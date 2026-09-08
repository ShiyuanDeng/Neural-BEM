# Review of the implicit-MLP repair and implementation guide — 2026-09-08

Reviewed implementation `6496cd367541b404ee396a76acf48c03f383a318` and guide
`127ac89999d65dfff4700bdeb11d55b875d9d0cd`. The pull fast-forwarded to the latter.
Production code, historical result bundles, and the existing notebook edit
were left unchanged.

**Verdict:** keep the repairs and conversion-resolution controls. The longer
runs demonstrate useful progress, but do not establish recovery. The guide's
matched observability study is sensible; its premise that conversion and
finite-backtracking effects have been eliminated from the star termination
is contradicted by a fresh frozen-checkpoint probe.

## New checkpoint evidence

Reloaded the actual local `rerun-20260907/star-bw96/kress_model.pt`, observations,
geometry, fixed regularization samples, and optimizer settings. Recomputed
training loss exactly matches the saved `0.3461879920809253`. The total gradient
norm is `8.643277626394939`; its negative is a data-descent direction. The
weighted Eikonal gradient norm is `0.12139245430732466`, compared with data
gradient norm `8.656829117099724`. The checkpoint is not stationary.

Probed the unchanged production steepest-descent fallback, independently of
Adam moments:

| Backtracks | Maximum weight step | Result |
|---|---:|---|
| 8, last permitted | 3.90625e-6 | Conversion audit rejects: distance 0.112325 mm passes, but refinement change 0.0115825 mm exceeds 0.010 mm |
| 9 | 1.953125e-6 | Passes geometry, both Armijo conditions and boundary-motion limit; loss 0.3460535595880327 |
| 10 | 9.765625e-7 | Passes all acceptance conditions; loss 0.3461205686179813 |
| 12 | 2.44140625e-7 | Passes all acceptance conditions; loss 0.3461710975628153 |

The backtrack-9 candidate has conversion distance `0.10919206879405789 mm`,
boundary movement `0.07075868257211537 mm`, and regularized objective
`0.34709571567702063`, down from `0.34722994933010864`.

This disproves the assertion that the final accepted state's 0.1061 mm distance
means the guard cannot be binding on the next trials. The guard has two
conditions, and candidates must satisfy both. It also demonstrates that the
configured backtracking budget still terminates a nonstationary star with an
available acceptable fallback step. The earlier small-gradient repair remains
valid; it never guaranteed that eight halvings suffice for every gradient and
geometry. These selected probes do not replay all 18 rejected terminal trials
or Adam's historical moments, and do not demonstrate eventual recovery.

Evidence: [probe metrics](checkpoint_probe.json), [script](checkpoint_probe.py),
[configuration, hashes and tests](provenance.json).

To reproduce without replacing this bundle:

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONPATH=solvers \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python \
  results/validation/implicit_mlp_adjoint/review-20260908/checkpoint_probe.py \
  /tmp/implicit_verdict_recheck.json
```

The historical checkpoint and response archive must exist locally; they are
ignored binary artifacts. The script never saves modified network weights.

## Assessment of the longer runs

- Circle bandwidth 20 reaches 60 accepted updates, training relative L2
  0.001795 and holdout 0.07053, with about 1.122 mm maximum node-to-target error.
  This is substantial improvement over the guarded bandwidth-10 run, but the
  recovery gates still fail. A training/holdout gap alone does not establish
  that further iterations cannot improve holdout.
- Star bandwidth 96 remains poor: training relative L2 0.5966, holdout 1.078,
  maximum node-to-target error 36.386 mm, and worse fitted lobe amplitude and
  phase. Increasing bandwidth alone has not fixed recovery.
- The frozen conversion comparisons support bandwidth as the dominant error
  lever on those checkpoints. They do not establish that every candidate is
  resolved, nor isolate every source of termination.
- The historical five-parameter star already succeeds at 0.5/1.5 GHz with 12
  pairs. The new neural run uses eight pairs. Thus those frequencies are not
  categorically incapable of recovering the lobes, and angular acquisition
  deserves a matched control alongside frequency.

## Companion review

The arguments now follow the implementation guide section by section in
[the companion review](../../../../docs/iterations/implicit_mlp/iteration_01/02_proposals/02_codex_review.md).
It maps the termination correction, observability requirements, matched
acquisition controls, holdout discipline and conditional optimizer changes to
Phases 1–5. This bundle retains the underlying checkpoint evidence.

Validation during this review: **45 focused inverse/adjoint/repair tests
passed**, and `git diff --check` passed. No full new inverse or guide phase was
implemented as part of this verdict.
