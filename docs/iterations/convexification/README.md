# Carleman convexification and auxiliary fields

Track 13 of the [architectural backlog](../../reports/architectural_experiment_backlog_2026-10-11.md).

[CVX-001](CVX-001_results.md) is a completed formulation study: primary-paper
assumptions, actual TG-002 information, interface regularity, exact data-completion
counterexamples, finite-basis conditioning and interface readout. Its
[registered component checks](CVX-001_plan.md) passed all five gates.

The supported opportunity is a frequency/source-differentiated log field whose
second-derivative interface jump cancels. Tail closure and boundary observability
remain unresolved. No published theorem inspected here establishes global
recovery for the unchanged paired sharp-interface benchmark. CVX-001 ran no
inverse and changed no solver default.

The next discriminating question is a coercivity/closure argument for that
differentiated field and its explicit tail, under a stated observation operator.
An exact interior tail is oracle information, not an admissible inverse input.

[CVX-002](CVX-002_results.md) implements a joint unknown reference field and
real coefficient, with H2/H3 regularization and matched spatial-weight controls.
The [registered screen](CVX-002_plan.md) used augmented full Cauchy data on four
TG-002 targets. Two low-contrast arms optimized; six arms stopped at sampled
log-field qualification. The low-contrast images improved overlap but failed
the original paired-data physical check. Both met the declared grid-refinement
trigger. The completed 57-grid reruns improve coefficient RMSE slightly but
worsen overlap and all-contour geometry; they do not establish grid convergence.
This is an isolated prototype, with no maintained solver default change.
