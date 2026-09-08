# Implicit-MLP star: matched controls and acquisition decision

**Phases A–E are complete. Neural recovery remains unresolved.** The five-parameter
star recovers with eight paired views at 0.5/1.5 GHz. The same acquisition also
has full rank in the tested 21-mode local boundary space. Multistatic readout
improves conditioning, and higher frequency adds further sensitivity. The next
MLP experiment should isolate multistatic readout at the original frequencies,
followed by a separate 1.5/2.5 GHz ablation.

Base commit: `838bedf4eb37beb3c01ae770958e6c92f2abdf04`, branch
`feature/ordered-boundary-nystrom`, with the uncommitted implementation recorded
by source hashes in [provenance.json](provenance.json). This implements the
[latest directions](../../../../docs/iterations/implicit_mlp/iteration_01/02_proposals/04_chatgpt_revised_guide.md)
through their requested stopping point; no long neural run, continuation, or
new optimizer was launched.

## Decision table

| Question | Measured answer | Implication |
|---|---|---|
| Is the low-dimensional star recoverable with eight pairs? | Yes: 0.03870 mm maximum sampled boundary error; train relative L2 `5.433e-6`, fixed holdout `1.978e-4`. Twelve pairs reach essentially the same geometry. | Eight pairs suffice within the five-parameter family. This does not establish neural sufficiency. |
| Is the target-fitted MLP locally stable? | Three accepted steps improve train `0.01073 → 0.00745` and holdout `0.11963 → 0.08926`; boundary error changes `1.191 → 1.290 mm`. | A short local descent neighborhood is usable, but some geometry deteriorates. Long-term stability is untested. |
| What actually terminates steps? | Frozen backtrack 8 fails conversion refinement change; 9 passes every gate. It moves only 0.07076 mm and lowers loss 0.03883%. | The historical search was too shallow. Its first extra valid step is below the declared 0.1 mm meaningful-movement floor. |
| Which physical directions are observed? | All five physical columns have rank 5 at all three thresholds, for all acquisitions and both geometries in the original band. | Center/radius/amplitude/rotation are locally separated; the lobes are not absent from the original data. |
| Which general modes are observed? | The stacked original band has rank 21/21 at `1e-2`, `1e-3`, and `1e-4` for every acquisition. One paired-8 frequency has at least five structural null directions. | Paired-8 is not rank deficient in this particular two-frequency, mode-0..10 test. Higher modes and neural update geometry remain open. |
| Does multistatic readout help? | At the target, the scaled modal condition number improves `73.6 → 10.4`; the absolute smallest singular value increases `18.15×`. | It improves conditioning and absolute sensitivity, without creating missing rank in the tested stacked basis. |
| Does higher frequency add beyond multistatic? | Changing multistatic `{0.5,1.5}` to `{1.5,2.5}` raises the smallest target-relative modal singular value `4.83×` at both geometries. | Frequency adds strength even after enriching readout; it is not categorically required to recover the five-parameter star. |
| Which full MLP experiment comes next? | First multistatic-8 at `{0.5,1.5}`; then multistatic-8 at `{1.5,2.5}` as a separate frequency change. | Preserve the architecture, seed, initialization, inverse Eikonal policy, bandwidth 96, conversion gates, two frequency terms, and comparable work budget. |

The recommendation uses training-side derivative information. The fixed
3.0 GHz holdout is excluded from acquisition and frequency selection. These
are diagnostic experiments, not proof that the selected data recover an
arbitrary neural boundary or all 8,577 weights. Basin reachability, unprobed
shape directions and neural update geometry remain plausible contributors.

With two frequencies, paired-8 supplies 32 real residual rows, paired-12 supplies
48, and multistatic-8 supplies 256. These are upper bounds on data-Jacobian rank,
against 8,577 neural weights; they do not imply that every remaining weight
direction changes the boundary.

## Matched recovery and local control

| Control | Accepted updates | Train relative L2 | 3 GHz holdout | Maximum node-to-target error |
|---|---:|---:|---:|---:|
| Five parameters, paired-12 | 10 | `5.881e-6` | `2.064e-4` | 0.03869 mm |
| Five parameters, paired-8 | 13 | `5.433e-6` | `1.978e-4` | 0.03870 mm |
| Target-fitted MLP, initial | 0 | `0.01073` | `0.11963` | 1.191 mm |
| Target-fitted MLP, final | 3 | `0.00745` | `0.08926` | 1.290 mm |

