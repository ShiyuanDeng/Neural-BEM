# Radial-Fourier topology birth — iteration 01 execution

Outcome: **full_pass**.

This bundle separates four evidence classes: the saved oracle-only TD values
used by G1; new direct multi-component Kress forward/TD evidence in G0--G3;
optimization evidence in the T3/T4 trajectories; and truth-based qualification
metrics in `field_metrics.csv` and `geometry_metrics.csv`.  Only 0.50 GHz was
used for training and topology decisions.  The 1.50/2.50 GHz values are
holdouts and were not fed back into the inversion.

G0--G4 passed.  T4 ran and passed G5.  See
`metrics.json` for the exact gate record and the two MP4 files for the accepted
one-circle-to-two-circle inversion trajectories.
