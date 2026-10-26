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

**Physics context**:
The object that holds one physics' execution settings, geometry caches and
counters. Its forward solve and derivative use it; `make_backend` returns the
context with its forward solve.
_Avoid_: service, backend

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

**Gauge**:
The choice of parameterisation of a boundary, meaning the speed at which the
parameter moves along it. Many coefficient vectors describe the same boundary
in different gauges. The arclength gauge has constant speed.
_Avoid_: parameterisation drift (for the gauge itself)

**Speed unevenness**:
How far the speed |z'| varies along the curve, relative to its mean. It is
zero in the arclength gauge.
_Avoid_: level, non-uniformity

**Centred update**:
The geometry update that keeps the stored coefficients and adds only the
change of the arclength refit caused by the step. A zero step returns the same
coefficients. Any existing speed unevenness is kept.

**Uncentred refit**:
The geometry update that stores the arclength refit of the moved boundary
directly, so every accepted curve is in the arclength gauge, up to the crop to
the storage band.

**N-update**:
The geometry update that moves each point along the unnormalised normal
N = -i z' (length |z'|) and optionally slides it along the tangent z'. Both
amounts are real series of the update band, so the step is exact in
coefficients before the crop.
_Avoid_: naive update, normal push

**Level penalty**:
A term added to the data loss that grows with speed unevenness. It acts on the
unevenness of the curve itself, not on its change, so it is nonzero for a
zero step.
_Avoid_: soft constraint, regulariser

**Slider**:
The geometry update that turns a requested normal push into one linear
coefficient step. The step moves the boundary normally and keeps the relative
speed change equal everywhere, so the speed unevenness before the step is kept.
_Avoid_: tangential correction

## Research

**Direction**:
A family of proposed changes intended to address a particular limitation.
One unsuccessful construction does not necessarily close the whole direction.

**Experiment**:
A bounded comparison that answers a specific question about a direction.
Its conclusion applies to the construction and conditions actually tested.
