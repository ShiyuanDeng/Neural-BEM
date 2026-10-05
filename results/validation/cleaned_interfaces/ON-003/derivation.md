# ON-003 fixed mathematical contract

Reference: immutable `reference_HEAD_sources.tar.gz`, exported from 6f2c1408.
The four retained curves and physical split scales are in `manifest.json`.
This document records the derivation before numerical qualification.

## Units, trace coordinates and normalization

Write the counterclockwise physical curve as gamma(t), t in [0,2pi),
N(t)=R_clockwise gamma'(t) and J=|gamma'|. The unknown is (u,p),
p=J partial_n u. Conversion from package coordinates by length_unit_m
leaves p invariant; k_physical=k_package/length_unit_m. No arclength
weight belongs in the scalar map for V acting on p.

For q=2pi*l/L, define normalized moments

A[q,n]=(1/(2pi)) integral exp(-i q.gamma(t)) exp(i n t) dt,
N_j[q,n]=(1/(2pi)) integral N_j(t) exp(-i q.gamma(t)) exp(i n t) dt,
C[q,n]=sum_j (-i q_j) N_j[q,n].

Fhat(q)=2pi integral_0^R1 r w(r) (G_out(r)-G_near(r)) J0(|q|r) dr.
D(q)=Fhat(q)/L^2. The series kernel is sum_q D(q) exp(i q.(x-y)).
The even NxN storage uses fftfreq modes; unpaired Nyquist planes carry zero
weight, so the retained Fourier truncation is reciprocal. This convention
is fixed before measurement for both declared grids.
The Fourier test is exp(-i m t)/(2pi); the source integration is unnormalized.
Thus Vfar=2pi A^H D A, Kfar=2pi A^H D C, Kprimefar=2pi C^H D A.
The H here conjugates the geometry map only: D is not conjugated at damped k.
A scalar speed-weighted B^H D B would use the wrong flux coordinates.

Maue in these parameter coordinates gives
Tfar[m,n]=-m*n*Vfar[m,n]+2pi*k^2*sum_j N_j^H D N_j[m,n].
The split T components are the *linear split of the full Maue form*.
Neither compact far nor finite-time near separately satisfies the homogeneous
Helmholtz equation. Their heat/cutoff forcing terms cancel on the required
separation interval; the separate Maue components must not be claimed to
equal independently differentiated hypersingular layers without those terms.
The sum implements the full Maue operator.

Take exterior minus interior for V,K,T,Kprime and assemble
[[I-deltaK, deltaV],[-deltaT,I+deltaKprime]]. Universal jumps cancel
in the differences; retain the displayed identities. On a circle Kprime=K.
This is the maintained modal_operator.py convention, not a new transmission law.

## Split, outgoing shell, and compact support

For a=q^2-(k+i0)^2 the identity 1/a=(1-exp(-tau*a))/a+exp(-tau*a)/a
has removable near value tau. Real k uses outgoing Hankel G=i H0^(1)(kr)/4.
The spatial near kernel is integral_0^tau exp(k^2*t-r^2/(4t))/(4pi*t) dt.
With x=r^2/(4tau), z=k^2*tau, it equals
(1/(4pi)) sum_p z^p/p! E_(p+1)(x). At r=0 both full and near have the
same logarithmic singularity. Their finite difference at the origin is

i/4 - (EulerGamma+log(k^2*tau)+sum_(p>=1) z^p/(p!*p))/(4pi).

The fixed cutoff is identically one through R0, a conservative coefficient
triangle bound on every boundary separation plus 1 mm. For
s=(r-R0)/(8 sqrt(tau)), w=exp(-1/(1-s))/(exp(-1/s)+exp(-1/(1-s)))
on (0,1); w=1 below and 0 above. R1=R0+8 sqrt(tau), L=2.1 R1.
This smooth cutoff is flat to all orders at both endpoints. Its radial
transform is computed directly, with no real-grid pole samples or added
absorption. The period excludes image supports on the entire required
boundary separation interval. Existing Graf maps handle sources/receivers;
they are not evaluated by this compact-support kernel.

