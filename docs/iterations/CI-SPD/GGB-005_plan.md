# GGB-005 — Single-frequency initial circle fit

2026-10-05. Preregistered before execution. User: "try this back on one
frequency. also whats 2 resolutions??" This is a directly requested
single-frequency follow-up to the immediate GGB-004 case-8 series, retaining
the user's scope "Inspect the initial stage first." GGB-005 is the tracking
ID. No new branch/worktree, normal shape stage, or frequency sweep is authorized.

Run once from the original centred 0.35 m circle, fitting only the existing
0.5 GHz observations (the lowest member of the four-frequency panel). This
matches the GGB-002 S1 frequency; it is not the archived 0.4 GHz acquisition.
Use the byte-identical sealed data, same known material and three physical
coordinates (tx,ty,dr), same 18/18/12 mm caps, ordinary scheduled damping,
100-iteration limit, 2600 stage/8000 global work and 2400 s fit caps. No new
initialization, Mie shortcut, larger step, or retuning. Use CUDA and one
frequency/BLAS thread as before. The observation count is 512 pairs.

Derive the one-frequency weight and noise discrepancy from that observation
alone. Retain modal cutoffs 64 and 96 and the same 1e-4 field/decrease checks:
these are two numerical accuracies of the same physical frequency. Record
centre/radius/loss at every accepted state. Stop at the existing criterion;
meeting the noise threshold is distinct from restricted-model stationarity.
Do not force further iterations after a noise-target stop.

After fitting, audit all five stored frequencies at both cutoffs. Only
0.5 GHz counts toward fitting success, joint loss and fitted field gates;
0.4/0.75/1/1.25 GHz are explicitly held out. Recompute endpoint gradient and
Gauss-Newton model diagnostics only for the active frequency. Geometry truth
is used only for post-fit scoring/display. Compare timings and errors with
saved GGB-004 results; do not rerun the four-frequency fit.

Before execution, verify unchanged numerical-source hashes and sealed inputs
against GGB-004's passed CPU/CUDA similarity-derivative qualification. Reuse
those actual 0.5 GHz checks with their source receipt hash; a source mismatch
requires new qualification before fitting. Test single-frequency audit
selection, its holdout exclusion and the unchanged four-frequency path.
Save a fresh complete source manifest, authorization, tests, accepted states,
endpoint predictions, timings, and failure evidence. Generate report and
direct-boundary video using the established encoder; validate, commit and
push after the run.
