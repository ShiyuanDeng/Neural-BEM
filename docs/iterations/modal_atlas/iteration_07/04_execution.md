# MA-007 execution receipts

2026-10-13. The user authorized implementation and execution, then explicitly
selected the latest 19-fit plan and the proposed local raw-array retention route.
This is an execution record; the preregistered plan is preserved unchanged.

Work uses the existing `feature/shape-frequency-continuation` checkout as the
plan prescribes. No branch or worktree was created. Pre-existing NG-004 files and
`pytest/bem_inverse/test_coefficient_geometry.py` changes are unrelated and preserved.

## Phase A maximum-dimension pilot

Attempt: `results/validation/modal_atlas/MA-007/phaseA-max-001/`.
The TG-002 seal passed. Nine structural/package-boundary tests passed; numerical
pilot evaluations use only hook's prescribed initial circle, archived DP-001
F_screen last damped state, and archived failed endpoint, exactly padded to K384.

All 39 prescribed maximum-dimension field/response cells completed: four
frequency/catalog combinations at Ku320/352/384 plus the real 2.5 GHz B1024
evaluation on each of three states, with P159 complete projected responses.
Another 24 small-cutoff assemblies checked the eight sub-block comparisons per
state. Total elapsed: 198.79 seconds. Peak worker RSS: 1.67 GiB. Sampled maximum
GPU usage: 11.31 GiB of 31.84 GiB. Lossless chunks total about 505 MiB.

The sub-block property fails its 1e-12 threshold. Worst block relative errors:
2.7215e-9 (initial), 4.9942e-11 (last damped), 5.2258e-11 (failed endpoint).
Apply section 8.3's specified fallback: designated snapshot coverage retains
separately assembled matrices at every cutoff used in a conclusion, and the
resource forecast must charge that additional coverage. Do not treat a failed
sub-block identity as proof of a physical cutoff mechanism.

The opt-in settings now separate the coefficient workspace and trace cutoff
from K; the historical defaults remain available for C0. Modal stage validation
does not use the nodal node-count guard; the nodal guard remains active. The
plain progress-exit option is explicit and defaults off.

This pilot is partial qualification. It establishes no policy outcome, upper
bound, recovery result, complete derivative qualification, or release of Phase B.
The C0 recording/instrumentation pilot, its complete atlas/probes, and the
remaining qualification/release checks are still required. Machine-readable
state and outstanding work are in the evidence root. Raw NPZ arrays remain on
this machine only; their manifests, hashes, receipts and reports are committed.

## C0 instrumentation pair

Attempt: `results/validation/modal_atlas/MA-007/phaseA-control-001/`.
The historical named feedback policy ran from the prescribed hook start with
recording enabled, then disabled in a fresh interpreter, under the same sealed
source epoch. Both returned NUMERICAL_FAILURE at release_M11, with 1,099 fitting
work units, 8.6530739084 mm RMS, and 25.1401779119 mm Hausdorff upper bound.
Their endpoint audits pass, but geometric/data recovery does not.

Accepted states, trial decisions and final coefficients agree bitwise. Audited
output wall times were 25.593 s recorded and 23.438 s disabled; these include
capture/I/O overhead and are not an isolated speed claim. The recorder indexed
2,092 events and retained 2,007 lossless chunks (43.44 MiB). Serialization took
4.475 s, pure serialization waits took 1.132 s, and complete refusal reciprocal
traces added 76 separately charged post-return diagnostic work units (0.109 s).
Snapshot/operator retention remains part of the pending offline atlas.

Read-back verifies each chunk's exact hash/shape/dtype. Saved objectives,
gradients and regularized/clipped proposals replay within the plan's unchanged
tolerances; event counts reconcile with the solver's field/derivative receipts.
Ordinary runner JSON payloads are preserved locally byte for byte as ignored
`.json.raw` files. Committed receipts replace raw numerical arrays with lossless
NPZ references and hashes; expansion reproduces the original numerical content.

