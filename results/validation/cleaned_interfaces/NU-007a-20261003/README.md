# NU-007a: completion of GPU geometry-certificate qualification

2026-10-03. Authorized by the user after the NU-006 runtime investigation.
The [fixed protocol](PLAN.md), [contract](contract.json), and source/input
[manifest](manifest.json) were written before this rerun. Original NU-007
failed results remain untouched.

Status: qualified and integrated. The full offline precheck, all 18 complete
inverse pairs (36 fits), archived NU-006 identity, and nodal retention gates
passed. Shared integration occurred only after FM-002 completed its final
verification. All **142 package/interface regression tests passed** after
integration, with no skips or failures (132.09 s).

## Matched full-path runtime

Three repetitions per arm, with the arm order reversed in repetition 2.
Both arms use modal physics, CUDA preparation, four frequency threads, one
BLAS thread, identical NU-006 starts/observation bytes, and the same policy.
The only numerical difference is CPU versus GPU certificate evaluation.

| Core case | NU-006 wall (s) | NU-007 wall (s) | CPU certificate (s) | GPU certificate (s) |
|---|---:|---:|---:|---:|
| wrong_circle | 6.958 | 6.870 | 0.115 | 0.008 |
| circle_to_star | 22.860 | 18.554 | 4.369 | 0.340 |
| circle_to_c | 29.506 | 20.590 | 9.816 | 1.076 |
| kite | 128.928 | 63.841 | 68.225 | 3.906 |
| peanut | 17.737 | 15.936 | 2.145 | 0.219 |
| hook | 41.203 | 23.842 | 18.826 | 1.927 |
| **Sum of per-case medians** | **247.192** | **149.634** | **103.496** | **7.477** |

Total wall time fell **39.5%** (1.65x speedup); certificate work fell **92.8%**
(13.84x speedup). Every case's median improved. The original predictions of
140–160 s total and at most 15 s of certificate work were met. Each timing
sample is retained in [qualification.json](qualification.json), with full
receipts under `pair_1/`, `pair_2/`, and `pair_3/`.

No preparation/certificate fallback occurred. No other numerical work was
detected at fit boundaries; this was sampled before and after each fit, not
continuously. These are the six core cases, not the full 36-case suite.

## Full-path numerical qualification

All 18 fresh pairs had bit-identical accepted states and final coefficients,
the same complete trial traces (including damping/backtracking and validity
tiers), decisions, units, tier counts and comparison statuses. Both endpoint
audits passed in every run. All 36 fits also retained archived NU-006 accepted
step counts, full trial traces, decisions, units and tier counts; the maximum
relative final-curve difference from the archive was **0**.

The existing NU-001 no-drift and >=5/6 matching rule passes: no drift flags
and **6/6 retained**. Five cases are PASS; circle_to_star retains its existing
REGRESSION status against the nodal reference. This is performance retention,
not a claim of newly improved recovery. Recomputed per-stage certificate and
speed-ratio evidence is included in `qualification.json` under `drift_audit`.

See [pairs.json](pairs.json), [campaign.log](campaign.log), and
[report.log](report.log). Report-source revisions are preserved and described
in [report_source.json](report_source.json); later revisions strengthened the
recorded identity checks and retained the per-stage drift evidence without
changing fits, certificate formulas, or comparison thresholds.

## Completed offline qualification

All 864 paired trials on 72 saved NU-006 states passed:

- Same acceptance/refusal decisions and reasons, exact accepted candidates,
  validity roles/tiers, and presence of increment/full bound records.
- All accepted coefficient byte hashes matched; all 74 refused pairs agreed.
- Every bound agreed within `1e-9 * max(1, abs(host bound))` and stayed on the
  same side of 1. Both implementations also agreed on the regularity-floor
  predicate.
- Maximum scaled difference: 5.97e-12. Closest bound to 1: 0.0063912.
- Zero device-certificate fallbacks.
- CPU certificate work: 1,615.06 s. GPU: 181.76 s, 8.89x faster. This replay
  overlapped FM-002; it is numerical qualification and a diagnostic timing,
  not a quiet-host full-path comparison.

See [precheck.json](precheck.json), [per-state raw records](precheck_states/),
and [precheck.log](precheck.log).

The 23 [focused tests](focused_tests.xml) also passed, with none skipped.
They include near-bound and regularity-threshold decisions, a near-cusp/cusp/
crossing family, clockwise refusal, device-memory fallback, and the staged
public CPU/CUDA selection. The numerical certificate formulas and validity
conditions were not relaxed; the revised comparison gate measures numerical
agreement on the scale of its decision threshold. Its choice followed the
original failed gate and diagnostic; that prior observation is disclosed.

## Isolation and integration

FM-002 hashes every existing numerical source. All 304 shared sealed source
files were preserved through its successful final verification; see the
[preservation receipt](fm002_preservation.json). Qualification executed from the independent
[source archive](sources.tar.gz), extracted under `/tmp`; this is an ordinary
source snapshot, not a Git branch or worktree. It reads the original input
bytes after checking their hashes.

The applied [integration](integration.patch) changes only maintained geometry
selection: `certified_spectral` uses the existing `DeviceCertifiedUpdate` on
CUDA, retaining `BatchedCertifiedUpdate` on CPU. The default spline/nodal
selection is unchanged. No relaxed-BIE implementation is edited.
The shared selection bytes exactly match the qualified archive. The GPU path
retains a counted CPU fallback on device-memory exhaustion.
The [integration verification](integration_verification.json) records source
and artifact hashes, with test output in [integration_tests.log](integration_tests.log)
and [integration_tests.xml](integration_tests.xml). The test command was:

```bash
env PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/drdeng/miniconda3/envs/EMNerf/bin/python -m pytest \
  pytest/bem_inverse experiments/cleaned_interface -q \
  --junitxml=results/validation/cleaned_interfaces/NU-007a-20261003/integration_tests.xml
```

The new campaign driver is
[`nu007a.py`](../../../../experiments/cleaned_interface/nu007a.py), with
[`test_nu007a.py`](../../../../experiments/cleaned_interface/test_nu007a.py).
The separately hashed report driver is
[`nu007a_report.py`](../../../../experiments/cleaned_interface/nu007a_report.py).
All historical inputs, failed attempts, and source archives are preserved.
The temporary selection-test skip used during the concurrent campaign was
removed after integration; it is now an unconditional public-selection test.

For source-seal verification or report reproduction, extract `sources.tar.gz`
to an ordinary temporary directory, put its `solvers/` directory and root
first on `PYTHONPATH`, set `NU007_WORKSPACE` to this repository, and run from
outside the live checkout. Use `python -m experiments.cleaned_interface.nu007a
verify` to verify the frozen sources and inputs. The report command is the
absolute path to `experiments/cleaned_interface/nu007a_report.py`; its separate
source hash is pinned above. BLAS/OpenMP thread counts should remain 1.
