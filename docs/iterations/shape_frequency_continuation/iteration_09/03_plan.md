# SC-026 plan — a consolidated atlas dataset, then a first analysis

2026-09-24. The user asked for the atlas dataset to be filled before
strategies are proposed ("fill the dataset first, then … some analysing …
cp when you filled the dataset"). The work is descriptive: no policy claim
and no change to any recorded run. Existing branch.

## Dataset

**States.** Every accepted state recorded in:
- SC-022: 6 runs;
- SC-024: 19 runs, including the V2x4 diagnostic;
- SC-025: 24 runs, covering the six cases and four arms.

That is 2,066 state records and 1,286 unique curves once each case is
deduplicated. An `index.json` maps every unique curve to each place it
occurs, with its source, run, stage, iteration, band, loss and damping.

**Cells.** For each unique state and each of SC-022's 19 catalog frequencies
(0.25–2.5 GHz), at N=512:
- the normalized residual Jacobian J, 48 measurement rows × 97
  normal-harmonic coordinates (P=48);
- the residual r;
- the loss, the relative residual and the solver residual.

G = JᵀJ and g = Jᵀr are then exact, and every SC-022 layer derives from
them. J is stored rather than G because it is half the size and keeps the
per-measurement structure. The cells use SC-022's conventions, inputs and
oracles; the held-out cases use SC-025's.

**Evaluation-only layers**, in separate files:
- the normal-ray error per harmonic, with its coverage and misalignment;
- the closest-distance proxy;
- symmetric RMS and Hausdorff distances;
- the tightest curvature radius;
- the refit error at K=192;
- the speed ratio and the perimeter.

**Build check.** For SC-022 states, JᵀJ and Jᵀr must equal SC-022's stored
blocks to ≤1e-12 relative. The input hashes must match their bundles'
manifests.

**Storage.** About 1 GB of `.npz`, kept locally and not tracked. The index,
manifest, hashes and README are tracked.

**Budget.** About 24k cells, roughly 2 h on 22 processes.

## Analysis

The analysis is brief and descriptive, written after the build. It covers:
- how many harmonics each frequency determines, and how that depends on the
  state;
- whether the frequencies agree on the step;
- how the determined harmonics compare with where the error is;
- what distinguishes states that later roughened or stalled.

Strategies are proposed separately, from this analysis.