This closes the instrumentation pair, not the C0 recording pilot: its complete
five-role atlas, local probes, regeneration and the Phase B release gate remain
required. The machine-readable state lists those outstanding steps.

## First response-atlas attempt: retained implementation defect

`phaseA-atlas-001` completed all 114 prescribed frequency/catalog cells at the
five C0 roles, with separately assembled snapshots at every attempted cutoff.
Hash/shape/dtype read-back and stored source-system/prediction identities pass
for all 1,363 chunks (6.544 GiB). Numerical compute was 110.681 s; serialization
and read-back during collection took 166.157 s. This is not a complete atlas:
active-objective step tests, local probes, selected derivatives and regeneration
are still outstanding.

The response qualification implementation incorrectly also gated on intrinsic
diagnostic Jacobian columns. Section 3.3's threshold is for the complete-trial
Jacobian. All 19 initial-circle cells were therefore labeled unqualified from
extremely weak intrinsic directions, despite stable complete-trial responses.
The other 95 cells passed both response comparisons. Preserve all raw arrays
and flags, correct the gate to the specified complete-trial response, retain
intrinsic errors as separately labeled diagnostics, reseal and rerun the five
roles. This correction changes no threshold, direction coverage, solver or
geometry algorithm. It is an implementation correction, not a research policy
decision or a physical workspace-failure conclusion.

## Corrected response atlas

`phaseA-atlas-002` reran all five roles under a fresh source seal. Every one of
the 114 cells passes the prescribed field and complete-trial P127-column
response gate. Intrinsic diagnostics remain separately flagged, including weak
initial-circle columns that do not qualify. All attempted B512 matrices are
stored independently under the declared sub-block fallback.

Collection used 72.242 s numerical compute and 71.436 s serialization/read-back,
retaining 2.775 GiB of arrays. Peak worker RSS was 1.675 GiB; maximum CUDA reserved
memory was 10.830 GiB; sampled total GPU use peaked at 12.190 GiB of 31.843 GiB.
Read-back verifies all retained chunk hashes/shapes/dtypes and snapshot source
residual/paired-prediction identities. The active-objective step comparisons,
local probes, selected derivatives, regeneration and release forecast remain
pending; response qualification alone is not the complete C0 pilot or a ceiling.

## Initial registered HOLD branch and control implementation

`phaseA-probe-check-001` executes the registered role-1 HOLD branch from the
actual prescribed hook circle. It validates the opt-in independent trace
qualification with the existing LM optimizer: two accepted iterations, 22
charged branch units, all performed workspace/trace/move checks recorded, and
a qualified independent 320/352 full-real monitor. This partial registered
branch is not a full fit or policy/ceiling result. The remaining 44 branches
are still required in the completed probe batch.

The fixed S0 and O1–O7 schedules are implemented as an opt-in numerical policy.
Their metadata enumeration preserves the prescribed bridge, cap vectors,
zero-padding, and identical-rung skips. Trace and accepted-move qualification
are hooks in the existing optimizer, with every witness dispatched through its
charged ledger. Research geometry caches have one entry throughout the common
epoch to keep GPU retention bounded; this changes no radial/log/Graf tolerance.
No registry/default recipe was promoted. Nine structural/package tests pass.

The user resolved both O8 boundary details: each decision slot ends at the saved
winning two-iteration branch endpoint, and lambda resets to the default at each
new decision slot. Within a slot each candidate starts from the same saved
controller; no winning rung continues beyond its saved endpoint.

## Complete C0 local-branch batch

`phaseA-probes-001` closes all 45 registered branches (nine at each of the five
roles): 16 normal optimizer returns, 2 stage-quota returns, 21 numerical
refusals, and 6 range-limited entries. All computed recording chunks read back,
objectives/gradients/proposals replay, and field/reciprocal/event counts reconcile.
Raw arrays use about 1.526 GiB; branch and monitor elapsed computation is 628.777 s
(before separating serialization). This closes branch collection; labels,
matched K proposal replays, actual-direction audits, selected derivatives,
regeneration and the resource gate remain required. No policy/ceiling claim is
released by this batch.
