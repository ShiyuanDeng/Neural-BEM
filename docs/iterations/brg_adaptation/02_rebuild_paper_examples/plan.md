# Rebuild the paper's single-component examples

## Status and decisions

Drafted on 17 November 2026 at the coordinator's request while activity 01
runs. **No activity 02 run is authorized or has been started.** The intended
baseline is BRG's obstacle solver with the paper settings, followed later by
our BEM inverse on the exact same data and known contrast.

The request names seven runs and three true shapes. The specified glider,
star and cavity pairs define **six** runs. The seventh case is not identified.
The paper does not provide enough information to define two of the three
true shapes exactly. Those are blockers, not choices to fill by guessing.

Keep the pinned public code and the approved transmission repairs 03/04.
No tuning, grid search, extra initial guesses or noise. Source definitions,
settings and budget must be settled before running this activity.

## Questions and comparisons

Can the public obstacle solver reproduce each fully specified paper case
using its available options? Which settings or geometry definitions cannot
be recovered from the public record? After those gaps are resolved, compare
the recovered boundaries and area errors with Figures 1, 4–7.

This activity does not change `solvers/bem_inverse/` or run our BEM method.
It freezes BRG data, shapes and native timings for that later comparison.
Record raw errors without choosing a new success threshold.

## Run inventory

Here eta denotes the interior/exterior squared-wavenumber ratio. BRG's
`bc.q` must be its positive square root, not eta itself.

| Slot | True shape | eta | Receiver/direction counts | State |
|---|---|---:|---|---|
| 1 | Glider | 0.33 | floor(10k), floor(10k) | Shape fully specified |
| 2 | Glider | 10 | floor(10k), floor(10k) | Shape fully specified |
| 3 | 35-band Cartesian star | 0.9 | floor(10k), floor(10k) | Coefficients missing |
| 4 | Same star | 0.9 | 200, 10 | Coefficients missing |
| 5 | Paper cavity | 0.9 | floor(10k), floor(10k) | Exact geometry missing |
| 6 | Same cavity | 2 | floor(10k), floor(10k) | Exact geometry missing |
| 7 | **Unspecified by the request** | — | — | Coordinator must identify it |

The four shifted-circle examples in section 4.1 concern the volume solver;
they are not silently substituted for slot 7. Example 4's multiple obstacles
remain excluded by the agreed single-component scope.

## Exact shape definitions and their limits

### Glider: complete

Use `geometries.starn` with `nc=8` and 17 real coefficients in its ordering
(constant, eight cosines, eight sines):

```text
coefs = [0.9, 0, 0, 0.18, 0.018, 0, 0.09, 0, 0.09,
         0, 0, 0, 0, 0, 0, 0, 0]
```

The radial series uses those coefficients; Cartesian coordinates are its
radius times cosine and sine of the parameter, from zero to one full turn.
No translation, rotation or additional scaling. This exactly implements
section 4.1's glider. The public helper supplies analytic parameter
derivatives, speed, outward normal and curvature.

### Star: the paper supplies a representation, not a shape

Equation 27 expands **each Cartesian coordinate** in complex Fourier modes
from -35 through +35. It does not give the 71 coefficients for either
coordinate. They must have conjugate symmetry for real coordinates.
This is not the same definition as a radial 35-lobed `starn` curve.

No coefficient table, generator or boundary sample file appears in the
official arXiv source archive: it contains `main.tex`, a bibliography and
figure PDFs only. The exact shape cannot be reconstructed from the text.
Required input: both Cartesian coefficient arrays, or the original generator
and its parameters. A boundary traced from Figure 4 would be an approximate
replacement and needs an explicit coordinator decision and a separate label.

### Cavity: exact shipped shape known; exact paper shape unknown

Section 4.3 identifies its cavity by Figure 7, without a parameterization.
The pinned `geometries.charlie_cavity(j,n)` gives an exact candidate family.
For the activity 01 shipped example, `j=10.2`; its continuous construction is:

```text
rx = 1 - (j-1)/11 + 0.03*(j-1)
ry = 1 - (j-1)/11 + 0.8*(j-1)
X(t) = 20 + rx*cos(t);  Y(t) = ry*sin(t)
a = (1 + 0.7*(j-1))/2
rmax = 400*rx^2/(ry^2-rx^2) + 400 + ry^2
rho(t) = ((X(t)^2 + Y(t)^2)/rmax)^a
theta(t) = 2*a*atan2(Y(t),X(t))
x(t) = rho(t)*cos(theta(t));  y(t) = rho(t)*sin(theta(t))
```

