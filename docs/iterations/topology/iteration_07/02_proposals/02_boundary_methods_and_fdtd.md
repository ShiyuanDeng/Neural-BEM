# Are the current failures intrinsic to boundary methods? What FDTD would change

2026-09-12. Author: Codex. Records the user's question following the
[independent TOP-008/TOP-009 review](01_independent_review.md).
Status: scientific assessment and suggested comparison order. No matched
BEM/FDTD comparison or material-grid inverse was run for this assessment.

The current evidence does not establish an intrinsic failure of boundary
methods. Most suspected causes concern optimizer stopping, derivative quality,
observation sensitivity, or our chosen geometry coordinates. FDTD could remove
particular boundary-quadrature difficulties. A material-field inverse could
remove our explicit component and Fourier restrictions. Those are different
interventions and should be evaluated separately.

## What the current evidence establishes

The [saved-evidence audit](../../../../../results/validation/topology/TOP-009-20260912-review/evidence_audit.json)
finds 13 loss-change stops and one iteration-limit stop among the 14 retained
stage-4 rungs. The final K=9 reconstruction has training relative error
`8.7878e-5`, below the controller's `0.003` threshold, but matched boundary
error `11.849 mm` and worst holdout relative error `1.4154`.

These observations establish poor recovery under the recorded procedure. They
do not certify a local minimum, unique inversion, or a boundary-integral
forward-model defect. The near-zero response error at the supplied truth
establishes forward consistency; it does not establish stable recovery of the
shape from the observations. TOP-010's proposed stopping/stationarity audit
therefore remains relevant with either forward solver.

## Separate the solver from the geometry unknowns

| Suspected cause or restriction | Would changing only BEM to FDTD remove it? |
|---|---|
| Early stopping, damping/scaling problems, or inaccurate finite-difference derivatives | No automatic remedy. The optimizer and derivative implementation still require validation. |
| Small training residual with wrong geometry; weak sensitivity or non-uniqueness | The same physical observations contain the same information under a consistent forward model. Discretization changes can affect the numerical objective, but do not add measurements. |
| Fourier bandwidth and the topology optimizer's polar-angle gauge | These remain when FDTD receives the same Fourier shapes. Changing to a material field is a separate representation change. |
| Close-boundary quadrature and resolution-dependent clearance restrictions | FDTD avoids boundary-integral quadrature. It must still resolve gaps, curvature and material interfaces on its grid. |
| Explicit component birth, split, merge and death | A material-grid inverse can change connectivity through its field variables without this particular event controller. FDTD alone does not change the controller. |

The existing radius floor, gauge and unsupported-topology rules are properties
of this implementation, not universal restrictions on all boundary methods.
The [architecture](../../../../current_architecture.md) and
[baseline scope discussion](../../../../baselines/B0_2026-09-10.md#7-representation-scope-the-distinction-that-matters-most)
distinguish the representation policy from the forward solver.

Waveform least-squares objectives can have misleading minima because the data
are oscillatory. This is a broader wave-inversion difficulty: it is documented,
for example, in a seismic transmission setting, independently of our boundary
solver. That literature motivates a possible mechanism; it does not diagnose
our saved state as cycle-skipped or locally minimal.
[Registration-guided least-squares waveform inversion](https://math.mit.edu/icg/papers/EAGE13_RGLS.pdf).

## The stronger alternative: FDTD with a material-field adjoint inverse

Optimizing permittivity or a smooth occupancy field throughout the reconstruction
region would remove the particular Fourier chart and explicit component-event
machinery. It offers a route to different connectivity and more general material
distributions. Meep supports gradients with respect to a material grid over
multiple frequencies, as well as derivatives through smoothed shape
representations. [Meep adjoint documentation](https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/).

This also introduces many more unknowns. Our expectation is that spatial
regularization, initialization and a controlled transition toward distinct
materials would become important; successful recovery is not guaranteed.
An adjoint makes a large parameter count computationally practical, but does not
make those parameters identifiable. Source/excitation count must also be included
in gradient-cost comparisons; an adjoint example's two time-stepping runs should
not be read as two runs for an arbitrary multi-source experiment.

## FDTD has its own derivative and resolution risks

A binary voxel mask changes in discrete cell jumps. A small shape perturbation
can change no material cells, followed by an abrupt change as a cell switches
material. Consequently the current `1e-4 m` finite-difference steps cannot simply
be transferred to an arbitrary FDTD grid and assumed to yield usable shape
derivatives. A validated continuous geometry-to-grid mapping is needed.
Meep documents subpixel smoothing specifically for continuously varying shape
responses; its applicability also depends on the material and resolution.
[Meep subpixel smoothing](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/).

FDTD discretizes the surrounding computational region and advances fields in
time. Finer cells constrain the time step through the CFL condition; numerical
dispersion and feature resolution must be checked. This replaces boundary
quadrature costs with a different set of accuracy and cost requirements, rather
than establishing a speed advantage for either method on our cases.
[gprMax numerical guidance](https://docs.gprmax.com/en/latest/gprmodelling.html).

## Suggested comparison order

1. **Independent forward and derivative check.** Compare the supplied truth,
   failed reconstruction and a few nearby shape perturbations using both
   methods. Match 2-D TMz physics, materials, line-source normalization, source
   and receiver locations, frequency/phase conventions, and scattered-field
   subtraction. Establish convergence with BEM resolution and FDTD grid,
   timestep, run duration and absorbing-boundary settings. Compare selected
   directional derivatives as well as responses. Declare an error tolerance
   fine enough to resolve the loss differences being investigated.
2. **Interpret agreement before changing the inverse.** Agreement would weaken
   the claim that boundary quadrature causes the observed failure. Disagreement
   requires resolving numerical accuracy or model matching before treating
   either inverse as evidence about optimizer quality.
3. **Compare inverse representations separately.** If topology flexibility is
   the objective, compare the boundary inverse with a material-grid adjoint
   inverse. Declare the changed unknowns, regularization and initialization;
   attribute results to the complete inverse design rather than solely FDTD.

Broadband time-domain simulation is attractive, but fitting additional
frequencies changes the acquisition. Our frozen benchmark trains at 0.5 GHz
and holds out 1.5 and 2.5 GHz. Any experiment using those holdout frequencies for
training needs a separate comparison and independent evaluation data. Test the
same richer acquisition with BEM to distinguish information gain from solver
choice. Simply retaining the same Fourier samples from an FDTD waveform adds
no observations to the inverse.

This comparison order is a discussion note, not a numerical experiment
contract. A future contract should specify reference states, accuracy gates,
compute limits and fresh artifacts. The present assessment changes neither
the frozen benchmark nor the pending Boundary–BIE brief review.
