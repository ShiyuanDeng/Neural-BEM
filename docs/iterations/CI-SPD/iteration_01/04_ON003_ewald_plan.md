# ON-003 — Fourier-factorized Müller forward feasibility

Prepared 2026-10-05. Approval status: **APPROVED FOR EXECUTION**.
Execution status: **STARTED — preparation**. This is a separate, bounded eight-hour
forward experiment. No numerical experiment was performed while writing it.

User launch: `Go ON-003 using docs/iterations/OVERNIGHT_AGENT_TRACKS.md.`
Start: **2026-10-05 01:49:12 UTC**. Deadline: **2026-10-05 09:49:12 UTC**.
No new variants after 07:49:12 UTC; closeout reserve begins 08:19:12 UTC.
Existing checkout: `feature/shape-frequency-continuation`, as explicitly instructed
by the launch guide. ON-001 runs concurrently; OS locks serialize numerical work.

## Question and authorization boundary

Can a reusable geometry-to-Fourier map, a matched local correction and
frequency-dependent diagonal propagation reproduce the maintained modal
Müller service at a useful complete cost?

Approval of **ON-003** covers only the fixed-state forward diagnostics and
conditional derivative checks below. It does not authorize inverse fitting,
new scenes, regenerated observations, a new branch/worktree, ON-001 or ON-002.
Use the existing checkout and preserve every reference implementation and
failed result. Any later inverse qualification needs its own approved ID and
the unchanged TG-002 benchmark contract.

The [integration review](../../cleaned_interfaces/iteration_30/02_proposals/02_gaugal_restructuring_integration.md)
explains the broader proposal. The [existing speed comparison](../01_results.md)
does not establish a timing advantage for this new operator. The
[ON-001 inverse plan](../../cleaned_interfaces/iteration_30/03_plan.md) remains
a separate route.

## Scope and fixed inputs

Read `experiments/benchmark/README.md` first. Use physical units, source
strength, paired acquisition and exterior/interior wavenumbers from `Problem`.
No truth geometry enters the selection below.

Select four fixed curves deterministically before the first numerical call:

1. The sealed TG-002 start, from
   `results/validation/cleaned_interfaces/TG-002/inputs/start.json`.
2. The last saved accepted curve in PC-001 M1 `kite__c4`.
3. The last saved accepted curve in PC-001 M1 `hook__c13.3`.
4. The last saved accepted curve in PC-001 M1 `aphex_twin__c13.3`.

The three saved-state roots are
`results/validation/cleaned_interfaces/PC-001/M1/runs/<case>/`. Inspect stage
JSON files containing `history`; admit only rows with `iteration > 0` and a
stored `coefficients` object. Select the row with largest
`work.work_units`, then largest `work.seconds`; break any remaining tie by
lexicographic filename and then iteration. Do not select a proposed/rejected
curve, repair a curve, or replace a failed-case endpoint with an easier state.
Stop preparation if the required row or provenance is unavailable.

Before measurement, commit a manifest listing the exact source file, row,
stored band, physical length unit, source-file SHA256 and canonical extracted
coefficient SHA256 for each curve. Also pin the numerical source commit,
dependency versions and frozen TG-002 input seal. Preserve the selected
coefficients without resampling or cropping.

Evaluate each curve at material ratios **0.5, 4 and 13.3**, with the frozen
**0.25 and 2.5 GHz** real and damped observations: four curves × three ratios
× four observation configurations = **48 fixed forward configurations**.
These are operator diagnostics on TG-002 states, not 48 new inverse scenes.
Use all 24 paired source/receiver channels. Retain the stored geometry band;
test trace cutoffs 64 and 128, with the existing refined profile when needed.
Declare unresolved references separately rather than counting them as passes.

## Mathematical contract before implementation

For outgoing real-frequency Helmholtz use the limiting-absorption convention
`a = |q|^2 - (k+i0)^2`. The finite-time identity is

