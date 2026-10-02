# Two-layer TM forward model

This isolated implementation adds a **Sommerfeld layered Green function** to
the existing Müller/Kress boundary solver. Air occupies y>0, soil occupies
y<0, one smooth dielectric interface is entirely buried, and sources and
receivers lie strictly in air. Permeability is equal across all materials.
The returned field is the object's contribution in air, with the flat-interface
background excluded. Source strengths are one; columns enumerate sources.

The repository already had `experiments/support_certificates/layered.py`, a
Sommerfeld kernel and volume-integral numerical screen. This extension reuses
its spectral feature representation and transmitted/reflected kernels, adds
analytic boundary-normal derivatives, resolves both real branch points for
lossless media, and couples those smooth corrections to the existing Kress
matrix. It does not modify the historical volume screen or production solver.

## Formulation

The convention is exp(-i omega t), with outgoing `G=i H0^(1)(k r)/4` and
passive `Im(k)>=0`. Write `ba=sqrt(ka²-xi²)` and `bg=sqrt(kg²-xi²)`, with
nonnegative imaginary parts. For a soil source y and soil target x, the
reflected Green function is

```text
Gref(x,y) = i/(4 pi) integral_R
    [(bg-ba)/(bg+ba)] / bg
    exp(i xi (x1-y1) - i bg (x2+y2)) dxi.
```

For a target x in soil and source y in air,

```text
Gtrans(x,y) = i/(2 pi) integral_R
    exp(i xi (x1-y1) - i bg x2 + i ba y2) / (bg+ba) dxi.
```

These expressions follow by horizontally Fourier-transforming Helmholtz,
selecting outgoing/decaying vertical solutions, and matching field and normal
derivative at y=0. Their per-mode coefficients give the usual Fresnel values
`R=(ba-bg)/(ba+bg)` and `T=2ba/(ba+bg)` for incidence from air.

On the buried boundary, let Sref, Dref, K'ref and Nref be the smooth reflected
single layer, source-normal double layer, target-normal derivative, and mixed
normal derivative. Arc-length weights are included. The existing free-space
Müller matrix receives the correction

```text
Ahalf = Afree + [[-Dref,  Sref],
                [-Nref, K'ref]].
```

The unknowns remain the total Dirichlet and outward-normal traces. Incident
boundary traces come from Gtrans and its analytic target derivative. By
reciprocity, the air receiver operator is `[Dtrans, -Strans]`. The reflected
kernel is smooth because the entire buried boundary has positive separation
from the plane. Consequently its derivatives need no extra singular
quadrature; the existing Kress splitting handles the free-space singular part.

Both signs of horizontal frequency are integrated on the positive axis.
Gauss–Legendre nodes are mapped by sin² on subintervals ending at the air and
soil real branch locations, twice the larger real wavenumber, and a finite
spectral cutoff. Order and cutoff are independent numerical controls.

## Why this is not a WGF implementation

The ranked document offers both Sommerfeld and windowed Green function routes.
The reusable layered kernel made the Sommerfeld route directly testable through
an independent volume formulation. [Bruno and Pérez-Arancibia, 2017, §§3–5](https://arxiv.org/html/1703.01034v1)
derive a different method: free-space operators on truncated material
interfaces, slow-rise windows and a planar-solution correction. Simply applying
a window to the present spectral integral would not implement that method.
We therefore report **spectral-cutoff convergence**, not WGF window-size
convergence, and make no claim to the paper's super-algebraic window estimates
or speed comparisons. A future WGF arm needs its own interface unknowns and
planar correction, then can use this solver as a reference.

## Validation and limits

```bash
export PYTHONPATH=solvers:.
OPENBLAS_NUM_THREADS=1 python -m pytest -q experiments/halfspace/test_sommerfeld.py
python -m experiments.halfspace.run
```

The run used `/home/drdeng/miniconda3/envs/EMNerf/bin/python`, CPU and one BLAS
thread. Tests cover equal-media free-space kernels, Fresnel continuity and
energy flux, all normal derivatives by finite differences, full-space Kress
equivalence, zero object contrast, interface-crossing rejection, and an
independent volume-integral disk convergence control.

`results/halfspace/qualification.json` contains two buried-circle cases:
lossless soil/object relative squared wavenumbers 6/3, and passive complex
values `(6+0.48i)/(3+0.24i)`, with `ka=15.70796 m^-1`, radius 25 mm and center
depth 150 mm. Both quadrature order and cutoff are varied. Independent scipy
adaptive integration on the raw spectral axis checks a transmitted Green
function entry. Independent Lippmann–Schwinger volume discretizations use
fractional boundary cells and a local equal-area-disk singular integral.
They solve the full multiple-scattering volume system, not a Born model.

These are forward controls for a separated smooth disk. They do not qualify
near-contact geometry, rough interfaces, unequal permeability, TE, multiple
buried inclusions, broad frequency/contrast ranges, shape derivatives or
inversion. The volume comparison is an independently convergent numerical
reference, not an exact solution. Fixed spectral cutoff must be refined for
shallower geometry or shorter source/interface distances.