The analytic controls share the same current parameter-FD Gauss–Newton code,
settings, wrong initialization and independent observations. Their final
`no_decreasing_step` label reflects proposals below the existing step floor;
geometric recovery is assessed separately. Their initial boundary error is
43.088 mm, versus 42.745 mm for the historical neural warm start: identical
nominal star parameters do not make the pretrained contour identical.

The MLP control reuses the existing exact-target supervised fitting procedure,
which produces an approximate target fit. Initial data-gradient norm is
`1.00728`; Eikonal-gradient norm is `9.67349`, or `0.096735` after its 0.01
weight. The final boundary error increase is retained as evidence; improving
training and holdout losses does not establish geometric recovery.

Full trajectories, settings, oracle checks and interpretation are in
[Phase A](phase_a/README.md) and [Phases B/C](phase_bc/README.md).

## Physical and modal observability

Directions use **equal 1 mm RMS normal boundary displacement**, integrated on
arc length. Physical derivatives retain their native units in
[physical_jacobian.csv](observability/physical_jacobian.csv). The separate
[modal probes](observability/modal_jacobian.csv) are constant plus cosine/sine
modes 1–10 on arc length. These analytic diagnostic curves never become the
production geometry representation and are never fitted back into the MLP.
The local `observability/jacobians.npz` archive contains the complex matrices
scaled to 1 mm RMS, with five physical columns followed by the 21 modal columns.
Dividing each column by its CSV `native_increment_for_1mm_rms` recovers the
native-unit complex derivative. CSVs retain native and scaled column norms.

The table uses real-stacked Jacobians normalized by each acquisition's fixed
exact-target response norm at each frequency, with frequency contributions
summed. All listed modal stacks have rank 21 at every requested threshold.

| Geometry | Acquisition | GHz | Smallest singular value | Smallest / largest |
|---|---|---|---:|---:|
| Wrong initial star | paired-8 | 0.5 + 1.5 | 0.011203 | 0.04927 |
| Wrong initial star | paired-12 | 0.5 + 1.5 | 0.016439 | 0.07842 |
| Wrong initial star | multistatic-8 | 0.5 + 1.5 | 0.007334 | 0.10945 |
| Target | paired-8 | 0.5 + 1.5 | 0.002746 | 0.01359 |
| Target | paired-12 | 0.5 + 1.5 | 0.012020 | 0.06001 |
| Target | multistatic-8 | 0.5 + 1.5 | 0.006911 | 0.09603 |
| Wrong initial star | multistatic-8 | 1.5 + 2.5 | 0.035394 | 0.38621 |
| Target | multistatic-8 | 1.5 + 2.5 | 0.033389 | 0.34211 |

Normalization matters. Multistatic readout increases the full response norm,
so it does **not** increase every target-relative sensitivity: its initial
smallest normalized singular value is below paired-8. Under absolute field
scaling, multistatic's original-band smallest modal singular value increases
`4.76×` at the wrong initial star and `18.15×` at the target. Both weightings
are retained in [the spectra](observability/singular_values.csv). Any next
inverse must keep its data scaling and balance with Eikonal regularization
explicit; improved conditioning alone is not a recovery guarantee.

In the original band, the largest absolute physical amplitude correlation with
center/radius across all arms and geometries is 0.255; the corresponding
rotation value is 0.0481. Full [column correlations](observability/column_correlations.csv)
and [spectral plots](observability/singular_spectra.png) are available.

The frequency sweep covers 0.25, 0.5, 1.0, 1.5, 2.0 and 2.5 GHz. At the target,
multistatic mode-5 cosine/sine relative sensitivities rise from `0.04154/0.03536`
at 1.5 GHz to `0.05649/0.05143` at 2.5 GHz. The weakest joint modal direction
benefits more: the `{1.5,2.5}` pair has a `4.83×` higher minimum than the original
pair at both shapes. It also exceeds the tested `{0.5,2.5}` pair. This supports
the subsequent frequency ablation while keeping two objective terms; there is
no hard `kR` cutoff. See [sensitivities](observability/sensitivity.png) and the
[observability bundle](observability/README.md).

## Validation, resolution and work

All **184 focused integration tests pass**, including exact paired-readout
equivalence, indexed JVP/adjoint finite differences, duplicate observations,
rectangular acquisitions, conversion rejection reasons, acceptance beyond eight
halvings, fatal-error rollback and failure-isolated holdout replay.

