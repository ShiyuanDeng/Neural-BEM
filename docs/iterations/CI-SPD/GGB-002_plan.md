# GGB-002 — Case 8 with four real frequencies

Prepared 2026-10-05. **APPROVED** by the user: "go", responding to the
explicit GGB-002 approval request. The two arms below are authorized.

## Request and question

The user requested a BEM rerun of GGB-001 case 8 with four frequencies,
suspecting that the original single-frequency observations were insufficient.
This explicit case selection overrides the ordinary TG-002 scene restriction
for this experiment only. The original unsuccessful case and all its evidence
remain unchanged.

Test whether four-frequency data permit recovery from the same centred start.
A matched new single-frequency control distinguishes a benefit of the expanded
panel from changes in the observation generator. Success would support the
frequency-information hypothesis for this case; it would not identify a unique
cause of the historical failure.

## Frozen target, acquisition, and data provenance

- Official SingleTX cylinder sample index 8, not the eighth selected case.
- Original 64-by-64 permittivity image, physical pixel coordinates, 16 source
  locations, and 32 recovered receiver locations are retained. All 512 pairs,
  including collocated Tx/Rx pairs, are retained in source-first order.
- Object relative permittivity is 1.404252052307129; background is 1.
  Material is known to the inverse. This is a shape-recovery control.
- Inputs come from `/home/drdeng/Gau-Gal/outputs/GGB-001/prepared`, verified
  against its inventory and prepared-file hashes. The official archive member
  SHA256 is `060e9d779ec8b6ebfd299c54cf9204148cdd9f5c43b71c6b43cdc55c5b1e5cd6`.
- The archive supplies only 0.4 GHz observations. New frequencies are explicitly
  synthetic extensions, not measurements present in that archive.
- The four real frequencies are **0.5, 0.75, 1.0, and 1.25 GHz**, matching
  `CumulativePolicy.prefix_frequencies_hz`. Wavenumbers retain the archive's
  wavelength/speed convention, scaling its 0.4 GHz wavenumber linearly.
- Generate fields with an independent pixel-volume transmission calculation
  on the original permittivity image. Use its original physical source
  normalization and the frequency-dependent outgoing Green functions, cell
  interaction, and receiver map. Do not generate fitting data with the inverse
  modal solver or replace the pixel target with a truth-fitted smooth circle.
- Before extending the catalog, reconstruct the archived clean 0.4 GHz fields
  and require relative agreement <= 1e-5. Source, receiver, and self-cell
  conventions must be grounded in the archived operators and generator code;
  do not infer a frequency law from fitted scattered observations. If the
  generator cannot satisfy this gate, stop and retain the failure evidence.
- Require finite fields and a <= 1e-10 relative residual of each generated
  discrete volume system. Record the generating discretization and its
  physical limitations; this is not a claim of continuum-exact truth.
- Add 5% complex Gaussian noise by the released convention:
  `sigma = .05 * sqrt(mean(abs(clean)**2)/2)`. Use seed 1000 independently
  for each frequency in receiver-first ordering, then transpose to Tx/Rx.
  Reuse the exact 0.5 GHz array in both new arms. Seal all new inputs.

## Arms and inverse settings

1. **S1:** new synthetic 0.5 GHz observations only.
2. **F4:** new synthetic 0.5, 0.75, 1.0, and 1.25 GHz observations jointly.

The completed GGB-001 0.4 GHz run is a historical reference, not rerun or
treated as a matched control for the new generating path.

Both arms use the maintained `solvers/bem_inverse` numerical implementation,
the qualified GGB-001 full-matrix research adapter, `modal_muller`,
`certified_spectral`, CUDA execution, and one frequency thread. The start is
the original circle centred at (0,0) m with radius 0.35 m. There is no
localization, grid search, alternate start, restart, or material fitting.

Keep the original geometry storage band 32, normal-update modes 3 -> 7 -> 11,
100 iterations per stage, modal trace cutoff 64 refined to 96, and the 1e-4
production/refinement field gate. Retain the original LM step limits, damping,
and domain box [-1,1]^2 m. Only the observation panel changes between arms.

Normalize and whiten multi-frequency observations using the maintained
`CumulativePolicy._config` rule: weights proportional to
`(norm(data_f)/sigma_f)^2`, and discrepancy floor `1.1^2` times the expected
normalized noise loss. Use all of each arm's observations in every stage.

S1 has the original 650 work units per stage, 2000 total, and 600-second fit
cap. F4 has 2600 units per stage, 8000 total, and a 2400-second fit cap, scaling
the original limits by the number of frequencies. Thus F4 is not stopped
solely because each evaluation dispatches four times the physics work.
Iteration and geometry-proposal rules are identical. Report budget exhaustion
separately from numerical failure or convergence.

