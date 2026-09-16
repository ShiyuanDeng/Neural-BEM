# Neighbour-assisted shape sensing

Follow-up to the calibration-quotient feasibility test. This isolated experiment
asks whether a neighbouring object's benefit survives uncertainty in that
object's position, size, shape, material, and the antenna calibration.

Five arms share the same multioffset measurements and absolute noise:

- Target alone.
- Known neighbour with full multiple scattering.
- Unknown neighbour with full multiple scattering.
- Known neighbour with additive echoes only.
- Unknown neighbour with additive echoes only.

The additive controls have their own correctly matched data and inverse. They
separate calibration-reference effects from changes to physical illumination.

A 63-case prior-only screen selects one candidate for overall information and a
second for interaction-specific gain. Both selections precede nonlinear recovery.
Independent full BIE data, two target/neighbour shape pairs, five noise/gain seeds,
two initializations, and fresh final forward checks support the comparison.

See the [measured report](../../results/experiments/laurent_neighbour_20260916/report.md)
for the results, assumptions, and full reproduction commands.

The code reuses the existing Laurent scattering compiler without editing it or
any production solver. The model is homogeneous, lossless, and two-dimensional;
it is a controlled information experiment rather than a validated field GPR method.
