# FM-003 execution details

The ZIP was opened on `feature/shape-frequency-continuation` at `6a2c3731`.
No branch or worktree was created. Its proposal, plan, reference JSON and lifting
script were extracted without modification. Phase L passed its registered gates;
its source and input seal are separate from the subsequent census seal.

The census implementation is `experiments/cleaned_interface/fm003.py`. It calls
`bem_inverse` directly. No maintained solver, production default, or previous
experiment implementation is changed. Execution uses the existing EMNerf Python,
one worker, four frequency threads, `device=auto`, N512/1024, and single-threaded
BLAS. Phase 0 also repeats converged start 0 with one frequency thread and requires
identical coefficients, loss, stop, accepted-step count and charged work.

The following implementation details resolve unspecified mechanical conventions
before any census result is seen:

- Draw the six alpha values, then six beta values, then the rotation when required.
  Beta at order zero is drawn and retained but multiplies the identically zero sine.
- The initial draw uses scalar seed `20261004+i`. Up to ten redraws use NumPy's
  sequence seed `[20261004+i, attempt]`, with attempt 1 through 10.
- Pad z1 to K12 before preparing the existing projected trial map. Convert sigma
  from package units to metres for the map's coefficient API. Rotate the displaced
  curve around its own area centroid, evaluated by the periodic line integral.
- Validate the same curve and domain conditions as the optimizer. Retain every
  rejected draw, including its seed, coefficients and reason.
- Relative loss agreement is symmetric: absolute difference at most 2% of the
  larger loss. Single linkage uses a strict distance below 0.5 mm. The FM-001
  arclength distance is evaluated with cached projections and the equivalent FFT
  form of its 2048-point phase search, checked against FM-001 directly.
- Stage 0 of Phase 1 reuses the converged Phase 0 start, with a hash pointing to it.
  Subsequent starts execute sequentially. A timed-out partial start is retained
  outside the completed prefix and is not silently treated as converged.
- Winner selection uses finite endpoint losses, ties by index, before loading
  truth. Failed starts remain in the census denominator and are reported separately.
- Phase 2 executes the exact suffix from stage 3 onward. Its global fitting budget
  is 13,250 units and 1,784.5 seconds; the separate phase deadline is 900 seconds.
  Initial/final numerical audits are retained. Census work is reported separately.

Commands, in frozen order, with `PYTHONPATH=solvers:.` and
`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`:

```bash
python -m experiments.cleaned_interface.fm003_lift
python -m experiments.cleaned_interface.fm003 lift-gates
python -m experiments.cleaned_interface.fm003 seal
python -m experiments.cleaned_interface.fm003 replay
python -m experiments.cleaned_interface.fm003 census --phase phase1
python -m experiments.cleaned_interface.fm003 continue
python -m experiments.cleaned_interface.fm003 census --phase phase3
python -m experiments.cleaned_interface.fm003 census --phase phase4
python -m experiments.cleaned_interface.fm003 report
```

Each completed phase is validated, committed and pushed. Existing incomplete
stage/census directories are refused rather than overwritten. A failed required
gate stops subsequent phases under the frozen plan.
