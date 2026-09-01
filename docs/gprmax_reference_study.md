# gprMax Cross-Check — an Independent Method, Not Another BIE

2026-08-25

## Why this exists

Two other checks already exist for the circle case: `gpr_bem_ref` (the frozen
first-kind BEM) and the Nystrom reference (`docs/nystrom_reference_study.md`,
essentially exact). Neither can catch a **formulation-level** bug in
`gpr_bem_mod`. `gpr_bem_ref` shares the same kernels and the same code
lineage. The Nystrom reference deliberately shares the Muller formulation --
that was the point of building it fast, but it means a wrong sign in the jump
relations or a misplaced factor would appear in both `mod` and Nystrom
identically and neither would catch it.

gprMax is FDTD: no boundary integral, no Green's function, no jump relations,
no shared code of any kind. Agreement with it is evidence about the physics,
not evidence that two copies of the same method agree with each other.

## What it is not

Not a high-accuracy oracle. It is a 2nd-order, staircased-boundary,
off-the-shelf FDTD run, and its own discretisation error (1-2%, measured
below) is far larger than `mod`'s. It exists to catch gross errors -- a sign
flip, a units mistake, a wrong material -- not to out-measure Nystrom.

## Design decisions

**One run covers the whole ring.** The circle target is rotationally
symmetric and the 24-pair ring scan in `test_circle_comparison.py` is that
one representative pair rotated around the center, so every pair has the
identical scattered field. Confirmed with the Mie series, not assumed: all 24
values agree to `7e-17` absolute. One gprMax run (background + target) stands
in for the whole comparison test.

**Update, 2026-08-25: `build_scene.py`/`run_case.py`/`cache_io.py` were
generalised to `target_shape`/`target_size` (radius for a circle, half-side
for an axis-aligned square) so `test_square_comparison.py` could reuse the
same gprMax infrastructure. `build_geometry` now snaps a square's half-side to
a whole number of cells, so a square target sits exactly on cell faces --
zero staircasing, unlike the circle case this section measures below. Because
the square lacks the circle's full rotational symmetry (only 4-fold), its
comparison test uses just the index-0 ring pair, not the whole ring. See
`docs/validation_change_log.md` for the change record and first measurement.**

**Update, 2026-08-26: ellipse/star support was added for smooth non-circular
checks. These shapes are rendered by voxelizing the analytic target onto the
Yee grid and compacting each row into `#box` commands; unlike the square, they
therefore have staircasing error. The pytest files use the standalone Nystrom
solver as the precision baseline and keep gprMax as an independent index-0
sanity check only.**

**Update, 2026-08-27: two-circle support was added for the multi-component
case.** The two components are rendered as separate gprMax `#cylinder`
commands, with component centers stored relative to the target center in the
cache key. There is still only one simulated Tx/Rx pair, so
`test_two_circle_comparison.py` follows the square convention: gprMax is the
external baseline for the index-0 ring pair only, and full-ring behavior is
covered by self-convergence plus the recorded deltas to `gpr_bem_mod`.

**Update, 2026-08-27: gprMax cache generation now defaults to one run per
frequency with frequency-scaled grid spacing and a centered Ricker pulse.** The
old design used one broadband pulse centered at 1.5 GHz and one fixed 1 mm grid
for the whole 0.5-8 GHz sweep. That was fine for the gated low-frequency
cross-check, but it made 6/8 GHz weak twice over: fewer cells per wavelength and
little source energy far from the pulse center. `run_case.py` now defaults to
`--frequency-mode scaled`: each requested frequency gets its own background +
target pair, its Ricker center is set to that frequency, and `dx` is
`min(1 mm, lambda_sand / 30)` by default. The legacy one-blob sweep remains
available as `--frequency-mode sweep`. The pytest-side loader first looks for a
complete set of per-frequency scaled cache entries and falls back to the legacy
fixed-sweep blob if the scaled entries have not been generated yet.

**A background-only run calibrates out everything gprMax-specific.** Rather
than deriving gprMax's Hertzian-dipole current normalisation, cell-size
scaling, or mesh-dispersion phase error by hand, two FDTD runs are made:
without the target (`background`) and with it (`target`). The background
run's Fourier transform at each frequency is compared against the closed-form
incident field `0.25j * H0^(1)(k |Tx-Rx|)` -- the same normalisation this
whole project uses -- which pins down a complex calibration factor per
frequency:

    calibration(f) = 0.25j H0^(1)(k |Tx-Rx|) / FFT(Ez_background)(f)
    scattered(f)   = calibration(f) * [FFT(Ez_target)(f) - FFT(Ez_background)(f)]