```text
1/a = (1-exp(-tau*a))/a + exp(-tau*a)/a,
G_near(r) = integral_0^tau exp(k^2*t-r^2/(4*t))/(4*pi*t) dt.
```

The removable value of the first quotient at `a=0` is `tau`. The flat
single-layer near symbol is
`erf(sqrt((omega^2-k^2)*tau))/(2*sqrt(omega^2-k^2))`, with consistent branches
and grazing value `sqrt(tau/pi)`. It is a finite-tau formula. For propagating
modes it involves `erfi` and grows as tau increases; it does not converge to
the full outgoing symbol as tau tends to infinity. Record the near/far
cancellation and amplification rather than invoking that invalid limit.

Fix the dimensionless split choices before measurement. Let `k_star` be the
largest physical absolute wavenumber among both media, all three material
ratios and the four observation configurations. Test
`xi/k_star = 1, 2, 4, 8`, with the report's convention `tau = 1/(4*xi^2)`. Each choice uses one fixed
Fourier grid/window across those frequencies and materials so its geometry
maps can actually be reused. Report the expense of this common-grid choice.

The scalar arclength-weighted formula `B* D B` is not directly the package's
flux-coordinate matrix. The current unknown is `(u, J*d_n u)`, `J=|gamma'|`,
in a fixed parameter Fourier basis. Derive the operator in that basis using
an unweighted trace moment map and an unnormalized normal-flux map involving
`n*J=R*gamma'`, or write the exact speed/mass transformations explicitly.
Preserve all four Müller blocks, jump identities, exterior/interior
differences and the Maue cancellation. Record orientation and conjugation
conventions. A single-layer result alone does not qualify the transmission
system.

### Matched outgoing far treatment

Ordinary sampling of `1/(|q|^2-k^2)` on a real Cartesian grid is not an
outgoing quadrature. Use one declared matched construction for this first
experiment: smoothly truncate the **far kernel itself**,

```text
F_tau,R(r) = w_R(r) * (G_outgoing(r) - G_near,tau(r)).
```

Choose a radial smooth cutoff which is identically one through every relevant
source/target separation plus a 1 mm buffer for derivative probes. Its
transition width is `8*sqrt(tau)` and its shape is fixed across cases. Record
the radii and the exact cutoff formula in the pre-measurement manifest. Compute
the radial Fourier transform with qualified one-dimensional quadrature and
stable small-r cancellation. On the required separation interval,
`G_near + F_tau,R` is exactly the outgoing kernel before numerical truncation.
The Fourier multiplier and the local correction must come from this same
construction. A compactly supported far kernel does not retain the simple
untruncated exponential multiplier; do not substitute one for the other.

Use a square period strictly greater than twice the far support radius and
derive the Fourier-series normalization explicitly. The initial grid is
128×128; one declared refinement to 256×256 is allowed. Record the resulting
physical q spacing and cutoff. Double the radial quadrature order once when
its own error is unresolved, independently of the spatial Fourier grid.
Stop a configuration if the declared ceilings cannot qualify it. No silently
growing grids, pole shifts, periodic-image approximations or arbitrary
replacement damping are allowed.