Fresh central differences at 0.5/1.5 GHz cover six directions, three RMS
perturbations (0.1, 0.03, 0.01 mm), both geometries and all acquisitions. All 72
direction/acquisition/frequency groups show second-order convergence; maximum
finest-step relative error is `1.123e-6`. Every swept frequency separately passes
forward and derivative 256/512-node refinement. The independent
[spectrum refinement audit](observability/spectrum_refinement.json) bounds changes
in the singular values and their thresholds: all **792 rank checks** are stable,
with maximum bound/largest-singular-value `1.06e-10`. This compares the two
discretizations and does not certify continuum or noise-dependent inverse accuracy.

| Study | Forward / conversion resolution | Budget and actual work | Optimizer and stop |
|---|---|---|---|
| A0/A1 | Kress 128; Method B bandwidth 48, grid 257, projected samples 128 | 14-update caps; 121/154 inverse evaluations, 75.53/95.81 s | Existing parameter-FD damped GN; both `no_decreasing_step` |
| B | Kress 194; bandwidth 96, grid 513, projected samples 256 | 3 updates; 27 attempted training evaluations, 23 rejected trials | Adam/adjoint fallback; `maximum_iterations` |
| C | Frozen historical B configuration | Backtracks 0–14; 16 attempted evaluations including initial, 235.46 s | Unchanged steepest fallback; `completed_frozen_diagnostic_budget` |
| D/E | Exact analytic curves; Kress 256/512; no Method-B conversion | 336 frequency-specific forwards, 1,248 frequency-specific JVPs; 1,739.98 s | No optimizer; `completed_requested_diagnostics` |

A/B/C evaluation counts include a complete frequency vector; B/C attempts also
include geometry rejection before a BEM solve. D/E counts individual frequencies.
B's original 387.22 s included 52.22 s of successful holdout callbacks; the
corrected driver runs holdout after optimization. A separate saved-state replay
reproduced all four holdout values exactly and restored final weights. Its
timing and the original accounting are preserved in the B/C bundle.

Rejection reason counts overlap when a trial fails multiple tested gates:

| Study | Topology | Conversion distance | Refinement change | Motion | Data Armijo | Regularized Armijo | Solver/nonfinite |
|---|---:|---:|---:|---:|---:|---:|---:|
| A0/A1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| B | 3 | 3 | 1 | 10 | 17 | 17 | 0 |
| C | 2 | 2 | 4 | 1 | 1 | 1 | 0 |
| D/E | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

A uses the existing loss-decrease test, not neural Armijo; D/E have no optimizer.
Physics/motion conditions are unevaluated when extraction/conversion rejects first.
All conversion tolerances remain unchanged: 0.2 mm distance and 0.01 mm
refinement change. Maximum neural boundary motion remains 2 mm. The 0.1 mm
meaningful-step floor is reporting only; every accepted frozen fallback lies below it.

All acquisitions use the existing 0.30 m ring, 0.2 rad source/receiver offset,
source strength `1e-6`, exterior relative permittivity 6 and interior 3, with
zero conductivity. Paired-8/12 select the diagonal; multistatic-8 retains all 64
entries from the same eight source solves. Inverse training remains 0.5/1.5 GHz.
The common holdout is **3.0 GHz only**, independently verified at 512/1024 oracle
nodes with maximum relative difference `2.494e-10`; 0.25 GHz is reserved for the
diagnostic candidate sweep, not holdout.

## Implementation and reproduction

Neural adjoint defaults now use 14 halvings; parameter-FD defaults remain eight,
including mixed solver comparisons. Each trial logs independent rejection
reasons and rejected/fatal states restore accepted weights. `--start-at-truth`
reuses the exact-target fitting control; optional holdout replay runs only after
optimization and preserves its completed result even when evaluation fails.

`IndexedForwardProblem` and its prediction functions select arbitrary entries
from the existing Kress response, with a matching indexed objective adjoint.
The paired interface remains unchanged and the neural production driver still
uses paired observations. A full multistatic neural inverse is the next
experiment, not an outcome claimed by this implementation.

See [metrics.json](metrics.json), [decision_table.csv](decision_table.csv),
[commands.txt](commands.txt), [provenance.json](provenance.json), and
[tests.log](tests.log). Generated checkpoints, response/Jacobian arrays, per-weight
trajectories and plots remain local artifacts under the repository's existing
binary-output policy. Commands regenerate the controls and diagnostics; the
frozen audit additionally requires the existing historical checkpoint/archive.
