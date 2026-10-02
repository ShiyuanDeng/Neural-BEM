# Incident source model qualification

This follow-up provides reusable incident-field and shape-JVP components for the
cleaned interface. It uses the archived Fresnel incident measurements to qualify
an outgoing Helmholtz expansion, then compares the qualified 1–4 GHz subset with
the original line-source inverse. Results and every tested order are in
[the result record](../../results/fresnel/source_qualification/README.md).

## Physical assumptions and calibration data

The [2001 experimental description, §§1–6](https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf)
identifies double-ridged horn antennas, a fixed emitter with target rotation,
source/receiver radii of 720/760 mm with ±3 mm uncertainty, and measured incident
fields on the receiver circle. It explicitly leaves estimation of the incident
field in the target region to the inversion procedure. Source labels therefore
represent rotations of one physical antenna; the present calibration averages
the 36 incident measurements at each equivalent relative receiver angle.

The earlier [Belkebir et al., 2000, §5.2](https://www.fresnel.fr/perso/belkebir/Articles/Belkebir_JEMWA_00.pdf)
uses forward-direction incident calibration and discusses the horn directivity,
polarization approximation and differences at 1 GHz. Those observations motivate
a directional source model, but do not identify its coefficients for these data.

The importer already conjugates the original exp(+iωt) measurements once. All
new calculations use exp(−iωt), outgoing Hankel functions, metres and physical
wavenumbers. Calibration accepts **incident samples only**. Measured scattering,
true cylinder locations/radii and reconstructed boundaries never select source
coefficients or source order. The fixed target audit box is [−80,80] mm².

A receiver measurement is interpreted as a scalar field sample, following the
existing inversion model. The incident dataset alone does not independently
separate transmitter radiation, receiver directional response, three-dimensional
polarization effects or phase-centre offsets. Numerical qualification below is
conditional on that measurement interpretation.

## Source model and exact derivatives

For source centre `s` and inward boresight `β`,

```text
u(x) = Σ[m=−M..M] a_m (i/4) H_m^(1)(k |x−s|) exp(i m(arg(x−s)−β)).
```

Each term satisfies the source-free Helmholtz equation away from `s` and is
outgoing. The source singularity remains outside the target region. Rotating
source and target coordinates rotates the field and its Cartesian derivatives
consistently. No angular correction is simply multiplied onto a Green function
without preserving its spatial derivatives.

For unrotated `F_m=(i/4)H_m^(1)(kr)exp(imθ)`, the
[NIST Hankel recurrences, §10.6](https://dlmf.nist.gov/10.6) give

```text
∂x F_m = k/2 (F_(m−1) − F_(m+1))
∂y F_m = ik/2 (F_(m−1) + F_(m+1)).
```

Applying these identities again gives the Hessian and exactly
`trace(Hessian) = −k²u`. Boresight phase factors are held fixed under spatial
variation. The finite-aperture synthetic control uses a sum of five displaced
line sources, independently of this fitted basis; the
[Hankel addition theorem, §10.23](https://dlmf.nist.gov/10.23) explains why a
compact external aperture can be represented this way outside its support.

## Portable interfaces

| API | Contract | Cleaned-interface use |
|---|---|---|
| `multipole_basis(points, source, k, order, boresight=...)` | Returns basis values `(P,2M+1)`, gradients `(P,2M+1,2)` and Hessians `(P,2M+1,2,2)` | Supply incident Dirichlet/Neumann traces and their shape derivatives |
| `fit_multipoles(A, incident, rcond=1e-8)` | Column-scaled complex SVD; records coefficients, rank, singular values and inverse map | Calibrate once outside the inverse, then freeze coefficients |
| `evaluate_fit(points, source, k, fit)` | Evaluates field, gradient and Hessian | Incident-field protocol independent of a chosen boundary representation |
| `solve_multipole_forward(curve, sources, receivers, k, coefficients, epsr=3)` | Experimental single-boundary Müller/Kress RHS adapter, `(sources,receivers)` output | Reference implementation for accepting externally supplied incident traces |
| `linearize_multipole_forward(result, direction)` | Exact discrete shape JVP with fixed source coefficients/material | Reference for a cleaned-interface incident-trace JVP hook |

The adapter reuses production matrices and `_directional_operators`, including
its primal consistency checks. It first constructs an ordinary line-source
result as an operator reference; that result's RHS is replaced for the new solve.
This incurs an extra factorization and is an experimental integration choice.
For velocity `V`, it uses

```text
δu = ∇u·V
δ(∂n u) = n·(Hessian(u) V) + δn·∇u
A δq = δb − δA q
δEsc = δC q + C δq.
```

The reusable source APIs contain no truth information or optimizer policy. The
adapter currently covers one lossless TM interface with fixed positive real
material parameters; it is not a qualified multi-component, lossy or TE adapter.
The cleaned interface should retain its existing solver and accept these traces
through an incident-field protocol. Production defaults are unchanged.

## Bounded model selection and continuation checks

Two successive, preserved experiments were run:

1. Full observed aperture (49 angles), fixed orders M=0…6.
2. Near-boresight receiver window 120…240° (25 angles), first M=0…3; a
   separate fixed ceiling audit extends only 4–8 GHz to M≤6.

Two interleaved angle sets are withheld separately. The smallest order within
15% plus 0.002 of the minimum validation error is preferred. A separate blocked
boresight test withholds 165…195° for the local window. This corresponds to
source ray angles about ±8°, covering the audit box's relevant central rays.
The wider first experiment used a larger blocked interval, 150…210°; its failure
is retained rather than reinterpreted as success.

Audits combine the field and gradient scaled by `1/k`, so different physical
units are not added. Checks cover withheld incident error, blocked-angle
prediction, target changes between folds/orders, and the exact operator-norm
bound for a 0.1% complex incident perturbation. The 0.1% value is a sensitivity
scenario, not an experimentally estimated noise level. Rotational sample
variation is recorded separately.

The initial incident-only position audit exposed a common phase uncertainty.
For a receiver-radius perturbation `δR`, calibration approximately adds
`exp(−ikδR)` to the target field, whereas receiver propagation adds
`exp(+ikδR)`. A separate full-BIE control perturbs **both consistently**, without
fitting scattering: two fixed circles, four ±3 mm radius perturbations and both
incident datasets. Its maximum predicted-data change is below 0.029% through
4 GHz. The original raw phase-sensitive failures remain in the record.

The 4 GHz extension chooses the qualifying **full-rank M=4** model. M=5 has
slightly better angular prediction but only ten retained dimensions for eleven
coefficients at the fixed SVD cutoff. Its result is preserved and is not used
in the geometry inverse. M=6 is also rank deficient. This prevents the extension
from quietly equating a truncated coefficient map with identified parameters.

## Identification limits and retained failures

Small local-field changes do not imply that antenna coefficients or the
unmeasured radiation pattern have been identified. For example, the 1 GHz
M=3 coefficient map has condition number about 1.12×10⁵; a 0.1% data perturbation
can change coefficients by 10%, while the target field/gradient bound is 0.253%.

There is also a direct finite-sample obstruction. At M=25 the unrestricted
source expansion has 51 complex coefficients and only 49 distinct receiver
locations. Its sampling matrix has a nontrivial nullspace. The archived witness
changes the audited target field/gradient by 10% while changing incident samples
by less than 9×10⁻¹⁰ relatively. It uses large coefficients and is **not** a
proposed antenna model; an independently justified aperture or radiated-power
bound could exclude it. The witness shows precisely which prior is needed for
unrestricted physical identification.

The M≤6 ceiling does not qualify 5–8 GHz. Their smallest blocked-target changes
across the tested orders are approximately 7.7%, 10.6%, 72.6% and 43.5%, versus
the 5% criterion. This closes the present branch experiment at 4 GHz. Further
measured-data work belongs in the cleaned interface and needs an explicit
receiver/source response contract or justified physical aperture constraint;
it should not promote a better fit on the measured arc into a unique source
field claim.

## Reproduction

From the repository root, using the existing EMNerf Python environment:

```bash
export PYTHONPATH=solvers:.
export OPENBLAS_NUM_THREADS=1
python -m pytest -q experiments/fresnel/test_fresnel2001.py experiments/fresnel/test_multipole_sources.py
python -m experiments.fresnel.qualify_sources
python -m experiments.fresnel.audit_source_ceiling
python -m experiments.fresnel.qualify_position_pair
python -m experiments.fresnel.qualify_position_pair --fourth-frequency
python -m experiments.fresnel.compare_qualified_source --maximum-frequency 1
python -m experiments.fresnel.compare_qualified_source --maximum-frequency 3
python -m experiments.fresnel.compare_qualified_source --maximum-frequency 4
python -m experiments.fresnel.summarize_source_qualification
```

The 4 GHz command reuses the checked 1–3 GHz prefix, verifies its data,
calibration and numerical-core hashes, and evaluates the new fourth stage.
The public inputs are the already archived text measurements. No ignored binary
checkpoint is needed. Figures, compressed diagnostics, results and source/input
hashes are stored together; per-run hashes retain the earlier driver versions.