At any required boundary separation, near+far=G_out before spatial Fourier
truncation. The cutoff changes the multiplier: exp(-tau*a)/a is not used
as a substitute for this transform. The same fixed geometry/grid/tau serves
both media and all four frequencies in a split choice. k_star includes
sqrt(13.3), damping and the actual background material in the frozen Problem.

## Flat and curved local terms

The exact flat arclength single-layer symbol is
S_tau(omega)=erf(sqrt((omega^2-k^2)*tau))/(2 sqrt(omega^2-k^2)).
The branch-independent removable value is sqrt(tau/pi). Propagating real
modes give erfi and grow with tau; the outgoing full symbol
1/(2 sqrt(omega^2-(k+i0)^2)) has positive imaginary value i/(2 beta).
The far symbol is the difference, including this cancellation. A grazing
full line symbol is singular; only its finite near value is tested there.

For locally constant curvature kappa, physical arclength s, and a smooth
arclength density exp(i omega s), chord squared is
s^2-kappa^2*s^4/12+O(s^6). The first nonzero single-layer correction is

kappa^2/48 integral_0^tau exp(-(omega^2-k^2)t)/(2 sqrt(pi*t))
                      * (12t-48t^2 omega^2+16t^3 omega^4) dt.

This is an asymptotic absolute symbol correction for single layer, under
small kappa sqrt(tau), bounded derivatives of curvature and resolved density
band. Relative O(kappa^2*tau) needs a lower bound on the leading symbol;
no uniform relative estimate is claimed at cancellations. For a circle
convert both arclength symbols to the package V by dividing by radius.
It is not an all-block error bound or a globally valid diagonal on a
nonuniform-speed curve. Nonlocal near pieces are retained by the fallback.

For the same local orientation N_source.(x-y)/J_source=-kappa*s^2/2+O(s^3).
Knear=-2 Gprime N_source.(x-y), so the linear-curvature arclength symbol is
-kappa/4 integral_0^tau exp(-(omega^2-k^2)t)/(2 sqrt(pi*t))
                              * (2-4t omega^2) dt.
The adjoint has the same leading term for constant curvature; on a variable
curve it is the transposed kernel, not an independently copied diagonal.
Higher terms depend on derivatives of curvature and density. Hypersingular
terms are kept in the Maue combination above; the k^2 normal-dot near term
and differentiated single layer must both be retained. Differentiating only
V would not qualify T or the shape derivative. No isolated flat formula
qualifies the transmission operator.

## Independent circle controls and complete near fallback

For radius a the exact outgoing parameter-coordinate diagonal actions are
V_n=i*pi/2 J_n(ka) H_n^(1)(ka),
K_n=i*pi/2 ka J_n'(ka) H_n^(1)(ka)-1/2,
T_n=i*pi/2 (ka)^2 J_n'(ka) (H_n^(1))'(ka).
The jump is independent of k and disappears in the Muller difference.
Exact moment A[q,n]=(-i)^n J_n(a|q|) exp(i n arg(q)); C=a*d_a A.
The far diagonal follows these analytic moments. Checking diagonals of all
basis columns can reject a full operator, but cannot qualify untested
Cartesian-grid off-diagonal entries. Passing diagonals alone is a screen.

The complete circle near correction uses logarithmic quadrature with
P=-J0(kr)/(4pi), log(4 sin^2(theta/2)) Fourier coefficients -1/|n|,
and the smooth remainder. Its zero-separation smooth value is
(-EulerGamma+log(4tau/a^2)+sum_(p>=1)z^p/(p!*p))/(4pi).
Knear=r^2*d_R Gnear and Hnear=a^2*k^2*cos(theta)*Gnear; Tnear=-n^2 Vnear+Hnear.
Quadrature counts 2048 and 4096 compare independently. This exact-near
control separates a failed flat/curvature model from a failed far grid.
It is quadrature-based and boundary-collocation-free, not coefficient-only.

## Derivative contract (conditional, not yet implemented)

Fixed tau, cutoff and Fourier grid: delta A includes -i q.V in the phase;
delta N=R_clockwise V', delta C includes both this normal-flux change and
phase change. Differentiate both test and source factors, near remainders,
and the complete source/receiver service. Compose with the maintained
finite-update Cartesian velocities; changing only speed-weighted V is
insufficient. Derivatives are authorized only after full field qualification.
