# Canonical inverse-solver information chain

User-supplied explanation framework, mapped to the maintained code on 2026-10-21
and updated for the 2026-10-25 reorganisation (no finer re-evaluations, D7).
Preserve the labels below; the geometry-update step uses its descriptive name.
Explain in words; code-location answers should take at most three lines.

This map describes `modal_muller` + `spectral` with `CumulativePolicy`
and no localization, the TG-002 default (`modal_fixed` recipe).
Optional policies change controls and stopping; identify them explicitly.

## Entry points and loops

- [Benchmark `run_case()`](../../experiments/benchmark/campaign.py#L237) and
  [`_fit()`](../../experiments/benchmark/campaign.py#L202) construct the fitting
  problem, invoke the solver, then run the endpoint audit.
- [Pipeline recipes](../../solvers/bem_inverse/pipelines.py) select physics
  and geometry; [named policies](../../solvers/bem_inverse/policies.py)
  also select schedule, optimizer options, and execution options.
- [Runner `fit()`](../../solvers/bem_inverse/runner.py) executes the
  visible operation queue and calls the canonical `fit_stage()`.
- [`FitStage`](../../solvers/bem_inverse/stage_types.py#L13)
  describes one stage: data, weights, update/storage bands, working resolution, and work.
- [`fit_stage()`](../../solvers/bem_inverse/fit_stage.py#L39)
  runs the stage. Its iteration, damping-retry and backtracking loops remain
  visible in that function.

The chain below describes dependencies. Cached geometry, factors, predictions,
and derivatives can be reused; the code need not recompute every item on every
retry. Rejected trials retain the current accepted geometry.

## Reading the canonical implementation

Start with `runner.fit()` → `fit_stage.fit_stage()` → the selected mathematical
module. `fit_stage()` has two local steps: `evaluate` runs A1–A4 at every active
frequency and then B5; `linearize` runs B6–B8. The caller passes the selected
methods as functions:

- `forward_solve` comes from `physics.make_backend()` with its physics context.
  Each file in `forward_solvers/` owns one context, its `forward_solve`, the
  reciprocal derivative, the resolution profile and the frontier.
- `geometry_update` comes from `geometry_selection.make_update()` with its update
  object. Each file in `geometry_update_methods/` owns its preparation and its
  trial curve, without an update-class inheritance chain.

`forward_batch.solve_frequencies()` dispatches one forward solve per active
frequency through `Ledger.calls`, which charges every solve and derivative.
The physics context keeps execution settings, geometry caches and counters;
the returned forward states keep factors and traces.

| Section | Module and mathematical entry points |
|---|---|
| A1 | `a1_geometry.ModalGeometry`, `log_modulus`, `WaveArrays` |
| A2 | `a2_muller.radial_coefficients`, `kernel_matrix`, `muller_matrix` |
| A3 | `a3_waves.point_kernels`, `graf_order`, `scaled_hankel` |
| A4 | `a4_fields.factorize`, `solve_and_predict`; `forward_solvers.modal_muller.forward_solve` |
| B5 | `b5_residual.evaluate`, `normalize`; `fit_stage` local `evaluate` |
| B6 | `geometry_update_methods.spectral.SpectralProjectedUpdate.prepare`, `batched_projection` |
| B7 | `b7_data_jacobian.normal_velocity_weights`, `reciprocal_jacobian`, `hadamard` |
| B8 | `b8_gauss_newton.residual_jacobian`, `gradient`, `curvature`; `fit_stage` local `linearize` |
| C9 | `c9_lm.damping_matrix`, `solve_proposal`, `hanke_damping`, `damping_floor` |
| Geometry update | `geometry_update_methods.control_step`; `geometry_update_methods.spectral.geometry_update`, `arclength_quadrature` |
| C11 | `checks.production_nondecreasing`, in the backtracking loop of `fit_stage` |
| C12 | `c12_iteration.scheduled_damping`, `accepted_damping`; visible commitment/callback/rebuild sequence in `fit_stage` |

[`checks.py`](../../solvers/bem_inverse/checks.py) contains numerical conditions,
including direct area, minimum-speed and sampled-intersection checks. Optional
certificate mathematics lives in [`geometry_update_methods/certificates.py`](../../solvers/bem_inverse/geometry_update_methods/certificates.py);
the Gaussian and similarity methods keep their own checks in their files.
The [endpoint audit](../../experiments/benchmark/audit.py#L62) is not part of the
fit: the benchmark runs it after `fit()` returns.

The [refactor status](inverse_refactor_status.md) records the earlier A1–C12
refactor; the [2026-10 reorganisation plan](../cleanup/bem_inverse_architecture_2026-10-24.md)
records what was removed since.

## A. Stored geometry → predicted measurements

### A1. Stored Cartesian Fourier/Laurent geometry

Input: stored complex Cartesian coefficients `c_m`, defining the two-dimensional
boundary through its Fourier series. These are the persistent shape state.

Output: frequency-independent coefficient arrays for squared distances,
divided differences, logarithmic geometry, speed-weighted normals, and waves.

Code: [`FourierCurve`](../../solvers/bem_inverse/continuation/geometry.py#L57),
[`ModalGeometry.__init__()`](../../solvers/bem_inverse/a1_geometry.py#L265),
and [`prepare_geometry()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L174).
The last function caches geometry by exact curve coefficients, window, and device.

### A2. Geometry arrays → modal Müller matrix

Input: A1 geometry and exterior/interior wavenumbers for one frequency.
Output: radial/logarithmic kernel coefficients, modal blocks, and matrix `A_f`.

Code: [`radial_coefficients()`](../../solvers/bem_inverse/a2_muller.py#L148),
[`kernel_matrix()`](../../solvers/bem_inverse/a2_muller.py#L214), and
[`muller_matrix()`](../../solvers/bem_inverse/a2_muller.py#L228).

The local blocks `v`, `k`, `kp`, and `t` are the exterior/interior combinations
needed by the Müller system. Assembly builds their differences directly.
Radial coefficients use analytic Bessel products; there is no radial sampling.

[`assemble_matrix()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L198)
selects CPU or [CUDA assembly](../../solvers/bem_inverse/modal_cuda.py).
The geometry coefficient workspace is distinct from all three shape/trace bands.

### A3. Geometry + source/receiver positions → modal wave coefficients

Input: current geometry, physical frequency, and source/receiver positions.
Output: incident trace and speed-weighted flux coefficients for both point sets.
These supply the source RHS, receiver evaluation, and reciprocal RHS.

Code: [`point_kernels()`](../../solvers/bem_inverse/a3_waves.py#L67),
using [`WaveArrays`](../../solvers/bem_inverse/a1_geometry.py#L215).
[`_solve()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L130)
requests both sets through Graf/addition-theorem expansions.

### A4. Matrix + source RHS → boundary traces → predicted measurements

Input: `A_f` and source RHS. Factor the matrix and solve for boundary traces.
The stacked trace state contains `u_D` followed by `q`, the speed-weighted
normal flux. Contract the traces with receiver coefficients to obtain data.

Code: [`forward_solve()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L108) calls
[`_solve()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L130) for A1–A4.
It stores factors, forward traces, and the reciprocal RHS in `ModalState`.
The current implementation uses CPU LU even when matrix assembly uses CUDA.

[`solve_frequencies()`](../../solvers/bem_inverse/forward_batch.py#L10)
dispatches the selected forward function over active frequencies and collects
predictions and retained forward states. The stage's local
[`evaluate`](../../solvers/bem_inverse/fit_stage.py#L77) calls it and then B5.
The current modal service uses paired point sources and receivers.

## B. Predicted measurements + geometry directions → residual Jacobian

### B5. Predicted data + observations → normalized real residual

Subtract observed data from predictions, normalize each frequency by its
observed-data norm with a small denominator floor, and apply square-root weights.
Stack real parts followed by imaginary parts to obtain `r`.

The loss is half the squared length of `r`. Default weights average the
normalized frequency losses equally; declared noise enables different weights.

Code: [`normalize()`](../../solvers/bem_inverse/b5_residual.py#L21),
[`b5_residual.evaluate()`](../../solvers/bem_inverse/b5_residual.py),
and [`CumulativePolicy._config()`](../../solvers/bem_inverse/policy.py#L96).

### B6. Optimizer coordinates → complete-trial geometry derivatives

Input: current `c_m` and the normal-harmonic update coordinates `a_i`.
Output: one Cartesian coefficient velocity for each optimizer coordinate.
The coordinates and the stored Cartesian coefficients are different quantities.

Code: [`SpectralProjectedUpdate.prepare()`](../../solvers/bem_inverse/geometry_update_methods/spectral.py#L154)
defines coordinates and builds velocities using centered finite differences of
projected geometry. [`batched_projection()`](../../solvers/bem_inverse/geometry_update_methods/spectral.py#L88)
evaluates the base and all positive/negative moves together.

The differentiated map includes normal displacement, arclength reset, and
projection. This is a geometry finite difference, not a finite difference of
the forward solver. Validity decisions are checks around the smooth trial map.

[`make_update()`](../../solvers/bem_inverse/geometry_selection.py#L7) selects
`SpectralProjectedUpdate` with batched preparation on the requested device,
together with `spectral.geometry_update`. Its method-owned `Prepared` record
retains the derivatives, the base projection and the N-point grid. Other
geometry methods own their preparation and measurements in their respective
files. Ordinary curve tools stay in [`continuation/geometry.py`](../../solvers/bem_inverse/continuation/geometry.py).

### B7. Geometry derivatives + forward/reciprocal traces → complex data Jacobian

Convert each B6 coefficient velocity into its normal-displacement weight,
including the boundary-speed factor. Solve the reciprocal RHS using the
existing Müller factors, then contract forward traces, reciprocal traces, and weights.

Code: [`ModalMuller.derivative()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L307),
[`_contract()`](../../solvers/bem_inverse/forward_solvers/modal_muller.py#L286), and
[`hadamard()`](../../solvers/bem_inverse/b7_data_jacobian.py#L30).

The reciprocal RHS is solved as a batch of receiver columns once per frequency
and derivative evaluation. Those reciprocal traces serve all update directions;
the code does not repeat the reciprocal solve separately for each `a_i`.

### B8. Complex data Jacobian → residual Jacobian → Gauss–Newton quantities

Apply the same normalization, square-root weights, and real/imaginary stacking
as B5 to obtain `J`. Combine `J` with `r` for gradient `g`, and with itself
for the Gauss–Newton matrix `H_GN`.

Code: the stage's local [`linearize`](../../solvers/bem_inverse/fit_stage.py#L99),
[`b8_gauss_newton.residual_jacobian()`](../../solvers/bem_inverse/b8_gauss_newton.py)
and [`curvature()`](../../solvers/bem_inverse/b8_gauss_newton.py).
The live stage loop uses `J`, `g`, `H_GN`, `D`, `lambda_trial`, `a_raw`,
`a_bounded` and `a_used`. Checkpoint fields keep their old names.

## C. Jacobian → LM proposal → accepted stored geometry

### C9. Gauss–Newton quantities → LM proposal

Use `g`, `H_GN`, damping metric `D`, and damping parameter `lambda` to solve
the damped linear system. Its answer is a proposed change in local update
coordinates, not yet a new stored curve.

Code: [`damping_matrix()`](../../solvers/bem_inverse/c9_lm.py#L42)
and [the proposal solve](../../solvers/bem_inverse/c9_lm.py).
The default metric uses the diagonal of `H_GN` with a positive floor.

### Geometry update. LM proposal → finite geometry trial

Bound the proposal, then try successively halved steps. Construct each trial
curve by normal displacement, spectral arclength reset on the N-point grid, and
restriction to the stored Cartesian band. The centered increment subtracts the
base projection.

Code: [`control_step()`](../../solvers/bem_inverse/geometry_update_methods/__init__.py),
[backtracking and the passed `geometry_update`](../../solvers/bem_inverse/fit_stage.py#L253),
[`spectral.geometry_update()`](../../solvers/bem_inverse/geometry_update_methods/spectral.py#L228),
and [`arclength_quadrature()`](../../solvers/bem_inverse/geometry_update_methods/spectral.py#L56).

The centered construction preserves the original stored curve for a zero step.
The active method directly calls [`check_area`, `check_speed`, and
`check_intersection`](../../solvers/bem_inverse/checks.py#L211) on the final
trial curve. The moved curve is not checked: refitting and centring change
it, so only the final curve is the boundary that is used. Area uses Fourier
coefficients; speed and intersection checks use sampled nodes. Sampled checks decide validity without certificates.

The optional [`certified_spectral`](../../solvers/bem_inverse/geometry_update_methods/certified_spectral.py)
method retains certificate decisions and sampled fallback in its own file.

There is no second, doubled-grid refit and no grid-agreement check (D7, Q12).
Output is `c_trial`, in the same stored Cartesian band. Exhausted backtracks
lead to a larger damping value and a newly computed proposal.

### C11. Trial curve → evaluation → accept or reject

Evaluate the trial curve at the stage's working resolution (A1–A4, then B5).
Accept it when its loss is lower than the current loss; otherwise halve the
step. Nothing is re-solved at a finer resolution, and there is no gain margin.

Code: [the acceptance test](../../solvers/bem_inverse/fit_stage.py#L294) and
[`production_nondecreasing()`](../../solvers/bem_inverse/checks.py#L324).
An accepted trial curve replaces the current shape in
[the C12 state commitment](../../solvers/bem_inverse/fit_stage.py#L311).

Numerical failures are different: a failed or non-finite physics evaluation
of the trial curve stops the stage.

### C12. Accepted step → damping / stopping / continuation

Update damping, invoke accepted-state callbacks, and normally rebuild the
geometry directions and Jacobian at the accepted boundary. Check loss,
gradient, step, iteration, and enabled stagnation conditions.

Code: [accepted-state handling](../../solvers/bem_inverse/fit_stage.py)
and [`c12_iteration.py`](../../solvers/bem_inverse/c12_iteration.py) and
[`checks.py`](../../solvers/bem_inverse/checks.py).
Work limits and numerical refusals can also interrupt earlier operations;
they are not checked only after acceptance.

If this stage continues, repeat the chain with the accepted coefficients,
reusing available results. If it finishes normally or exhausts its stage
quota, the runner may advance; other stopping outcomes can end fitting.

[`CumulativePolicy.operations()`](../../solvers/bem_inverse/policy.py#L125)
and [`tail()`](../../solvers/bem_inverse/policy.py#L185) choose subsequent stages.
The runner carries the accepted boundary forward, applying scheduled cleanup
or storage resizing when required.

Stages may change active frequencies, `M`, `K_geometry`, and the physics
resolution profile, which determines `K_trace`. After `fit()` returns, the
benchmark checks the endpoint independently in
[`experiments/benchmark/audit.py`](../../experiments/benchmark/audit.py#L62).

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

`FitStage.nodes` is the working modal resolution token, eight times `K_trace`,
on this path. It is not the geometry-update sample count. The endpoint audit
also uses the profile's refined token.
The coefficient workspace is another resolution setting, separate from `K_trace`.

The optimizer now calls its curvature `H_GN`; geometric normals remain
separate. Historical serialized fields still use `matrix` and `gradient`.
The kernel assembly's local `q` is not the trace-state flux `q` defined above.

## How agents should use this frame

Answer the requested question briefly: identify its location in this chain, state
what information enters and leaves, and explain why the next part needs it.
Link the relevant function; do not reproduce the whole chain for every question.

Keep geometry construction, the working physics resolution and loss acceptance
(C11), and the endpoint audit after the fit distinct. Keep `M`, `K_geometry`, `K_trace`,
and the coefficient workspace distinct.

Use this as the shared explanation structure, not as a frozen implementation
specification. Confirm current code when answering; line anchors describe the
checkout above and can move as implementation changes.
