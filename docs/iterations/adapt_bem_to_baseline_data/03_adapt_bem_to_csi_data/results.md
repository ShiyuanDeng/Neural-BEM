# Adapt the BEM inverse to CSI data: results

## Review stop 2: forward checks, 18 November 2026

**Outcome: the adapter passes every check, but the simulated circle fails
the user's 1% rule at 4, 6, 7 and 8 GHz.** Our forward matches an exact
series solution to about 1e-13. So the excess is in CSI's simulated data,
not in our forward or the adapter. Per the plan this stops the work: the
coordinator asks the user.

Run: `experiments/bem_on_baseline_data/csi_forward_check.py`, CPU, one
thread, 34.5 s, peak memory 1.2 GB. Solver: a clean `git archive` of commit
`78f084ca9`, because the checkout's `solvers/bem_inverse/` was being edited
by `bem-gpu` (recorded in the receipt). No fit ran. Truth was read only by
this script.

Evidence: [forward_checks.json](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/forward_checks.json),
[truth_predictions.npz](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/truth_predictions.npz),
[cylinder_frame_info.json](../../../../results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/cylinder_frame_info.json).
The NPZ is git-ignored and stays local; its SHA-256 is beside it.
The first run, kept in `forward_checks_run1_exact_circle_skipped/`, has the same numbers. It
skipped the exact series on the circle because the script's circle test was
too strict (a round-off-sized coefficient); that was fixed and the run repeated.

### Adapter checks

| Check | Result | Pass |
|---|---|---|
| Our factor vs CC-CSI's saved factors (288 rows), conj(Enor·ω_n²) | max relative difference 8.5e-14 | yes |
| Simulated table: conj(incident) vs our unit field i H0(kr)/4, all pairs | ≤ 1.3e-14 | yes |
| Simulated table: factor equals 1 | ≤ 2.9e-14 | yes |
| File order ↔ C order permutation round trip | ≤ 1.2e-16 | yes |
| Ragged vs rectangular B5/B8 at the start circle, all 8 frequencies, band 11 + contrast column | loss 1.2e-16, residual 5.7e-16, Jacobian 7.5e-16, gradient 2.9e-16 (relative) | yes |

The rectangular branch does accept the masked table. The two layouts agree to
round-off, so the frequency-block layout keeps the default loss.

Spread of |c| over the 36 sources (measured file, information only): largest
over smallest is 1.0002–1.0060 per frequency (worst 5 GHz). Phase spread
0.01–0.19°. So dividing by c hardly reweights sources.

### Mismatch per frequency on the true shapes

Relative L2, ‖our forward on the truth − data‖ / ‖data‖. The same to four
digits at the truth's own resolution and at the fit's storage band 192.

| GHz | Circle `circle__c4`, ε 4 | Cylinder `dielTM_dec8f`, nominal ε 3 |
|---|---|---|
| 1 | 0.17% | 47.8% |
| 2 | 0.13% | 23.1% |
| 3 | 0.30% | 24.5% |
| 4 | **1.14%** | 27.7% |
| 5 | 0.82% | 30.5% |
| 6 | **1.68%** | 33.9% |
| 7 | **2.29%** | 37.1% |
| 8 | **5.91%** | 40.4% |

Exact series check: for both circles our forward equals the separation of
variables solution to 6e-16 – 2.3e-13. The circle data differ from that
exact solution by the same amounts as from our forward. The error grows with
frequency, as a grid error would. CSI's forward grid is 0.625 mm with a
staircase boundary and averaged material (CSI note); that cause is likely
but not measured here.

Cylinder: the truth is nominal (about 30 mm offset, ε 3 ± 0.3), and the data
are measured. Fitting one complex number to each frequency, for information
only, leaves 16–37%. A frame check (information only, never used by a fit)
puts the same cylinder at (0,−30), (+30,0) and (−30,0) mm; those give
86–138%, against 23–48% at the nominal (0,+30) mm. So the frame sign is right.
The rest is the nominal geometry and measurement error. It is reported, not
judged.

### Series limit at 8 GHz

The solver's coefficient-based wave radius and loss, at k = 8.38 per 5 cm:

| Curve | Wave radius | k × radius | Loss | Under 1e-9 |
|---|---|---|---|---|
| Cylinder truth | 15 mm | 2.5 | 7.4e-16 | yes |
| Circle truth | 50 mm | 8.4 | 1.4e-13 | yes |
| Start circle | 65 mm | 10.9 | 1.5e-12 | yes |

8 GHz is not refused; the series limit stays 1e-9.

### Open for the coordinator

- The 1% rule fails on the circle at 4, 6, 7 and 8 GHz (worst 5.9%). By the
  user's decision, the coordinator asks the user before any fit.
- Not done yet: the small test file `csi_test.py` from the plan. The
  permutation, factor and conjugation checks above cover the same ground.
