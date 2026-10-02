# TE transmission, shape derivatives, and passive loss

The opt-in CPU implementation is `solvers/gpr_bem_kress/polarization.py`.
It extends the existing Kress difference operators to weighted normal traces.
The established lossless TM solver remains an independent comparison path.
This implementation has one smooth closed interface, exterior line sources,
and separated receivers in homogeneous full space. It is not a layered-ground
or a three-dimensional Maxwell solver.

## Conventions and the conductivity sign

The convention is `exp(-i omega t)` and `G_k = i H_0^(1)(kr)/4`, as recorded
in `gpr_bem_kress/conventions.py`. Maxwell–Ampère gives

\[
 \nabla\times H=(\sigma-i\omega\epsilon)E
 =-i\omega(\epsilon+i\sigma/\omega)E.
\]

Consequently passive media use `epsilon_c = epsilon + i sigma/omega` and
`k = omega sqrt(mu epsilon_c)`, with positive real part and nonnegative
imaginary part. The outgoing factor `exp(ikr)` attenuates. The Hankel
asymptotic form is given in [NIST DLMF §10.17](https://dlmf.nist.gov/10.17).
`passive_permittivity` and `passive_wavenumber` implement this convention.

The older package-local `Material.wavenumber` uses the opposite conductivity
sign. Its high-level TM builder already rejects nonzero conductivity. That
guard remains in place; the new experiment never calls that material method.
It passes independently computed passive wavenumbers to the kernel builder.

## Weighted transmission system

Let the normal point out of the inclusion, and let `[v]=v_o-v_i`. For TE,
`u=H_z`, `[u]=0`, and `[a partial_n u]=0`, where `a=1/epsilon_c`.
For nonmagnetic TM, `u=E_z` and one can set `a_o=a_i=1` after canceling the
common permeability. Define `rho=a_o/a_i`; thus TE has
`rho=epsilon_i/epsilon_o`, and TM has `rho=1`.

The unknowns are the total exterior traces `U=u_o` and `Q=partial_n u_o`;
the interior normal trace equals `rho Q`. Summing exterior and interior
Calderón equations gives

\[
 A\binom UQ = \binom{u^{inc}}{\partial_n u^{inc}},\qquad
 A=\begin{pmatrix}
 I-K_o+K_i & V_o-\rho V_i\\
 -T_o+T_i & \tfrac{1+\rho}{2}I+K'_o-\rho K'_i
 \end{pmatrix}.
\]

The off-surface scattered field is `D_o U - S_o Q`. The code forms the
weighted blocks as `DeltaV+(1-rho)V_i` and
`DeltaKp+(1-rho)Kp_i`, and reuses the analytically canceled `DeltaT`.
There is no subtraction of independently discretized hypersingular matrices.

Individual `V_i`, `K_i`, and `Kp_i` use the periodic Kress logarithmic rule.
For complex `k` in the passive quadrant, the same split applies: the
coefficient of `log r` in `H_n^(1)(kr)` is proportional to `J_n(kr)`;
`log k` enters the smooth diagonal remainder. This follows from the
[integer-order Bessel expansions in DLMF §10.8](https://dlmf.nist.gov/10.8).
No branch cut is crossed in the passive tests.

## Derivation of the boundary jumps

These are derived here from differentiating the scalar transmission
conditions. The general strategy of characterizing a shape derivative by
another scattering problem is also established for Maxwell transmission by
[Costabel and Le Louër, Part II, §6](https://arxiv.org/abs/1105.2479)
and [Hettlich (2012)](https://doi.org/10.1002/mma.2548).
Those Maxwell results are context, not a substitute for the following
scalar sign derivation.

Deform the interface by `x -> x+t h n`; primes below denote Eulerian field
derivatives at fixed physical locations. Differentiating continuity gives

\[
 f=[u']=-h[\partial_n u]=(\rho-1)hQ.
\]

The normal variation is `n'=-partial_s h t_hat`, so differentiation of the
weighted flux condition gives

\[
 g=[a\partial_n u']=-h[a\partial_{nn}u]
                      +(\partial_s h)[a\partial_su].
\]

On the boundary, `partial_nn u=-k^2 u-kappa partial_n u-partial_ss u`.
The curvature term cancels because the original weighted flux is continuous.
Tangential derivatives of the shared trace are equal. Hence

\[
 g=(a_o-a_i)\partial_s(h\partial_sU)
       +(a_ok_o^2-a_ik_i^2)hU.
\]

For nonmagnetic TE, `a k^2=omega^2 mu` is equal on both sides and the
last term cancels, also with conductivity included in `epsilon_c`. For TM,
`f=0` and `g=(k_o^2-k_i^2)hU`.

In code use `b=g/a_i`:

\[
 b=(\rho-1)\partial_s(h\partial_sU)
                  +(\rho k_o^2-k_i^2)hU.
\]

Writing the unknown derivative traces on the exterior as `U',Q'`, the
interior traces are `U'-f` and `rho Q'-b`. Substitution in the same Calderón
equations yields the second solve

\[
 A\binom{U'}{Q'}=
 \binom{(\tfrac12 I+K_i)f-V_i b}
       {T_i f+(\tfrac12 I-K'_i)b}.
\]

The primal LU factorization is reused for all sources and directions.
`T_i f` is evaluated by the Maue identity in this sign convention,

\[
 T_i f=\partial_sV_i\partial_s f+k_i^2 n\cdot V_i(nf).
\]

The periodic Fourier differentiation matrix supplies `partial_s`. There is
no geometry finite difference in this derivative. The field derivative is
`D_o U'-S_o Q'` on the unchanged reference boundary and at fixed receivers.
Normal velocity can contain multiple columns; the returned array has axes
`(direction, source, receiver)`.

## Validation evidence

Run with the project Python environment and `OPENBLAS_NUM_THREADS=1`:

```sh
python experiments/polarization/run_validation.py
python -m pytest -q pytest/gpr_bem_kress/test_polarization.py
python experiments/polarization/run_lossy_atlas.py
```

The independent circle series solves the two modal transmission equations
using Bessel/Hankel functions; it shares no quadrature or BIE operator code.
The circle check covers TE `epsilon_r=4`, exterior `kR={1,5,15}`, and
`N={64,96,128,192,256}`. At `N=256`, the largest relative L2 error is
`5.13e-14`. At `kR=15`, `N=64` is deliberately underresolved; all node
counts and errors are retained in `results/polarization/validation.json`.

Twenty random combinations of harmonics 0–8, ten each on a circle and an
ellipse, compare the second-solve derivative with centered geometry FD.
The worst relative error is `1.71e-7` at step `5e-5`; the three decreasing
steps expose the expected second-order FD trend rather than a single tuned
step. Passive complex-wavenumber circle checks cover 0.1, 0.5, and 1 GHz;
background `epsilon_r=6`, `sigma={0,1,10,50}` mS/m; target
`epsilon_r=12`, `sigma=5` mS/m; and both polarizations. The worst forward
relative error is `2.65e-14`, and the worst harmonic derivative FD error is
`3.46e-9`. Seven regression tests cover these mechanisms, including passive
attenuation and zero contrast.

The separate conductivity atlas uses a lossless target and records both a
relative spectral threshold and an absolute threshold anchored to the
zero-conductivity spectrum. Loss attenuation can disappear under spectrum
renormalization; interpreting the relative count alone as noise tolerance
would be unjustified. Details and computed counts are in
`results/polarization/README.md`.
