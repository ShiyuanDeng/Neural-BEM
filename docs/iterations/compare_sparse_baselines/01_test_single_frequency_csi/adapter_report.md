# Native 24-pair CSI adapter

The native acquisition checks passed at **03:13:28 UTC on 19 November 2026**.
On the 1.25 mm operators supplied to CSI, the true circle reproduced the
24 sealed readings to **0.64293% relative error**, below the 1% limit.

| Clean input | Pair order | Relative round-trip error | Mask / normalizer / residual counts |
|---|---|---:|---:|
| [Circle](../../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__clean/check.json) | Exact | 3.48e-16 | 24 / 24 / 24 |
| [Kite](../../../../results/csi/native_tg002/2026-11-19/checks/table_kite__c4__clean/check.json) | Exact | 4.87e-16 | 24 / 24 / 24 |

## Field and image units

The adapter reads the same 0.5 GHz column as the BEM runner. The sealed
source strength is 1e-6. Both incident and measured fields are divided
by this strength and conjugated for CSI. Prediction reverses both steps.

The vacuum-equivalent frequency is 1.224744871348682 GHz. It gives the
native exterior wavenumber of 25.66875441776988 per metre. The real
permittivity ratio is one plus the real part of the recovered susceptibility.

The native back-propagation weight uses the full 24-receiver operator
for each source. Both cases reproduced the full-operator start exactly.
CSI's data normalizer and residual use the single measured pair per source.

At the start, machine epsilon divided by the state-normalizer denominator
was 7.15e-15 scaled versus 7.15e9 unscaled for circle, and 3.22e-14
versus 3.22e10 for kite. The old gradient starts at zero in both units.

The source positions reconstructed from the CSI angles agreed with the
sealed geometry to 2.78e-16 m and receivers to 2.80e-16 m. SHA-256
receipts cover both pinned checkouts' identities, the sealed observations,
the 24 complex readings, physical positions, table, mask and `CSI.m`.
[Circle inputs](../../../../results/csi/native_tg002/2026-11-19/inputs/circle__c4__clean/inputs.json)
· [Kite inputs](../../../../results/csi/native_tg002/2026-11-19/inputs/kite__c4__clean/inputs.json)

## Circle forward check

The true circle was sampled on dual cell centres, then averaged onto
primary Ez nodes with the pinned MaxwellFDFD material routine. Both
grids used the same adapter and image-prediction function as the inverse.

| Cell size | Relative error vs sealed | Relative error vs disk series | Relative solve residual | Best-fit gain, diagnostic only |
|---|---:|---:|---:|---:|
| 1.25 mm | 0.64293% | 0.64293% | 3.06e-13 | 0.999557 − 0.003866i |
| 0.625 mm | 0.66058% | 0.66058% | 1.23e-12 | 0.998832 − 0.005423i |

The comparison used unit gain and zero phase correction. The independent
33-order disk series agreed with the sealed readings to 1.31e-15. The
finer grid had slightly higher field error on these 24 readings.
[Forward check and gains](../../../../results/csi/native_tg002/2026-11-19/checks/forward_circle__c4__clean/check.json)
· [Coarse truth image and predictions](../../../../results/csi/native_tg002/2026-11-19/checks/forward_circle__c4__clean/truth_1.25mm.mat)

## Failed reader attempt and equivalence check

At 03:09 UTC, upstream `ReadFreData.m` stopped before returning a field.
With one receiver per source, MATLAB returns a row of unique receiver
angles. The TM distance subtraction on line 384 expects a column.
[Attempt 1 log](../../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__clean/attempt_01/matlab.log)
· [Upstream shape note](../../../../external/patches/cc-csi/native_single_receiver.md)

The coordinator authorized an owned TM configuration and a retry.
A two-receiver ring compared that code with the upstream reader and
start on 48 readings. The operators, mask, incident and total fields,
currents and axes matched exactly. Starting susceptibility differed by
1.79e-17 relative to upstream. The acceptance limit was 1e-12.
[Equivalence check](../../../../results/csi/native_tg002/2026-11-19/checks/equivalence_upstream/check.json)

Each MATLAB launch met the 32 GiB free-available-memory check, used
eight threads, and ran alone on CPU. The external checkouts received
no changes. Existing edits to MR-CSI and its display script are recorded
in the input receipts. The pinned classical `CSI.m` bytes matched.

## Frozen 1% noise draw 0

At 03:16 UTC the coordinator authorized the noisy pair. Python read the
same frozen draw as BEM. Both saved 24-reading vectors matched the
0.5 GHz column of the corresponding noise file bit for bit.

| Case | SHA-256 of frozen noise file | SHA-256 of 24 native readings |
|---|---|---|
| [Circle](../../../../results/csi/native_tg002/2026-11-19/inputs/circle__c4__n1d0/inputs.json) | `3d23d3a9f8d9168c32af5341eaf5a4a8c6b42a390a5a2973926b00b099652aba` | `a5bdb06134d39785b93e05c82ee959963b28b9fdcfa5bfcd50cdb527cef283fa` |
| [Kite](../../../../results/csi/native_tg002/2026-11-19/inputs/kite__c4__n1d0/inputs.json) | `355ca4155e95cf0ab6fd17e02fa906ecf0bbcc3d3c3b94379bcb95d512c738ff` | `0c813d0254631c13677ae4a5b5bcddd0972a88b8836811699aa80b5bb4d72997` |

The clean kite fit completed at 03:36:19 UTC. The noisy checks launched
at 03:36:20 and 03:36:27 UTC. Both launch records show zero MATLAB
processes and more than 32 GiB available.

| Noisy input | Relative round-trip error | Pair order | Mask / normalizer / residual | Result |
|---|---:|---|---:|---|
| [Circle](../../../../results/csi/native_tg002/2026-11-19/checks/table_circle__c4__n1d0/check.json) | 2.8762256725e-16 | Exact | 24 / 24 / 24 | Passed |
| [Kite](../../../../results/csi/native_tg002/2026-11-19/checks/table_kite__c4__n1d0/check.json) | 5.8031564510e-16 | Exact | 24 / 24 / 24 | Passed |

The coordinator received both passing results after the checks were
pushed. The second check finished at 03:36:32 UTC.

```text
Activity: compare_sparse_baselines/01_test_single_frequency_csi (adapter), 2026-11-19
Runs: 6/6 final checks passed; 7 MATLAB launches including attempt 1; wall time 0:32 including the wait
Result: clean circle/kite round trips 3.48e-16 / 4.87e-16; noisy 2.88e-16 / 5.80e-16; 24 readings each
        Noisy reading SHA-256 prefixes a5bdb06134d3 / 0c813d025463; clean circle forward 0.64293% / 0.66058%
Failures: first circle table attempt stopped at ReadFreData.m:384; table_circle__c4__clean/attempt_01/matlab.log
Upstream patches: none
Changes to our code: inputs.py, native_configuration.m, native_ring_tm.m, native_predict.m and the table, equivalence and forward checks
New unknowns: effect of the frozen noise draw on CSI image accuracy
Proposed next activity: run agent fits the checked noisy circle and kite on coordinator release
```