This is motivated by, but is not a verbatim implementation of,
[Vico–Greengard–Ferrando](https://arxiv.org/abs/1604.03155).
[Beylkin–Kurcz–Monzón](https://www.colorado.edu/amath/sites/default/files/attached-files/be-ku-mo-2009.pdf)
provides a directly relevant outgoing Helmholtz split and shell-quadrature
reference. Poisson/strongly elliptic
[symbol-based asymptotics](https://arxiv.org/abs/2604.11436) and the
[modified-Helmholtz construction](https://arxiv.org/abs/2606.28865) motivate
local corrections but do not prove their unqualified continuation to this
radiating transmission problem.

### Local part and representation claims

Begin with the exact finite-tau flat single-layer symbol. Derive its first
nonzero curved-boundary correction before testing curved states. Any claimed
`O(curvature^2*tau)` behavior must identify the operator, relative/absolute
norm, smoothness assumptions and density-band dependence. It is not a bound
for every Müller block. Derive the double/adjoint-layer and Maue terms
separately, including the relevant trace limits.

Do not impose a reach floor or clip shapes to suppress close interactions.
Estimate omitted nonlocal near interactions against a declared tolerance;
`reach >= 2/xi` alone is not sufficient. A single permitted near fallback
evaluates the complete near remainder, including close nonlocal portions,
with independently refined boundary quadrature and correct singular/trace
treatment. Its cost is part of the candidate. It may be used once for a
failed local approximation, not as an unlimited repair sequence.

An intermediate implementation may evaluate the geometry moment integrals by
boundary quadrature while retaining modal unknowns and Galerkin testing.
Label that result **boundary-collocation-free, quadrature-based**. It is not
the current package's stronger coefficient-only operator. A coefficient-only
variant must compute the retained moments from Fourier coefficient algebra
with independently qualified truncation; boundary quadrature may then serve
as a reference, not a hidden execution path. Report both claims separately.

## Staged qualification and first-result decisions

### Stage A — algebra and single layer, maximum 90 minutes

Freeze the derivation, cutoff, normalization, quadrature orders, density
probes and source hashes. Test flat evanescent, propagating and grazing
symbols, finite-tau cancellation and analytic circle single-layer modes.
Compare both real and damped wavenumbers. These controls are necessary before
timing a curved kernel.

If the outgoing split, branches or flux-basis mapping remain unresolved at
the cap, close **FORMULATION_INCOMPLETE**. Do not proceed to fitting or call
a real-frequency pole regularization the same physics.

### Stage B — curved maps and all blocks, maximum 150 minutes

Build the four fixed-curve maps and the local correction, starting with the
circle and kite. Then include hook and aphex regardless of their outcome.
Compare individual block actions against the maintained modal assembly,
using every scalar Fourier basis column plus four fixed-seed complex
combinations. Compare absolute errors normalized by a declared reference
operator scale as well as relative errors; small difference blocks must not
produce misleading relative ratios. Keep exterior/interior cancellation
visible in the receipt.

Use complex128/float64 for the primary comparison. At cutoff 64, scalar maps
have 129 columns and the two-trace system has 258 unknowns; at cutoff 128
these are 257 and 514. A stacked two-map representation must be identified as
such. Cap persistent candidate arrays at 2 GiB and peak candidate allocation
at 4 GiB on each device. Batch Fourier rows to respect these limits, and
count transfers, allocation and synchronization. Do not exceed 80% of the
available device memory or spill silently to CPU. A configuration exceeding
the declared limits is an explicit resource-limited result.

### Stage C — full forward screen, maximum 60 minutes

Use the candidate complete Müller matrix with the current dense solve and
the current qualified Graf incident/receiver maps. This isolates the new
boundary operator. Reuse factors for all paired source and reciprocal
right-hand sides exactly as the maintained service does. Source/receiver
work remains in complete evaluation timing; the first experiment does not
claim to remove it.

An initial per-frequency field difference <=1e-6 is a screen only. Promotion
requires the existing <=1e-5 gates at <=0.5 GHz and <=1e-7 gates above 0.5 GHz,
comparison at the relevant refined trace cutoff, and a qualified independent
reference on the same fixed curve. Use the analytic circle reference where
available and independently resolved nodal comparisons for the other states.
Reference work counts against the global budget; unresolved references are
reported, never silently relaxed. Low linear-system residual alone is not
an accuracy qualification.

### Stage D — one continuation selected by evidence, maximum 90 minutes

| First screen | Declared next action | Terminal interpretation |
|---|---|---|
| All required fields pass and complete evaluation is faster | Freeze the forward variant; qualify derivatives below and repeat timings | Qualified forward candidate; possible derivative-qualified candidate |
| Circle passes but thin/concave cases fail local approximation | Apply the single complete-near quadrature fallback, including nonlocal interactions | Accurate hybrid local treatment, or local approximation rejected |
| Fourier-grid/radial quadrature error dominates | Apply only the one declared grid/order refinement | Qualified at greater cost, or Fourier representation unresolved |
| Only damped configurations pass | Retain the damped component and real-frequency failure evidence | DAMPED_ONLY; no transmission-service replacement |
| Required accuracy passes but total cost is worse | Finish matched timings and stop | ACCURATE_BUT_SLOWER at present trace dimensions |
| Required accuracy exceeds grid/memory/time ceilings | Preserve the complete failed configuration | ACCURACY_OR_RESOURCE_LIMITED |
| Full fields pass but derivative qualification fails | Retain forward evidence; stop inverse readiness claim | FORWARD_ONLY |

The near fallback and grid refinement address different diagnosed errors;
each may occur once, within this same 90-minute cap. Do not restart the clock
or search combinations until one appears favorable. Passing only at xi=8
is retained as evidence, but does not establish the suggested low-xi economy.

Derivative qualification is conditional on a fully qualified forward
variant. Differentiate both moment maps, both test/trial factors and the
local correction. In particular `delta(n*J)=R*V'`; the derivative of the
single-layer weighted map is insufficient. Keep grid, cutoff and tau fixed
during probes. Compose with the maintained complete finite-update Cartesian
velocities. Compare paired field-Jacobian actions with the existing Hadamard
derivative and independently rebuilt finite differences at 1e-6, 1e-7 and
1e-8 m, using the existing 1e-3 relative Jacobian/complete-trial criterion
with an absolute floor for near-zero directions. An unqualified derivative
does not invalidate an otherwise qualified forward result, but blocks
inverse integration.

## Timing, success criteria and closeout

Reserve the last 90 minutes for qualification summaries, matched timings,
regression checks and reporting. The global ceiling is eight hours including
implementation, failed checks, reference work and closeout. Stop starting
new variants after hour six. No simultaneous benchmark jobs.

Record cold setup, per-curve maps, per-frequency diagonal/local work, all four
block assembly, source/receiver maps, factorization, forward/reciprocal
solves, derivatives, transfers and total forward-service time separately.
Measure the actual four-frequency panel and the 19-frequency real catalog
on qualified curves when the budget permits; do not multiply component
timings to invent an amortized speedup. Use one cold and three warm repeats
on the qualified circle and kite configurations, identical precision and
device/worker settings, and include setup in a separately reported first-use
total. Optional 19-frequency measurements may not replace missing accuracy
checks on the fixed 48-configuration panel.

The proposed performance target is at least 2x faster median complete
all-frequency forward-service time on the qualified panel, with no lost
field qualifications. This is an ambition, not a forecast. An accurate
factorization, an unfavorable crossover, or a precise failure mechanism is
also a completed feasibility result. No inverse speed or recovery claim
follows from any of these outcomes.

Store implementation and evidence under the appropriate package/experiment
boundary: orchestration and reference selection in `experiments/benchmark/`,
reusable experimental operators in `solvers/bem_inverse/` behind an opt-in
interface. Do not change defaults. Store results under
`results/validation/cleaned_interfaces/ON-003/`, including derivation,
selection/hashes, settings, arrays, phase receipts, failed configurations,
accuracy tables and matched timing tables.

After each experiment batch, validate then commit/push its implementation,
documentation and complete or failed evidence to the configured remote;
verify remote HEAD and final working-tree status. The closeout must state
the achieved representation claim: coefficient-only, quadrature-based
boundary-collocation-free, or incomplete. A successful forward/derivative
prototype leads to a separately proposed TG-002 inverse experiment; it does
not release an overnight inverse rewrite under ON-003.
