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
