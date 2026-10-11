# CVX-002 Joint reference field reconstruction

Pre-registered 2026-10-11 before numerical runs. The user explicitly requested
implementation and numerical results following CVX-001. This is an isolated
augmented-data feasibility experiment on TG-002 targets. It is not a recovery
claim under TG-002's unchanged paired information contract. No branch/worktree
is created; unrelated work in this checkout is preserved.

## Hypothesis and intervention

Jointly reconstructing the unknown reference log field V and smoother finite
frequency differences can recover a useful coefficient image without supplying
any true interior field. A Carleman-type spatial weight might improve the
coefficient/shape result relative to the identical unweighted algorithm.
Those are separate questions. Failure of the weighted arm does not falsify the
regularity identity or every convexification method.

Let v_j=log(u_j/u0_j)/k_j², V=v_last and z_j=v_j−V. Each z_j has the same H3
interface regularity gain as the differentiated field, without estimating
frequency derivatives. Define F_j=Δv_j+k_j²∇v_j·∇v_j+2a_j·∇v_j.
The equations F_j+c−1=0 with one real coefficient c are exactly equivalent to
the difference equations F_j−F_last=0 and the last-frequency anchor equation.
The interior V remains unknown. At each update freeze one factor of the
quadratic gradient term, solve a regularized linear least-squares problem for
all complex fields and common real c, then use a data/PDE/regularization-only
backtrack. No global convexity/contraction theorem is asserted for this scheme.

Store v_j for sparse algebra. Regularize V with a discrete H2 norm and normalized
secants (v_j−V)/(t_j−1), t_j=(k_j−k_min)/(k_max−k_min), with a discrete H3 norm.
The discretization explicitly retains zeroth, first, second and third Cartesian
derivative terms. It does not impose H3 on the rough reference field V.

## Data and frozen controls

Preselected cases: circle at contrasts 0.5, 4 and 13.3, then c_shape at13.3.
Use the prescribed centered 65 mm circle as the initial coefficient and field;
no localization or multistart. Frequencies are the first three real catalog
entries: 0.25, 0.375, 0.5 GHz. Source0 is the existing ring source at (6,0) in
the 50 mm length units. The auxiliary box is [−2.4,2.4]² in these units.

Generate noiseless full Dirichlet and outward-normal data on that box from the
frozen TG-002 targets using CPU nodal Kress at N512/N1024. This is explicitly
additional acquisition, permitted only as a formulation feasibility study.
No interior truth field enters the optimizer. Normal derivatives are analytic
derivatives of the exterior layer potentials. Reference refinement gates:
1e-7 relative total field, 1e-6 relative normal derivative. Initial disk fields
are exact Mie expansions; qualify them against independent nodal fields on
the boundary. Preserve all failed qualifications. The original paired data
are reserved for post-fit physical prediction checks.

Screen grid: 41×41 (6 mm spacing). Twelve nonlinear updates maximum, one start,
no tuning. Matched weight arms: log span0 and4, weight proportional to
exp(span ψ), mean normalized to one; ψ is the normalized inverse-squared
distance to x0=(3.4,0), an exterior point. Spatial derivative/cell quadratures
use the same dimensionless coordinates in both arms. PDE rows are normalized
by frequency count. Boundary Dirichlet values are fixed; normal derivative
penalty is10. Fixed regularization coefficients: H2(V)=1e-5,
H3(secants)=1e-6, coefficient L2=1e-7. The coefficient regularizer is centered
at the known background1, not at truth. Do not tune these using shape scores.
Coefficient estimates remain real but unconstrained in the solve; report
out-of-material-range values. The fixed occupancy threshold handles both
above- and below-background contrast. Clipping for display changes no threshold.

Each linear system uses sparse normal equations after column scaling;
require normalized stationarity <=1e-7. On a numerical failure, the declared
fallback is scaled LSMR at atol=btol=1e-9, maxiter2000; retain its status.
Backtrack over1,1/2,1/4,1/8,1/16,1/32 against the actual nonlinear objective.
Stop if no decrease, relative step<=1e-5, the iteration cap, nonfinite values,
or wall cap. Save every attempted/accepted update and linear solve receipt.
Per-arm wall cap300 seconds, checked between solves/evaluations; an atomic
sparse or forward solve may overrun the check. Complete screen cap30 minutes,
also enforced by a launch watchdog with a signal handler preserving failures.

## Qualification and outputs

Before inversions: verify frozen inputs; check analytic normal derivatives
against centered off-surface differences; check Mie cutoff refinement; check
nonlinear residual Jacobian using random real/imaginary field and real-c
directions; verify full-rank Dirichlet elimination and an independently formed
linear residual. Gate derivative checks at1e-5 relative and refinement at1e-8.
Boundary phase winding, minimum |u/u0| and phase continuity must be recorded.
An unqualified/nonzero-winding log is a formulation stop, not quietly unwrapped
through an inconsistent branch.

Pre-run independent-review clarifications: check nonzero complex Dirichlet
elimination and every residual block; normalize the weight by its applied
interior-point mean; check initial-grid plaquette winding and use deterministic
phase unwrapping. A sampled field ratio below1e-8 fails log qualification.
The data generator checks support enclosure. Qualification failures stop only
the affected case, and fit failures only the affected arm; other preselected
cells continue, preserving all failures. These are qualification requirements,
not tuning based on reconstruction truth.

For each endpoint record objective, PDE residual, boundary-normal mismatch,
linear stationarity, weight range, field minimum, raw coefficient range,
coefficient RMSE, occupancy IoU, area error, and sampled contour RMS/Hausdorff.
Compare to the initial circle. Truth enters only data generation and post-fit
scoring. Field positivity/nonvanishing inside the inferred model is diagnostic,
not a proof that the true field is zero-free.

Keep every threshold contour for raster scoring. For the independent physical
check, take the largest closed contour (declared single-object readout), uniform
arclength resample and Fourier band16. Report discarded components and smoothing
error. Invalid/open/self-intersecting readouts fail visibly. Evaluate all19
original real paired frequencies at N256/N512; if their relative disagreement
exceeds1e-5, try N1024 once. Record unqualified results without recovery claims.
This output physics and geometry check is not TG-002's certified endpoint audit.

Conditional refinement: only if some arm improves sampled RMS by>=25% and
IoU by>=0.10 over start while all its forward/linear qualifications pass, rerun
that exact case/arm on57×57 (4.286 mm spacing), without retuning or selecting
an intermediate iterate by truth. This is a resolution check of a declared
development result, not held-out evaluation. Otherwise stop after the screen.

Root owns implementation and measurements. Separate agents reviewed the joint
reference-field equations, data adapters, and literature/discretization scope.
Keep the prototype in experiments/convexification, outside maintained solver
defaults. Save launch source archive/hashes, inputs, complete receipts, arrays,
plots and failures. After each completed or failed run validate, commit and
push its evidence to the existing branch; verify push and working-tree status.
