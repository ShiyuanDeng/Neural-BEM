# MA-006 — operator atlas and trace-cutoff feedback

2026-09-29. Owner: Codex. Independent reviewer: unassigned.

- **Approval status: APPROVED.** The user's “go” accepts the preceding review's
  recommendation to implement and run the operator/cutoff study. This is the
  bounded implementation of that request, not an additional inverse campaign.
- **Execution status: IN PROGRESS.** Existing checkout and branch retained;
  no branch/worktree creation, production changes, or historical-source edits.
- **Question:** Does projecting resolved traces understate the cutoff needed
  by a reduced Müller solve, and can retained/omitted operator coupling explain
  the discrepancy for data, shape sensitivities and a fixed local update?
- **Hypothesis:** small trace tails alone do not uniformly predict the usable
  solve cutoff. Direct reduced solves and their matrix feedback provide the
  missing measurement. A negative result (projection suffices on this screen)
  is equally informative; no success count is required to finish the study.

## API map and changes

Read-only imports: `modal_muller_research/modal.py` (flux similarity, unitary
DFT, reduced solves); `shape_continuation/forward.py` (qualified nodal reference,
incident/readout builders); `geometry.py` and `atlas.py` (curve and normalized
normal harmonics). New isolated files: `modal_atlas/operator_atlas.py`, its
tests, and a report generator. Original MA and Laurent source files stay
unchanged because their hashes are recorded in earlier evidence.

The initial atlas is a **projected-Nyström modal control**, not a newly
coefficient-native or node-free assembler. This deliberately separates the
cutoff question from Laurent coefficient-workspace errors. The fixed coordinate
is the stored curve parameter `t`, with unknowns `(u, |gamma'(t)| dn u)` and
unitary DFT normalization. Shape directions are physical arclength normal
harmonics, projected into a fixed Cartesian coefficient window without
reparameterizing the displaced curve. Their actual normal velocities are used
in every derivative comparison. This is not MA-001's arclength trace basis.

## Frozen screen and comparisons

Ten state/frequency/contrast cells:

1. Unit circle, contrast 0.5, 0.5 and 2.5 GHz.
2. Unit circle, contrast 13.3, 2.5 GHz.
3. SC-022 star truth, contrast 0.5, 0.5 and 2.5 GHz.
4. SC-022 star truth, contrast 13.3, 2.5 GHz.
5. SC-022 C truth, contrasts 0.5 and 13.3, 2.5 GHz.
6. MA-004 D's final star and C, contrast 13.3, 2.5 GHz.

Use the existing 24-pair acquisition. Base/reference grids: 512/1024.
Cutoffs: 8, 12, 16, 24, 32, 48, 64, 96, 128, 192. Shape band P=12;
Cartesian direction window 192. Store selected operator/map derivatives for
constant and cosine-6 directions. Centered differences at RMS steps 1e-4 and
5e-5 check derivative convergence; use the finer difference in reports.

At each cutoff compare (a) projected resolved traces, (b) the retained principal
system, (c) exact Schur elimination including RHS correction and reconstruction
of omitted traces. Arm (c) is an algebraic control and is **not a fast solver**.
Measure retained-solution feedback, all four trace-block coupling norms,
retained-system conditioning, Dirichlet/flux tails, data errors, full P=12
Hadamard-Jacobian errors, and gradient/ridge-step discrepancies. Separately
compare selected discrete reduced-model derivatives (including dA, dB, dC)
against the continuous Hadamard expression on reduced traces.

The update diagnostic uses fixed synthetic observations
`d = y_ref + 0.01 ||y_ref|| J_ref eta / ||J_ref eta||`, with eta selecting
constant, cosine-3 and sine-6. This is a controlled local residual, not a
reconstruction or independent observation. All arms use the same d, data scale
and ridge `lambda = 1e-3 ||J_ref / ||y_ref||||_2^2`.

## Gates, limits and artifacts

Qualify base versus refined data <=1e-7, Jacobian <=1e-5; selected fine FD
data derivatives versus actual-velocity Hadamard <=1e-4; derivative-map
step refinement <=5e-3; normal-direction projection discrepancy <=1e-4.
Full modal/nodal agreement and Schur/feedback identities <=1e-9. Unqualified
cells remain visible and are excluded from cutoff recommendations.

For qualified cells report the first **tested** cutoff attaining data and
Jacobian relative errors <=1e-3, plus a separate requirement of gradient and
fixed-ridge step relative errors <=1e-2. Test all larger ladder entries before
calling a cutoff sufficient; do not assume monotonic convergence.

Stage A: implement tests and run the first low-contrast circle cell. Its
algebra/reference qualification releases the remaining nine cells. Stop if
the pilot cannot qualify within the declared grids; do not widen them silently.
Hard limits: 120 nodal matrix assemblies, 320 reduced/Schur factorizations,
30 minutes measured campaign wall time, 1 GiB saved numerical artifacts.
One worker, one BLAS thread. Check reservations before each cell and retain
failures. No new inverse runs or automatic successor.

Artifacts: `results/validation/modal_atlas/MA-006/`, with manifest/source and
input digests, numerical NPZ snapshots (A, B, readout, both source/reciprocal
traces, selected dA/dB/dC, geometry, basis, residual and cutoff arms), JSON
diagnostics, reproducible report and figures. Record actual work and timings;
do not infer end-to-end speedup from reduced factorization timing.

Decision: identify whether operator feedback changes usable K_u on this
screen, and retain the numerical records needed for subsequent atlas analysis.
Adaptive K_u inside the production inverse, coefficient-native assembly,
noise-aware continuation, and generalization are outside this contract.
