# Analytic radial coefficients in modal Müller assembly

The maintained routine is `bem_inverse.modal_operator.radial_coefficients`.
Both CPU and CUDA assembly call it. It constructs scalar Chebyshev
coefficients from Bessel products, without a DCT or radial-function samples.
The geometry-dependent arrays remain the existing windowed Chebyshev
recurrences. All series are truncated and evaluated in floating point.

Let \(R\in[0,U]\), \(x=2R/U-1\), \(a=k\sqrt U/2\), and
\(e_n=2-\delta_{n0}\). Write \([f]_n\) for the coefficient of \(T_n(x)\).
An equal-radius specialization of [Graf's addition theorem](https://dlmf.nist.gov/10.23#E7)
gives, for integer \(m\geq0\),

\[
[J_{2m}(k\sqrt R)]_n=e_n J_{m+n}(a)J_{m-n}(a).
\]

Negative orders use \(J_{-r}=(-1)^rJ_r\). In particular,

\[
j_n(k):=[J_0(k\sqrt R)]_n=e_n(-1)^nJ_n(a)^2.
\]

The Green-function split is
\(G_k=P_k\log R+Q_k\), with \(P_k=-J_0(k\sqrt R)/(4\pi)\).
The [Neumann expansion of \(Y_0\)](https://dlmf.nist.gov/10.23#E16)
cancels the logarithmic term analytically and yields

\[
Q_k(R)=C_kJ_0(k\sqrt R)
 +\frac1\pi\sum_{m=1}^{\infty}\frac{(-1)^m}{m}J_{2m}(k\sqrt R),
\qquad C_k=\frac i4-\frac{\gamma+\log(k/2)}{2\pi}.
\]

Consequently the two basic coefficient arrays are

\[
p_n(k)=-\frac{j_n(k)}{4\pi},\qquad
q_n(k)=C_kj_n(k)+\frac{e_n}{\pi}
 \sum_{m=1}^{\infty}\frac{(-1)^m}{m}J_{m+n}(a)J_{m-n}(a).
\]

To form the derivative arrays without differentiating rounded coefficients,
use \(P'_k=k^2(J_0+J_2)/(16\pi)\) and define
\(S_k=Q'_k+(P_k-P_k(0))/R\). The Bessel recurrences give

\[
S_k=k^2\sum_{m=0}^{\infty}d_mJ_{2m}(k\sqrt R),\qquad
d_0=-C_k/4-1/(16\pi),\quad d_1=-C_k/4+1/(32\pi),
\]
\[
d_m=\frac{1+2(-1)^m/m}{8\pi(m^2-1)},\qquad m\geq2.
\]

This follows by differentiating the Neumann expansion and using
\(J_0(z)-1=-2\sum_{m\geq1}J_{2m}(z)\) to form the removable quotient.
All resulting even-Bessel terms use the same product coefficients above.
The six material-difference arrays represent

\[
P_o-P_i,\quad Q_o-Q_i,\quad P'_o-P'_i,\quad
Q'_o-Q'_i+(P_o-P_i)/R,\quad
k_o^2P_o-k_i^2P_i,\quad k_o^2Q_o-k_i^2Q_i.
\]

Primes denote R derivatives. The fourth array is \(S_o-S_i\), since
\(P_o(0)=P_i(0)=-1/(4\pi)\). Thus no numerical differentiation, singular
subtraction, or polynomial division is required. The constant coefficient of
\(P_o-P_i\) is reconstructed from \(p_0=-\sum_{n\geq1}(-1)^np_n\), avoiding
subtraction of nearly identical constant Bessel products at small arguments.

Integer Bessel orders are evaluated by scaled backward Miller recurrence.
The [generating-function](https://dlmf.nist.gov/10.12#E1) normalization is
\(J_0(a)+2\sum_{n\geq1}(\sigma i)^nJ_n(a)=\exp(\sigma i a)\), where
\(\sigma\) is chosen opposite to the sign of \(\operatorname{Im}a\) so that
the exponential grows. The recurrence and product sums use NumPy extended
precision, including extended-precision constants and the mapped argument.
Only the final six arrays are rounded to complex128 for CPU/CUDA assembly.
Qualification used Linux extended precision with a 64-bit significand;
`radial_work_precision_bits` records the platform's actual working precision.
The tests independently compare the recurrence with high-precision Bessel
values, including orders below float64 underflow.

The internal Neumann cutoff has a factorial/geometric truncation majorant
for both Q and S. Coefficient decay controls
the outer Chebyshev cutoff. The routine refuses unresolved or non-finite
coefficients and never falls back to sampled construction. These checks do
not certify the total floating-point error, geometry truncation, assembled
matrix, or solve. In particular, strong damping can make evaluation near a
small function value ill-conditioned even when the coefficient error is tiny
relative to the coefficient norm.

Diagnostics report `radial_coefficient_method="analytic_bessel"`,
`radial_points=0`, the internal term count, and the retained degree.
`amplification` now divides the largest coefficient l1 norm by the largest
Chebyshev-weighted RMS of the six functions; its scope is explicitly recorded.
It is not the former sampled-peak ratio. The old scalar value evaluator is
retained for reference tests, while the archived DCT control is confined to
the [AC-001 validation driver](../../experiments/benchmark/analytic_radial_validation.py).

See the [plan](../iterations/CI-SPD/AC-001_plan.md) and
[validation results](../iterations/CI-SPD/AC-001_results.md).
