# CI-001 implementation and focused qualification

2026-09-30. Implementation owner: Codex. Independent agent review: not
performed. The user authorized implementation and offered to run the 36-scene
campaign. The original iteration-01 plan remains the pre-implementation record.

The [maintained package](../../../../experiments/cleaned_interface/README.md)
now separates fitting inputs, the executable continuation policy, complete
geometry updates, physics, the shared LM optimizer, and independent reporting.
It runs without result-folder Python imports or solver/contrast monkeypatches.

The source and input inventory has exactly 36 configurations: 6 core, 6 fresh,
7 far and 17 modal. Twenty have archived damped observations. The other 16
are explicitly withheld until separately generated and qualified damped
catalogs are sealed. Original real samples and noise draws are preserved.

The noiseless schedule matches the archived MA-004 configuration exactly for
all 12 stages and optimizer settings. The centred projected trial and its
derivative preserve the extracted SC-035 construction; cleanup preserves the
SC-042 crop-then-pad operation. The named `cumulative_sc_ma/1.0.0` policy
produces both a readable plan and the runner's resolved operation/decision log.

The backend selection covers fitting, derivatives, exact-disk localization
and its BIE qualification, frontier diagnostics, and audits. Opaque states
keep nodal matrices/traces/factors out of the optimizer. CPU/GPU and frequency
concurrency are separate execution settings. Native modal Müller remains the
next backend integration and fails preflight explicitly rather than silently
falling back. The replacement contract is implemented; native modal inverse
qualification is not claimed.

SPD-010–015 threading, real CUDA, factor reuse and scoped geometry validation
remain available. SPD-016's recurrence/Mie contraction and fixed-ray damped
assembly use explicit services/kernel arguments. Device availability,
ray-envelope, and OOM handling have explicit reference/strict semantics.
The optional field-table extension is excluded.

Focused measurements and reproducible test commands are in the
[implementation evidence bundle](../../../../results/validation/cleaned_interfaces/CI-001-implementation/README.md).
These checks establish extraction/interface behavior and bounded numerical
agreement, not reconstruction performance across the 36 cases.

Two shared algorithm changes are exposed relative to DF: declared-noise
whitening/discrepancy stopping and recurrent cleanup before noisy full-catalog
releases. They carry SC-044 noise handling into the cumulative policy and stop
the frontier once the full real catalog reaches the declared discrepancy.
Their recovery/accuracy effect must be evaluated in the campaign. They are
not scene-specific D/DF branches, nor are they claimed as measured improvements.

The package freezes per-case geometry/residual tolerances, source/input
provenance, full historical predecessor references, work accounting and
runtime conditions before fitting. It keeps suffix-only and missing historical
costs visible. Comparison reports cannot claim requirement 1 until all 36
numerical gates and repeated matched runtime gates pass. The two known
high-contrast C failures remain in every report with their errors.

Next: the user runs the documented SPD pair control and the 36 original-start
configurations. No 36-scene fit, new synthetic benchmark catalog, full SPD D
pair, or all-36 speedup was run or claimed during this implementation turn.
