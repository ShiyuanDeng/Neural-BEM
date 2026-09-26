# SC-044 — fresh shapes and declared measurement noise

2026-09-26. Owner: Codex. Independent reviewer: unassigned. Authorized by the
user's instruction to execute the strategy comparisons and continue through
successive research obstacles. Existing branch and checkout only.

This contract is frozen before generating any observation or evaluating an
inverse on either target. It tests transfer of simple state strategies;
it does not tune a method against these shapes or establish population-level
robustness with two targets.

Two analytic constructions fixed in `run.py`: an asymmetric radial outline
with orders 3/5/7 and a deeper, thinner C than the development fixture.
The C's arclength-sampled outline is truncated once at K16 to define its
smooth truth. Both must pass the existing sampled geometric validity check.
Data use the existing 19 frequencies and 24 paired source/receiver channels,
the same physical contrast, and 2048 nodes, qualified against 1024 to 1e-8
relative per frequency. Failure retains the target and prevents its inverse;
do not adjust the geometry after seeing recovery.

Three datasets per target: clean, and 1% relative complex-RMS independent
Gaussian noise with seeds 44000 and 44001. At frequency f, each real/imag
component has standard deviation .01 ||y_f|| / sqrt(2*n). Save the actual
observations and standard deviations as JSON. The inverse receives these
observations and the declared noise standard deviations, not clean data or
truth geometry. Draws are paired across methods.

Whitening uses stage weights proportional to (||y_noisy,f||/sigma_f)^2.
With the inherited normalization this is exactly inverse-standard-deviation
whitening up to one common scale. Expected loss is sum(n_f)/sum(raw_weights).
Stop at 1.1^2 times that expected noise loss (or the inherited smaller-scale
numerical tolerance, whichever is larger). Prefix stages still advance to
the next data set; once the all-frequency suffix reaches discrepancy, stop
before releasing further modes. No best-truth iterate or noise-draw tuning.

All paths start from the existing wrong circle. A common four-stage prefix
uses M3/5/7/9, K8/12/16/20, 512/1024 nodes, 30 iterations and quotas
600/800/1000/1000. Compute each identical prefix once and charge its cost
to every complete path that reuses it. A failed prefix or failed endpoint
audit blocks its suffixes and stays in the denominator.

From each qualified prefix compare `none`, `boundary`, `cap`, with the
SC-042 definitions. Suffix M is 11/19/31; K192 for none/boundary and K64
for cap. Each of three suffix stages gets 380 work units, 22 iterations and
a 3600 s emergency wall ceiling. All grids, LM settings and field gates are
identical within a dataset. Cleanup can raise the objective, explicitly
visible in consecutive stage records. This differs from a one-off repair
of a saved artifact: it tests a complete pipeline from a common circle.

Six unique prefixes, 18 suffixes. Maximum fitting work is 20,400 unique
prefix units +20,520 suffix units. Each prefix/suffix endpoint gets the
SC-042 full-construction N/2N field/Jacobian/FD audit (130-unit ceiling;
24 audits, at most 3,120 units). Data generation costs 76 fields. At most
six numerical workers overall when sharing the host with the other studies;
no controlled wall-clock speed claim. Source and input hashes must remain
unchanged after preparation/sealing.

Report all failures, final RMS/Hausdorff, meaningful feature preservation,
loss relative to the declared discrepancy, and complete-path and unique work.
Compare methods within each target/draw. A simple restriction merits further
study only if it reduces the geometric-mean RMS relative to none, creates
no additional numerical/prefix failures, and no RMS or Hausdorff ratio above
1.25 with a 0.01 mm floor. Show each draw; do not convert six datasets into
six independent target shapes. No production default changes follow directly.

The data still share the inverse's governing model. This removes noiseless
precision as the sole evaluation regime; it does not test material,
calibration, dimensional or experimental model mismatch.