Both runs share the source, the domain, the cell size, and the propagation
path length, so this calibration cancels everything FDTD-specific and leaves
only genuine FDTD discretisation error. It also means the analytic spectrum
of the source waveform is never needed -- `solvers/gpr_bem_ref/waveforms.py`
has one for the plain "gaussian" waveform, but `run_case.py` uses gprMax's
"ricker" pulse and calibrates empirically instead.

The Fourier convention matches this codebase's own:
`F(w) = integral f(t) exp(+i w t) dt`, as already documented in
`waveforms.py`. Frequencies are extracted by direct summation
(`dt * sum f(t_n) exp(+i w t_n)`) rather than FFT-bin interpolation, since the
requested comparison frequencies do not generally land on FFT bins.

**2D TMz falls out of gprMax's standard 2D recipe.** A 1-cell-thick domain in
z with PML disabled on the z faces (`#pml_cells: n n 0 n n 0`) and a
z-directed Hertzian dipole leaves only `Ez, Hx, Hy` active -- gprMax reports
this scene as "Mode: 2D TMz" itself, matching this project's polarisation
exactly with no reinterpretation needed.

## Environment split, and why the cache is not optional

gprMax needs a Cython extension (`fields_updates_ext`) that is not built in
the `gprMax/` checkout vendored in this repo; the built copy lives at
`/home/drdeng/gprMax`, in the separate `gprMax` conda environment (Python
3.11, not the `EMNerf` env pytest runs in). So a gprMax run can never happen
inside the test process -- there is no import path from `EMNerf` to `gprMax`.

This makes the cache load-bearing, not a convenience: `solvers/gprmax_ref/`
splits into `cache_io.py` (pure stdlib + numpy, importable from either
environment) and `run_case.py` / `build_scene.py` (import `gprMax` and
`h5py`, must run under the `gprMax` env). The shape-comparison pytest files
only ever call `cache_io.load(...)`; they cannot invoke gprMax even if they
wanted to.

**Cache key.** `cache_io.build_params(...)` collects every physical and
numerical parameter that can change the FDTD answer -- target shape and size,
optional shape parameters, standoff, tx/rx offset, both materials' epsr/sigma,
cell size, waveform, center frequency, time window, PML thickness, gprMax
version -- and hashes them (`case_key`, sha256 truncated to 16 hex chars) to
a filename under `solvers/gprmax_ref/cache/`. A new geometry or material
combination hashes to a new key and gets its own entry automatically; nothing
here is hard-coded to "this test case" beyond the argparse defaults in
`run_case.py`, which mirror the shape config files. In scaled mode, the
frequency list in each cache key has length 1, and the key's `cell_size` and
`center_frequency` are the values for that frequency. `cache_io.load_frequency_sweep(...)`
assembles those one-frequency entries back into a sweep-shaped result for the
comparison tests. Each cache file is a small JSON blob: the params for
provenance, plus the calibrated complex scattered field, Tx/Rx/target-center
positions, iteration count, dt, and wall-clock time.

**Regenerating.**

```bash
/home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
    --target-shape circle   # or square / ellipse / star / two_circles
```

This now creates separate cache files, one per requested frequency. At the
defaults, 0.5/1.5/2.5/4 GHz keep the 1 mm cap; 6 GHz uses about 0.68 mm, and
8 GHz uses about 0.51 mm. To regenerate the old broadband cache format:

```bash
/home/drdeng/miniconda3/envs/gprMax/bin/python solvers/gprmax_ref/run_case.py \
    --target-shape circle --frequency-mode sweep
```

The comparison test files read whatever is cached; if a full scaled set exists,
they use it. If not, they fall back to the matching fixed-sweep cache. If neither
exists for the current config values, the gprMax row and cross-check test skip
cleanly rather than failing the suite or silently running stale numbers.

Current cache defaults are 0.5 / 1.5 / 2.5 / 4 / 6 / 8 GHz. The low three
frequencies are the gated gprMax cross-check; 4 / 6 / 8 GHz are printed as
diagnostics only. At the checked-in 1 mm cell size and 1.5 GHz-centered Ricker
pulse, gprMax itself estimates the maximum significant frequency at ~4.2 GHz,
so the 6 and 8 GHz values should not be treated as a precision oracle.

## Measured