Use one full parameter turn without a repeated endpoint. This is an exact
definition of the **shipped** shape, not proof of the paper shape. Its
300-point bounds are x=[-0.88675,0.71054], y=[-0.82832,0.82832]. Figure 7's
cavity opens upward and occupies a visibly different scale; the shipped
one opens rightward. Neither an exact rotation/scale nor the family
parameter is specified in the paper. Required input: the paper's generator
with all transformations, or its boundary coefficients/samples.

Do not call `charlie_cavity(10.2)` the exact Figure 7 geometry without that
evidence. Rotating or scaling it changes the finite-k problem and is not a
cosmetic plotting decision.

## Paper settings and public-code reach

Paper requirements below come from sections 2, 2.1 and 4; the reach column
comes from the pinned source. These are the intended settings after gaps
are resolved, not changes to the activity 01 shipped example.

| Requirement | Public option or wrapper operation | Reach / gap |
|---|---|---|
| k=1:0.25:30, 117 frequencies | `measurement.kh`, one-frequency RLA calls in order | Reachable; save and resume each frequency |
| Known, real material; equal density | `bc.q=sqrt(eta)`, `transa=transb=[1;1]` | Reachable with patches 03/04 |
| Unit-amplitude plane waves | `sensor_info.t_dir`, `compute_fields` | Reachable; preserve positive spatial phase |
| Radius-10 receivers, equally spaced full aperture | Explicit `tgt` and direction pairs | Reachable; floor counts, not the shipped ceiling |
| Limited star: 200 receivers, 10 directions | Same paired data API | Reachable; full aperture with sparse angles |
| Clean scattered field | `fields.uscat_tgt` | Reachable; no total-field or far-field-amplitude conversion |
| Data: 100 points per wavelength | Wrapper geometry sampling before `get_fw_mats` | Reachable once wavelength convention and exact shape are fixed |
| Inverse: 70 points per wavelength | `opts.nppw`; explicit starting sampling | Reachable, but see resolution ambiguity below |
| Alpert order 16 | Hard-coded `norder=16` in `get_fw_mats` | Already used |
| Dense direct solve | Public transmission path stores `inv(Fw_mat)` | Algorithmically direct; explicit inverse differs from paper's LU description; retain public code |
| Unit-disk start | Explicit `src_init=geometries.ellipse(1,1,n)` | Reachable; no localization or extra starts |
| floor(3*max(k,k_inside)) update band | Set `opts.ncoeff_boundary` per frequency; disable length scaling | Reachable; omit `ncoeff_boundary_mult` so it cannot overwrite the exact band |
| Better of GN and SD | `optim_opts.optim_type='min(gn,sd)'` | Reachable; ties choose SD in public code |
| Gaussian filtering, ten attempts | `filter_type='gauss-conv'`, `maxit_filter=10` | Available, but sequence differs from the printed formula; see below |
| Curvature-energy restriction | `optim_opts.n_curv`, `optim_opts.eps_curv` | Controls exist; paper's numerical tolerance and exact cutoff choice are missing |
| Residual and update stops 1e-5 | `eps_res=1e-5`, `eps_upd=1e-5` | Reachable; public update test uses coefficient-vector norm |
| At most 50 iterations per frequency | `optim_opts.maxit=50` | Reachable |
| Relative symmetric-difference area | Wrapper polygon areas divided by truth area | Reachable; also retain unnormalized area |

### Gaps that options alone do not settle

1. **Shape and count gaps:** missing star coefficients, missing paper cavity
   parameterization/transforms, and the unspecified seventh run.
2. **Wavelength definition:** section 2 says to use the larger wavenumber;
   section 2.1 also prints a point-count formula using exterior k. Public
   updates use exterior k. Choosing `opts.nppw=70*max(1,sqrt(eta))` realizes
   the larger-wavenumber interpretation; choosing 70 realizes the exterior
   formula. The data count has the corresponding ambiguity. Ask the
   coordinator to settle it; do not infer it from the shipped example.
3. **Resolution at the start of each frequency:** RLA does not resample the
   previous curve before the first forward solve at the new k. Updates
   enforce at least 300 points, even parity and no decrease from the old
   count. A zero-update resampling call in the wrapper can set the requested
   starting resolution, but this must be declared and agreed. The paper
   does not specify rounding or a minimum node count.
4. **Curvature tolerance:** the paper defines an energy-fraction bound but
   supplies no numerical value for its tolerance. The public option defaults
   to infinity, which imposes no useful restriction; the shipped driver's
   0.1 is not a published choice. The implementation compares the square
   root of the tail-energy fraction, so its `eps_curv` would need the square
   root of a chosen paper energy tolerance. The exact curvature cutoff is
   also not fixed by the reported update-band rule.
