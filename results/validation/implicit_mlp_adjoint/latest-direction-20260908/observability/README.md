# Star acquisition observability

Commit `838bedf4eb37beb3c01ae770958e6c92f2abdf04` with source hashes in provenance.json.

Exact analytic wrong initial star and target; Kress 256/512 native-angle nodes. No Method-B conversion or MLP fit is used by these diagnostic probes. Production geometry remains unchanged. Physical columns and arc-length normal modes 0..10 use equal 1 mm RMS normal motion. Native derivatives retain their declared units.

Acquisitions: paired-8 and paired-12 select source i/receiver i; multistatic-8 retains all 64 source-major entries using the same eight sources and receivers. Ring radius 0.3 m, receiver offset 0.06/0.3 rad, source strength 1e-6, original materials. Probe frequencies: [0.25, 0.5, 1.0, 1.5, 2.0, 2.5] GHz; reserved holdout: 3 GHz, unused here. No optimizer, accepted/rejected trial loop, or holdout tuning. Rejection counts: {}.

Budget: one bounded baseline plus conditional six-frequency study at two shapes and two resolutions, central differences for six directions at three perturbation magnitudes in the original band. Actual work: {'forward_frequency_solves': 336, 'jvp_frequency_solves': 1248}; wall time 1740.0 s. Stop: `completed_requested_diagnostics`.

Baseline resolution pass: True; finite-difference convergence-window pass: True; sweep executed: True; all-frequency resolution pass: True. Thresholds are recorded per row. Spectra include structural zero singular values and ranks at 1e-2, 1e-3, 1e-4. Absolute spectra preserve field units; target-relative spectra normalize each frequency by its exact-target prediction norm, matching equal relative frequency contributions.

This establishes local sensitivities and sampled-resolution stability for the declared diagnostic shape spaces, conditional on passing gates. It does not prove global nonlinear or neural recovery, a noise-dependent usable rank, or convergence of an MLP/Method-B representation. See the parent decision table before any long neural run.