Cell size 1 mm, PML 12 cells, Ricker pulse centered at 1.5 GHz, 15 ns time
window (6361 iterations), single representative Tx/Rx pair (chord 0.0599 m).
Numerical dispersion analysis (gprMax's own estimate): -0.10% phase-velocity
error in sand, wavelength sampled by 29 cells, maximum significant frequency
~4.2 GHz. Solve time ~8.7 s per variant, ~18 s total including background.

| f (GHz) | gprMax scattered | Mie scattered | rel. error |
|---:|---|---|---:|
| 0.5 | 4.678e-03 + 2.885e-03j | 4.649e-03 + 2.934e-03j | 1.03% |
| 1.5 | 8.148e-04 + 3.461e-03j | 7.348e-04 + 3.481e-03j | 2.32% |
| 2.5 | -2.171e-03 + 1.862e-03j | -2.225e-03 + 1.849e-03j | 1.90% |

For scale, `gpr_bem_mod` measures 0.03% / 0.36% / 3.4% and `gpr_bem_ref`
measures 9.2% / 62.8% / 19.6% on the same case (`docs/validation_change_log.md`).
gprMax sits *between* the two BEM packages at every frequency except 2.5 GHz,
where `mod`'s own error has grown large enough to be comparable to gprMax's
FDTD discretisation floor -- both are small in absolute terms there,
0.03-0.05, so this is not a meaningful reversal.

**What this settles.** gprMax's agreement with the Mie series to 1-2% at a
completely independent, non-BIE, non-Green's-function method is evidence that
`mod`'s large accuracy gains (the Muller formulation, the analytic kernels)
reflect real physics and not a self-consistent bug shared between `mod` and
the Mie series or `mod` and Nystrom. It does not, by itself, prove `mod`'s
sub-percent accuracy is correct to that precision -- gprMax's own floor is a
coarser instrument than that.

**What this does not settle.** Coverage is still narrow: centered targets,
lossless materials, and low-frequency gprMax gates only. Ellipse/star now have
cache entries, but their FDTD geometry is staircased, so Nystrom remains the
precision baseline for those shapes. Lossy materials (`sigma != 0`) and the
4/6/8 GHz band (would need a finer cell size and a higher-frequency source
than the checked-in 1 mm / 1.5 GHz Ricker setup) are not precision-validated.

## Files

- `solvers/gprmax_ref/build_scene.py` -- sizes the domain around the target
  and the representative Tx/Rx pair, renders the `.in` scene text.
  Shape-agnostic: takes `target_shape`/`target_size` and emits `#cylinder`,
  exact `#box`, voxelized row-wise `#box` geometry for ellipse/star, or two
  separate `#cylinder` commands for the two-circle case.
- `solvers/gprmax_ref/run_case.py` -- runs both FDTD variants, does the DFT
  extraction and calibration, writes the cache. Requires the `gprMax` env.
- `solvers/gprmax_ref/cache_io.py` -- cache key, load, save. No gprMax
  dependency; safe to import from `EMNerf`.
- `solvers/gprmax_ref/cache/*.json` -- the checked-in cached result(s).
- `pytest/test_circle_comparison.py` -- adds the `gprmax` row to the
  three-way table and `test_circle_gprmax_cross_check`, both cache-driven.
- `pytest/test_square_comparison.py` -- the square target's version, compared
  on the index-0 ring pair only (see the 2026-08-25 update above).
- `pytest/test_ellipse_comparison.py`, `pytest/test_star_comparison.py` --
  Nystrom-baselined smooth non-circular checks with gprMax index-0 rows.
- `pytest/test_two_circle_comparison.py` -- multi-component check using
  gprMax as the index-0 baseline plus full-ring self-convergence.

## Update, 2026-09-01: genuinely single-frequency (`contsine`) runs, replacing the broadband-pulse-per-frequency default

**Motivation.** Every gprMax run up to this point -- including "scaled" mode's
per-frequency cache entries -- drove the source with a broadband Ricker pulse
and read off one frequency's response by DFT over the whole time-domain
signal. That conflated two costs: what it takes to resolve *one* frequency's
scattered field, versus the wall-clock cost of a wideband transient that
happens to contain it. It also made gprMax's timing not directly comparable to
a BEM forward solve at one frequency, or to the operator-level QBX forward
solves in `docs/validation_change_log.md` -- the actual reason this was
revisited, when asked to compare a proposed QBX solver's forward-solve time
against gprMax's and found no genuinely single-frequency FDTD number to
compare it with.

**Mechanism.** `--frequency-mode harmonic` (now the default) drives the source
with gprMax's built-in `contsine` waveform -- a continuous `sin(2*pi*f*t)`
ramped linearly to full amplitude over its first 4 periods (see
`gprMax/waveforms.py`) -- at exactly the target frequency, no separate
"center frequency" concept. `cache_io.harmonic_time_window` sizes the run
length from four additive terms, all in physical time (not period counts,
except where periods are the physically correct unit):

- **transit time**: domain-diagonal distance (a conservative stand-in for the
  longest Tx-target-Rx path actually used) divided by the background phase
  velocity, times a 1.15 safety factor;
- **settle time**: `DEFAULT_HARMONIC_SETTLE_TRANSIT_MULTIPLIER` (1.0) times
  the transit time above. Secondary reflections (PML residual, multi-bounce
  off the target) travel a physical distance comparable to the direct path,
  so they arrive after a comparable *absolute time* -- not a comparable
  *period count*. A first version used a flat 3-period settle margin; at
  8 GHz, 3 periods is 0.375 ns, nowhere near enough for reflections that take
  a few ns regardless of source frequency, and it measurably corrupted the
  circle's 8 GHz result (rel. error vs Mie jumped past the legacy Ricker
  sweep's by roughly 10x). Scaling the margin off transit time instead of a
  period count fixed it -- see "Validation" below;
- **ramp time**: 4 periods, `contsine`'s own built-in ramp;
- **extraction time**: 6 periods, the trailing window the phasor is fit from.

Cell size still comes from the existing `frequency_scaled_cell_size` (same
30 cells/wavelength rule, capped at 1 mm) -- unchanged from "scaled" mode.

**Extraction.** `run_case.py::run` slices both the background and target
signals to their trailing `extraction_seconds` before the existing DFT-sum
calibration (`_spectrum`). Re-zeroing both signals' time origin identically
introduces the same `exp(-i*w*t0)` factor into both spectra, which cancels
exactly in the existing background-calibration ratio -- no other change to
the calibration math was needed.

**Cross-platform cache-key stability.** `harmonic_time_window`'s
transit/settle terms go through `cmath.sqrt`/`math.hypot`, which differed in
their last 1-2 bits between conda environments in practice (observed: the
`EMNerf` env's Python 3.9 vs. the `gprMax` env's Python 3.11 disagreed at the
15th significant digit for some frequencies). Since nothing else rounds
`time_window`, that noise changed the cache key depending on which machine
looked it up. Fixed by rounding the returned value to 15 decimal places, the
same defensive pattern `frequency_scaled_cell_size` already uses for `dx`.

**Validation.** Circle's harmonic-mode error against the Mie series now
reproduces the legacy Ricker-sweep numbers at every frequency (both to within
their own run-to-run noise floor):

| f (GHz) | legacy Ricker (broadband, DFT-extracted) | harmonic (`contsine`, single-frequency) |
|---:|---:|---:|
| 0.5 | 0.0102 | 0.0104 |
| 1.5 | 0.0232 | 0.0233 |
| 2.5 | 0.0190 | 0.0188 |
| 4.0 | 0.0766 | 0.0766 |
| 6.0 | 0.1079 | 0.1087 |
| 8.0 | 0.1725 | 0.1728 |

This is the strongest check available (circle is the only shape with a
closed-form oracle): agreement to within ~1% relative at every frequency means
the harmonic method is measuring the same physics as the broadband one, not a
cheaper but biased substitute.

**Measured wall-clock, all five shapes.** `pytest/results/aggregate_metrics.md`
now has a "Wall-Clock Comparison" table (regenerated by
`pytest/test_aggregate_comparison_results.py`) with one column per shape and
one row per solver, including gprMax. The generated file is the canonical
source for the measured values because BEM timings vary from run to run.
Coverage is shown explicitly there: every BEM row covers the full 24-pair
ring, whereas the cached gprMax row covers one representative Tx/Rx pair per
frequency. The report intentionally emits no ratio between those unequal
workloads. In particular, rotational symmetry makes the one-pair circle cache
representative of the ring, while full nonsymmetric 24-pair gprMax workloads
have not been measured. The raw timing rows must not be read as an equal-work
speedup claim.

Per-frequency, harmonic mode's cost is roughly flat across the sweep (cell
size and time window both scale with wavelength, so iteration count is
roughly frequency-independent once the wavelength-based cell size takes over
from the 1 mm cap), whereas the legacy Ricker sweep's fixed 15 ns window made
its cost grow with frequency (same duration, ever-finer mesh). Net effect on
circle: harmonic mode is slower than Ricker at 0.5 GHz (was ~21 s per
frequency pair, now ~35 s) but faster at 8 GHz (was ~42 s, now ~25 s after the
settle-time fix). See `docs/validation_change_log.md` for how this compares to
BEM/QBX forward-solve timing, which was the reason this was measured.

**Regenerating.** `--frequency-mode harmonic` is now the default, so the
existing regeneration command in each pytest file's docstring
(`run_case.py --target-shape <shape>`) now produces harmonic-mode cache
entries. `cache_io.load_frequency_sweep` prefers a harmonic cache entry when
present, falls back to a scaled/Ricker entry, then the legacy whole-sweep
blob -- old cached entries are untouched and still load if a harmonic entry
is missing for some frequency. `--frequency-mode scaled` (Ricker,
per-frequency) and `--frequency-mode sweep` (legacy, one broadband run) are
still available for comparison.
