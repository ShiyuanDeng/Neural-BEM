# Inverse shape reconstruction

Recovering a scatterer's boundary from measured scattered fields, using a
boundary-element forward solver inside a damped Gauss–Newton fit. Symbols
(`c`, `a`, `M`, `K_trace`, `J`, `H_GN`, …) are defined in
[the chain map](docs/reference/inverse_information_chain.md#fixed-terminology).

## Language

**Pipeline**:
A named choice of forward solver and geometry update.
_Avoid_: recipe, backend

**Policy**:
A named choice of stage schedule and optimizer options, run with one pipeline.
_Avoid_: schedule, controller

**Stage**:
One part of the fit with fixed active frequencies, update band, storage band,
working resolution and work quota.
_Avoid_: phase

**Working resolution**:
The physics resolution at which a stage solves and judges every curve.
_Avoid_: production resolution, refined resolution

**Iteration**:
One pass of the fit loop; it ends with at most one accepted curve.
_Avoid_: step

**Trial curve**:
The curve built from one proposed step, not yet accepted.
_Avoid_: candidate

**Accepted curve**:
A trial curve whose loss is lower than the current curve's; it becomes the
current curve.
_Avoid_: committed state, qualified curve

**Forward solve**:
One physics solve at one frequency, giving predicted measurements and
boundary traces for a curve.
_Avoid_: physics evaluation

**Evaluation**:
A curve together with its predictions, residual and loss at the working
resolution.
_Avoid_: objective, production evaluation

**Geometry update**:
The method that turns a step in update coordinates into a checked trial curve.
_Avoid_: projection, trial method

**Endpoint audit**:
A comparison of fields and Jacobian at two resolutions on the curve a fit
returns; the benchmark runs it, the fit does not.
_Avoid_: qualification, resolution check
