# What this experiment can distinguish

The local update has scalar normal amplitude h in an M-band space. The
Cartesian displacement is h*n, where the current normal n need not be
band-limited at M. Multiplication convolves the spectra. Arclength refitting
then composes the moved curve with a nonlinear parameter map. Thus limiting
M does not by itself limit the Cartesian state band or curvature content.
Repeated restricted updates can accumulate geometry outside their nominal
harmonic band; the actual complete-construction derivative already captures
the first-order effect of the refit and projection.

This reasoning does not imply K=2M, that all high-band content is harmful,
or that a Cartesian truncation guarantees bounded curvature. Curvature
also depends on parameter speed; a speed lower bound is essential to such
a guarantee. Sharp true features are an explicit preservation control.

SC-042 tests the following different mechanisms:

- Once versus none: an existing high-band state can impede the subsequent path.
- Boundary versus once: repeated cleanup is needed at later releases.
- Cap versus boundary: preventing accumulation within each stage adds value.
- Star and the four other shapes: the intervention can introduce bias or
  disturb a useful path even when it helps kite.

The cap changes the complete local trial space as well as finite states.
Therefore cap versus boundary does not isolate an identical tangent-space
finite-path effect. This is a strategy comparison with a known distinction,
not a proof that every difference is caused by smoother intermediate curves.

Cleanup is a deterministic reset in the current stored parameterization.
The candidate strategy may temporarily raise loss; all such jumps are saved.
No truth-guided selection or unrecorded reversion is allowed. A later
noise-aware strategy would need its own data-side acceptance of the reset.

The centred construction also deserves a parameterization qualification:
`T_z(0)=z`, not `A(z)`. It preserves the existing zero-step state instead of
resetting it to uniform arclength. The returned unchanged kite has a sampled
maximum/minimum parameter-speed ratio of 3.03. Thus a cutoff in its stored
Cartesian coefficients is parameterization dependent; it is not an intrinsic
curvature-band constraint. `regularity.py` separately evaluates curvature
on a uniform-arclength grid and labels stored-coordinate energy explicitly.
Its diagnostics are post-fit measurements, never policy inputs. The kite's
sharpest point still lies where the nearby truth has about 18 mm radius,
confirming that the 0.093 mm returned radius describes the flank artifact.

The full returned kite comparison makes the distinction quantitative. The
fraction of uniform-arclength curvature energy above order 64 is 95.0% for
none, 32.2% for once, 29.9% for boundary and 30.1% for the K64 cap. The truth
has 0.250% there. Thus even the permanently capped curve retains substantial
intrinsic high-band curvature. This is an evaluation diagnostic; it is not
a new rejection threshold applied to the frozen paths. The boundary and cap
original endpoint audits timed out, with separate SC-045 qualification pending.
