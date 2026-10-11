# Carleman convexification and auxiliary fields

Track 13 of the [architectural backlog](../../reports/architectural_experiment_backlog_2026-10-11.md).

[CVX-001](CVX-001_results.md) is a completed formulation study: primary-paper
assumptions, actual TG-002 information, interface regularity, exact data-completion
counterexamples, finite-basis conditioning and interface readout. Its
[registered component checks](CVX-001_plan.md) passed all five gates.

The supported opportunity is a frequency/source-differentiated log field whose
second-derivative interface jump cancels. Tail closure and boundary observability
remain unresolved. No published theorem inspected here establishes global
recovery for the unchanged paired sharp-interface benchmark. No inverse was
run and no solver default changed.

The next discriminating question is a coercivity/closure argument for that
differentiated field and its explicit tail, under a stated observation operator.
An exact interior tail is oracle information, not an admissible inverse input.