This uses the standard **four-frequency panel**, not the entire standard
continuation recipe. That recipe additionally requires 0.25 GHz damped warm-up,
damped prefixes, and a larger real catalog. Adding those would change both
the observations and the optimization path and needs a separate declared plan.

## Qualification, execution, and evidence

After approval, first qualify the new generator and the full-matrix adapter.
Independent analytic-disk fields must agree with the adapter to <= 1e-8 at
all four frequencies; rebuilt-geometry derivatives must agree to <= 1e-5 on
a deterministic off-centre fixture at the panel endpoints. These qualification
checks cannot select the case-8 start or tune its optimization settings.
Stop before inverse execution if an input or adapter gate fails.

Run each arm once, in order S1 then F4, with no automatic retries or
outcome-driven setting changes. Save source hashes, environment/device
information, generated clean/noisy fields and their hashes, resolved settings,
complete stage/trial histories, work ledgers, native physics receipts, returned
curve, and failures as they happen. Use fresh output directories below
`results/validation/cleaned_interfaces/GGB-002/`.

At each endpoint, independently evaluate all four real frequencies at trace
cutoffs 64 and 96; also evaluate the original archived 0.4 GHz observations.
Record per-frequency residuals, production/refinement error, whitened joint
loss and expected discrepancy, and actual stage stop reasons. Failed endpoint
audits do not convert to recovery. Separate fit and audit wall times.

Report original-grid image metrics (released SSIM/RRMSE, PSNR and contrast
SNR), the truth/start/S1/F4 images and curves, accepted steps, attempted
proposals, refusal categories, work units, physics timing and other wall time.
Judge data fit against declared noise thresholds and image recovery together;
SSIM or a normal optimizer return alone is insufficient.

A successful F4 with a failed S1 supports a benefit of the additional
frequencies under this frozen optimizer. If both recover, the new generator
or changed single frequency may explain the difference from GGB-001. If F4
stalls, report that four frequencies alone did not resolve this case under
these settings. Do not select further runs from any of these outcomes.

## Workspace and closeout

Work stays in `/home/drdeng/Neural_SDF_BEM_AD`. The currently checked-out
`feature/shape-frequency-continuation` branch contains the maintained
`solvers/bem_inverse` package used by GGB-001; the existing default
`feature/ordered-boundary-nystrom` branch does not contain that package.
Preserve the active maintained checkout for this follow-up. No branch or
worktree is created. Campaign code and truth-based scoring stay outside
`solvers/bem_inverse`; the original Gau-Gal checkout and archived GGB-001
evidence are read-only sources.

Before committing, validate the relevant adapter/generator tests, verify
reported residuals and metrics from saved arrays, and run whitespace checks.
After each new run, automatically commit and push its code, documentation,
and results, including unsuccessful evidence, to the current branch's
configured remote. Verify the remote commit and final working-tree status.

Approval received: **GGB-002**, with the two arms and four real frequencies
specified above. The original plan was written before experiment execution.

## Implementation and reproduction

Campaign: `experiments/benchmark/ggb002.py`. Adapter:
`experiments/benchmark/ggb002_adapter.py`, a byte-identical snapshot of
GGB-001's `comparisons/modal_full_matrix.py` (verified before execution).

The archived active-cell operator verifies point-cell off-diagonal entries
and the equal-area disk self-cell average of `G=i H0^(1)/4`. The integral is
`i*pi*a*H1^(1)(k*a)/(2*k) - 1/k^2`, divided by cell area for the diagonal.
The pixel current convention uses `eps0=8.85e-12`, `mu=eta_0/c`, `c=3e8` and
`J=-i*omega*eps0*cell_area*contrast*E_total`. The archived source strength
scales with omega. No scattered-field calibration is used. These conventions
are checked against the archived fields before extending the catalog.

Run from the repository root, with the existing EMNerf environment:

```bash
export PYTHONPATH=solvers:.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
GGB_PY=/home/drdeng/miniconda3/envs/EMNerf/bin/python
"$GGB_PY" -m experiments.benchmark.ggb002 prepare
"$GGB_PY" -m experiments.benchmark.ggb002 run --arm S1
"$GGB_PY" -m experiments.benchmark.ggb002 verify
# Validate, commit, and push S1 before the second inverse run.
"$GGB_PY" -m experiments.benchmark.ggb002 run --arm F4
"$GGB_PY" -m experiments.benchmark.ggb002 verify
# Validate, commit, and push F4; verify remote and final working-tree status.
```
