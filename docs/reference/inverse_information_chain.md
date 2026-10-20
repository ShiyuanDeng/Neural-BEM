# Canonical inverse-solver information chain

User-supplied explanation framework, mapped to the maintained code on 2026-10-20.
Preserve the A1–C12 labels and terminology when explaining this inverse.
Explain in words; code-location answers should take at most three lines.

This map describes `modal_muller` + `certified_spectral` with `CumulativePolicy`
and no localization, the TG-002 default (`modal_fixed` recipe).
Optional policies change controls and stopping; identify them explicitly.

## Entry points and loops

- [Benchmark `run_case()` and `_fit()`](../../experiments/benchmark/campaign.py#L198)
  construct the fitting problem and invoke the solver.
- [Pipeline recipes](../../solvers/bem_inverse/pipelines.py#L52) select physics
  and geometry; [named policies](../../solvers/bem_inverse/policies.py#L101)
  also select schedule, optimizer options, and execution options.
- [Runner `fit()`](../../solvers/bem_inverse/runner.py#L179) executes the
  operation queue at line 315 and calls `fit_stage()` at line 425.
- [`FitStage`](../../solvers/bem_inverse/continuation/lm_backend.py#L71)
  describes one phase: data, weights, update/storage bands, resolution, and work.
- [`fit_stage()`](../../solvers/bem_inverse/continuation/lm_backend.py#L626)
  runs the phase. Its update loop starts at line 912, damping retries at 933,
  and backtracking at 951. Tests exercise these same implementations.

The chain below describes dependencies. Cached geometry, factors, predictions,
and derivatives can be reused; the code need not recompute every item on every
retry. Rejected trials retain the current accepted geometry.

## A. Stored geometry → predicted measurements

### A1. Stored Cartesian Fourier/Laurent geometry

Input: stored complex Cartesian coefficients `c_m`, defining the two-dimensional
boundary through its Fourier series. These are the persistent shape state.

Output: frequency-independent coefficient arrays for squared distances,
divided differences, logarithmic geometry, speed-weighted normals, and waves.

Code: [`FourierCurve`](../../solvers/bem_inverse/continuation/geometry.py#L26),
[`ModalGeometry.__init__()`](../../solvers/bem_inverse/modal_geometry.py#L271),
and [`ModalMuller._geometry()`](../../solvers/bem_inverse/modal_muller.py#L170).
The last method caches geometry by exact curve coefficients, window, and device.

### A2. Geometry arrays → modal Müller matrix

Input: A1 geometry and exterior/interior wavenumbers for one frequency.
Output: radial/logarithmic kernel coefficients, modal blocks, and matrix `A_f`.

Code: [`radial_coefficients()`](../../solvers/bem_inverse/modal_operator.py#L147),
[`kernel_matrix()`](../../solvers/bem_inverse/modal_operator.py#L219), and
[`muller_matrix()`](../../solvers/bem_inverse/modal_operator.py#L234).

The local blocks `v`, `k`, `kp`, and `t` are the exterior/interior combinations
needed by the Müller system. Assembly builds their differences directly.
Radial coefficients use analytic Bessel products; there is no radial sampling.

[`ModalMuller._matrix()`](../../solvers/bem_inverse/modal_muller.py#L193)
selects CPU or [CUDA assembly](../../solvers/bem_inverse/modal_cuda.py).
The geometry coefficient workspace is distinct from all three shape/trace bands.

### A3. Geometry + source/receiver positions → modal wave coefficients

Input: current geometry, physical frequency, and source/receiver positions.
Output: incident trace and speed-weighted flux coefficients for both point sets.
These supply the source RHS, receiver evaluation, and reciprocal RHS.

Code: [`point_kernels()`](../../solvers/bem_inverse/modal_operator.py#L309),
using [`WaveArrays`](../../solvers/bem_inverse/modal_geometry.py#L221).
[`ModalMuller._evaluate()`](../../solvers/bem_inverse/modal_muller.py#L255)
requests both sets through Graf/addition-theorem expansions.

### A4. Matrix + source RHS → boundary traces → predicted measurements

Input: `A_f` and source RHS. Factor the matrix and solve for boundary traces.
The stacked trace state contains `u_D` followed by `q`, the speed-weighted
normal flux. Contract the traces with receiver coefficients to obtain data.

Code: [`ModalMuller._evaluate()`](../../solvers/bem_inverse/modal_muller.py#L258).
It stores factors, forward traces, and the reciprocal RHS in `ModalState`.
The current implementation uses CPU LU even when matrix assembly uses CUDA.

[`Objective._predict()`](../../solvers/bem_inverse/continuation/lm_backend.py#L447)
dispatches A2–A4 over active frequencies and collects their predictions.
The current modal service uses paired point sources and receivers.

## B. Predicted measurements + geometry directions → residual Jacobian

### B5. Predicted data + observations → normalized real residual

Subtract observed data from predictions, normalize each frequency by its
observed-data norm with a small denominator floor, and apply square-root weights.
Stack real parts followed by imaginary parts to obtain `r`.

The loss is half the squared length of `r`. Default weights average the
normalized frequency losses equally; declared noise enables different weights.

Code: [`normalize()`](../../solvers/bem_inverse/continuation/lm_backend.py#L347),
[`Objective._evaluation()`](../../solvers/bem_inverse/continuation/lm_backend.py#L431),
and [`CumulativePolicy._config()`](../../solvers/bem_inverse/policy.py#L106).

### B6. Optimizer coordinates → complete-trial geometry derivatives

Input: current `c_m` and the normal-harmonic update coordinates `a_i`.
Output: one Cartesian coefficient velocity for each optimizer coordinate.
The coordinates and the stored Cartesian coefficients are different quantities.

Code: [`BorgesUpdate.prepare()`](../../solvers/bem_inverse/continuation/updates.py#L88)
defines coordinates; [`BatchedCertifiedUpdate.prepare()`](../../solvers/bem_inverse/batched.py#L77)
builds velocities using centered finite differences of projected geometry.

The differentiated map includes normal displacement, arclength reset, and
projection. This is a geometry finite difference, not a finite difference of
the forward solver. Validity decisions are checks around the smooth trial map.

[`make_update()`](../../solvers/bem_inverse/geometry_selection.py#L5) selects
`BatchedCertifiedUpdate` on CPU or its
[`DeviceCertifiedUpdate`](../../solvers/bem_inverse/device_certified.py#L115)
subclass on CUDA. The latter replaces certificate computation.

### B7. Geometry derivatives + forward/reciprocal traces → complex data Jacobian

Convert each B6 coefficient velocity into its normal-displacement weight,
including the boundary-speed factor. Solve the reciprocal RHS using the
existing Müller factors, then contract forward traces, reciprocal traces, and weights.

Code: [`ModalMuller.derivative()`](../../solvers/bem_inverse/modal_muller.py#L312),
[`_contract()`](../../solvers/bem_inverse/modal_muller.py#L287), and
[`hadamard()`](../../solvers/bem_inverse/modal_operator.py#L360).

The reciprocal RHS is solved as a batch of receiver columns once per frequency
and derivative evaluation. Those reciprocal traces serve all update directions;
the code does not repeat the reciprocal solve separately for each `a_i`.

### B8. Complex data Jacobian → residual Jacobian → Gauss–Newton quantities

Apply the same normalization, square-root weights, and real/imaginary stacking
as B5 to obtain `J`. Combine `J` with `r` for gradient `g`, and with itself
for the Gauss–Newton matrix `H_GN`.

Code: [`Objective.jacobian()`](../../solvers/bem_inverse/continuation/lm_backend.py#L503),
[`gradient_frame()`](../../solvers/bem_inverse/continuation/lm_backend.py#L802),
and [the iteration body](../../solvers/bem_inverse/continuation/lm_backend.py#L919).
The implementation names `J` as `matrix` and `H_GN` as `normal` here.

## C. Jacobian → LM proposal → accepted stored geometry

### C9. Gauss–Newton quantities → LM proposal

Use `g`, `H_GN`, damping metric `D`, and damping parameter `lambda` to solve
the damped linear system. Its answer is a proposed change in local update
coordinates, not yet a new stored curve.

Code: [`damping_matrix()`](../../solvers/bem_inverse/continuation/lm_backend.py#L864)
and [the proposal solve](../../solvers/bem_inverse/continuation/lm_backend.py#L935).
The default metric uses the diagonal of `H_GN` with a positive floor.

### C10. LM proposal → finite geometry trial

Bound the proposal, then try successively halved steps. Construct each candidate
by normal displacement, spectral arclength reset, and restriction to the stored
Cartesian band. The centered increment subtracts the base projection.

Code: [`control_step()`](../../solvers/bem_inverse/continuation/lm_backend.py#L181),
[backtracking and `update.trial()`](../../solvers/bem_inverse/continuation/lm_backend.py#L951),
[`CertifiedSpectralUpdate.trial()`](../../solvers/bem_inverse/certified.py#L276),
and [`arclength_quadrature()`](../../solvers/bem_inverse/spectral.py#L29).

The centered construction preserves the original stored curve for a zero step.
Geometry validity is checked on the moved curves and final candidate, using
certificates or sampled checks according to the selected implementation.

Geometry refinement constructs the candidate on a grid and a doubled grid.
It evaluates their coefficient difference as boundary-position differences,
then compares the maximum difference, divided by perimeter-based radius,
against `projection_tolerance` (default `1e-5`).

This geometry check is separate from C11 physics refinement. Its two grids do
not change `K_geometry`. Output is `c_trial`, in the same stored Cartesian band.
Exhausted backtracks lead to a larger damping value and a newly computed proposal.

### C11. Trial geometry → production/refined evaluation → accept or reject

Evaluate the candidate at working physics resolution. If its loss decreases,
compare current/candidate losses at both working and finer resolutions.
Check the candidate's prediction discrepancy at every active frequency.

Code: [candidate evaluation](../../solvers/bem_inverse/continuation/lm_backend.py#L1022),
[`validate()`](../../solvers/bem_inverse/continuation/lm_backend.py#L711),
[`checked_pair()`](../../solvers/bem_inverse/continuation/lm_backend.py#L677),
and [`resolution_check()` / `acceptance()`](../../solvers/bem_inverse/continuation/lm_backend.py#L374).

Acceptance needs improvement at both resolutions exceeding the margin and
the allowance for disagreement. The default also requires prediction agreement.
The current-shape prediction discrepancy has an additional optional check.

An accepted candidate replaces the current shape at
[line 1080](../../solvers/bem_inverse/continuation/lm_backend.py#L1080).
Ordinary rejections try another backtrack or damping value.

Numerical failures are different: in the default `modal_fixed` recipe,
an unresolved candidate or failed physics evaluation can stop fitting.
Optional resolution-response policies can refine or reject instead.

### C12. Accepted step → damping / stopping / continuation

Update damping, invoke accepted-state callbacks, and normally rebuild the
geometry directions and Jacobian at the accepted boundary. Check loss,
gradient, step, iteration, and enabled stagnation conditions.

Code: [accepted-state handling](../../solvers/bem_inverse/continuation/lm_backend.py#L1080)
and [`globalization.py`](../../solvers/bem_inverse/continuation/globalization.py).
Work limits and numerical refusals can also interrupt earlier operations;
they are not checked only after acceptance.

If this stage continues, repeat the chain with the accepted coefficients,
reusing available results. If it finishes normally or exhausts its stage
quota, the runner may advance; other stopping outcomes can end fitting.

[`CumulativePolicy.operations()`](../../solvers/bem_inverse/policy.py#L137)
and [`tail()`](../../solvers/bem_inverse/policy.py#L207) choose subsequent stages.
The runner carries the accepted boundary forward, applying scheduled cleanup
or storage resizing when required.

Stages may change active frequencies, `M`, `K_geometry`, and the physics
resolution profile, which determines `K_trace`. The returned endpoint also
undergoes [independent numerical checks](../../solvers/bem_inverse/runner.py#L63).

## Fixed terminology

| Name | Meaning |
|---|---|
| `c_m`, `c` | Stored Cartesian Fourier/Laurent curve coefficients. |
| `a_i`, `a` | Local optimizer coordinates: normal-harmonic displacement amplitudes in metres. |
| `M` | Active normal shape-update band; `FitStage.update_modes`. |
| `K_geometry` | Stored Cartesian Fourier geometry band; `FitStage.curve_modes`. |
| `K_trace` | Modal boundary-trace cutoff used by physics. |
| `u_D` | Dirichlet boundary trace. |
| `q` | Boundary speed times the outward normal derivative of the field. |
| `A_f` | Modal Müller matrix at one physical frequency. |
| `r` | Normalized, weighted real residual, including stacked real and imaginary parts. |
| `J` | Derivative of `r` with respect to local coordinates `a`; residual Jacobian. |
| `g` | LM/Gauss–Newton gradient: transpose of `J` applied to `r`. |
| `H_GN` | Gauss–Newton matrix: transpose of `J` multiplied by `J`. |
| `lambda` | LM damping parameter. |
| `D` | LM damping metric/matrix. |
| `c_trial` | Stored Cartesian coefficients returned by the complete finite geometry trial. |

`FitStage.nodes` and `refined_nodes` are modal resolution tokens, each eight
times `K_trace`, on this path. They are not the C10 geometry sample counts.
The coefficient workspace is another resolution setting, separate from `K_trace`.

Some implementation-local names are overloaded: `normal` in the optimizer
means `H_GN`, while `normal` in geometry is a speed-weighted normal.
The kernel assembly's local `q` is not the trace-state flux `q` defined above.

## How agents should use this frame

Answer the requested question briefly: identify its A1–C12 location, state
what information enters and leaves, and explain why the next part needs it.
Link the relevant function; do not reproduce the whole chain for every question.

Keep geometry projection accuracy (C10), physics resolution and loss acceptance
(C11), and final endpoint checks distinct. Keep `M`, `K_geometry`, `K_trace`,
and the coefficient workspace distinct.

Use this as the shared explanation structure, not as a frozen implementation
specification. Confirm current code when answering; line anchors describe the
2026-10-20 checkout and can move as implementation changes.
