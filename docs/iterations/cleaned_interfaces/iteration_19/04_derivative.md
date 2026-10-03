# FM-002 reduced gradient

For one source and one frequency, the declared objective is

`F(z,q) = 1/2 ||C(z)q-d||² + lambda(z)/2 ||A(z)q-b(z)||²`,

where `lambda = tau * median(receiver row squared norms)` and all observations
and acquisition coordinates are fixed. Ordinary traces are `u=A^-1 b`.
With `H=A^-H C^H`, `r=C u-d`, and `v=(H^H H+lambda I)^-1 r`, the minimizing
field is `q*=u-A^-1 H v`. The paired case uses the corresponding single
receiver and scalar denominator independently for each source.

FM-001 evaluated the reduced loss correctly, but its update direction used
only `W dr`, discarding the shape dependence of W. This is not generally the
gradient of the reduced loss. The saved C warmup is a concrete counterexample:
the old gradient and the full loss gradient have cosine -0.9987.

At the minimizing field the derivative with respect to q vanishes. Therefore
the complete shape differential, with `e=Cq*-d` and `f=Aq*-b`, is

`dF = Re[e^H (dC) q*] + lambda Re[f^H ((dA)q* - db)]`
`     + 1/2 ||f||² d(lambda)`.

There is no dq* term. This does not permit dropping the dC, dA, db or penalty
terms. The implementation reconstructs the production discrete kernels with
the existing Kress reverse-geometry primitives, fixes q*, and differentiates
this scalar. It checks production A/C agreement and relaxed-field stationarity
(including an absolute signal-scale roundoff allowance near zero residual).
Source traces, normals, speed, quadrature and analytic diagonal terms are
inside the reverse graph. SciPy special functions have analytic reverse rules.

The returned position and native-first-derivative covectors are contracted
with the complete Fourier coefficient tangent supplied by the geometry update.
The ordinary projected spline update supplies its existing, independently
qualified central-difference geometry tangent. This is a complete derivative
of the actual discrete objective composed with that tangent, not a claim of
exact continuum differentiation or a new exact geometry map.

The receiver median is the average of the two middle values for an even count,
matching NumPy. It is differentiated with locally fixed ordering. The objective
is only piecewise smooth at ordering changes/ties. Near/direct kernel branches
are also locally fixed and independently checked against finite differences.

The optimizer uses this complete gradient with the old positive matrix
`(W J_data)^T (W J_data)` as a curvature approximation. That matrix is not
advertised as the full relaxed-residual Jacobian or exact Hessian. Actual trial
acceptance still checks the recomputed reduced loss at two numerical resolutions.
Ordinary fitting retains its original `J^T r` gradient and update behavior.

The corrected gradient needs one additional LU backsolve batch per frequency
and one CPU reverse-assembly pass, independent of the number of shape directions.
H and receiver rows are cached on the immutable-in-use forward state. Existing
CPU/CUDA factors serve the backsolve and retain their documented OOM fallback.
Reverse graphs are processed one frequency at a time to bound peak memory.

Qualification covers complete-loss directional finite differences, paired/full
observations, real/damped frequencies, several penalties, noncircular shapes,
frequency normalization, CPU/CUDA factor paths, and the archived C descent
regression. The sealed campaign adds saved-state gradient-refinement checks.