5. **Filter sequence:** the printed exponent divides by sigma squared;
   public code divides by sigma, with the same decimal sigma schedule.
   Its ten-loop limit includes the initial unfiltered trial. Also, it filters
   each candidate independently before comparing residuals, while the prose
   allows accepting an already admissible candidate immediately. No option
   makes these sequences identical. Keep public behavior unless the
   coordinator explicitly requests a separately reported repair.
6. **Zero gradient:** activity 01's exact-fit diagnostic exposed a zero-over-
   zero SD step followed by a MEX crash. The public residual stop is checked
   after updating. No guard has been applied; report any recurrence without
   silently changing stopping rules.
7. **Analytic check source:** the shipped cavity's `(0.85,0)` is outside its
   true domain, invalidating that manufactured-solution estimate. Paper-case
   verification needs a valid interior point per exact shape, or a separate
   resolution comparison. This diagnostic does not define the measurement.
8. **Paper notation:** the star paragraph prints an inconsistent unsquared
   interior wavenumber. The requested eta=0.9 and section 4.1's contrast
   definition fix the intended material ratio; record this interpretation.
9. **Paper drivers absent:** the checked public source cannot establish the
   authors' choices for unspecified controls. Defaults are allowed only
   where genuinely silent, and must be named; a default that disables an
   explicitly described restriction is not a faithful reproduction.

## Procedure after decisions

1. Freeze exact shape definitions, eta values, all settings, software hashes
   and the seven-case manifest. Record every coordinator choice above.
2. Reuse the activity 01 MEX build and low-frequency transmission checks.
   Check each true-shape forward solution only enough to establish the
   measurement convention and the chosen resolution. Keep those checks
   distinct from reconstruction scores.
3. Generate the native BRG data and run one centred unit-disk start per case.
   Save data and continuation states after every frequency. Run timed cases
   alone; no CSI overlap for final table timing.
4. Retain curves, residual histories, iterations, exit flags, wall times and
   polygon area errors. Save plots at the paper's displayed frequencies and
   the final frequency. A poor reconstruction is a result, not a reason to
   tune or rerun with another start.
5. Write `results.md`, commit and push each completed or failed run by path,
   and stop for coordinator review. Later BEM work gets these exact fields,
   positions, directions and known material ratios.

## Budget, commands and outputs

Current numerical-run budget: **zero**. Proposed later ceiling: four hours
per case including data and inversion, at most seven cases (28 hours total).
This is a proposal, not authorization to exceed activity 01's four-hour
limit; the coordinator must assign the campaign budget before launch.

The paper runner does not exist yet. After the case manifest is complete,
implement `experiments/baselines/brg/run_paper.py` with the intended command
`python experiments/baselines/brg/run_paper.py --case <manifest-name>`.
Do not present that proposed command as runnable today. Use explicit
per-frequency options rather than editing the public numerical methods.

Raw outputs: `results/brg/paper_examples/<date>/<case>/`. Keep bulk data,
full states and full logs in ignored `local/`, with command and SHA-256.
Commit no more than about 5 MB per run: compact boundaries, residuals,
timings, logs and JSON. Figures: this activity's `figures/`. Code stays in
`experiments/baselines/brg/`; any approved upstream repair gets its own patch.

Success means every specified case finishes or reaches its declared limit
with reproducible evidence, and every deviation from the paper is explicit.
It does not mean that BRG recovers every shape; the cavity failure is one
of the paper's reported outcomes.

## Sources checked

- [Paper and equations](https://arxiv.org/html/2210.11607), official v1 PDF and
  TeX source, especially sections 2, 2.1, 4.1–4.3 and Figures 1, 4 and 7.
- [Source archive inventory](../../../../results/brg/paper_sources/source_members.json)
  and [download commands/checksums](../../../../results/brg/paper_sources/manifest.json).
- [Pinned public code](https://github.com/flatironinstitute/inverse-obstacle-scattering2d/tree/bda24bddbf4562497280b671bc174ef891b47c6b):
  `src/+geometries/starn.m`, `charlie_cavity.m`, and the RLA forward, inverse,
  update and geometry functions inspected in activity 01.
- [Activity 01 data conventions](../01_run_published_examples/data_handoff.md)
  and [patch record](../../../../external/patches/brg/README.md).

In the repository's [information chain](../../../reference/inverse_information_chain.md),
these are external BRG counterparts of A1–A4, B5–B8 and the geometry-update
controls. They are not on our default BEM inverse path; this plan does not
authorize edits to that path.
