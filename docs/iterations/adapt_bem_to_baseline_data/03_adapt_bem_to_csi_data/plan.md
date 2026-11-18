# Adapt the BEM inverse to CSI data: plan

Agent `bem-csi`, 18 November 2026. Written before any code, for review
stop 1 of [coordinate_bem_side.md](../../coordinate_bem_side.md).

## Questions

1. Can our point-source table forward read CSI's seven-column table so
   that our forward on the true shape reproduces the data?
2. How large is the mismatch per frequency on the true measured cylinder
   (`dielTM_dec8f`) and on the true simulated circle (TG-002 `circle__c4`)?
   The circle must be at or below 1% (the user's rule).
3. Does the default method run on this data, unchanged, and keep the limits?

## Where this sits in the chain

Only data preparation is new. The adapter builds `Observation`s for the
existing table path: A3 point-source waves and A4 masked table fields
(`ModalSettings(table_mode=True)`, `PointSourceAcquisition(paired=False,
mask=...)`), and B5/B8 frequency blocks. All are in
[the chain](../../../reference/inverse_information_chain.md). The paired
TG-002 default path is not used and not touched.

## Answers for review stop 1

### Calibration factors

Source: CSI's own rule in `functions/ReadFreData.m`, TM branch, read in the
pinned tree `~/neural_bem_external/CC-CSI`:

- `calind = floor(NRX/2)+1 = 25`: the 25th row of each source's block **in
  file order** (not sorted order). For source 1 that is receiver 37, 180°.
- `Enor = Finc(calind,s) / ER(calind,s)`, one complex number per source and
  frequency. `ER = omega/4 * besselh(0,1,-k R) * omega^2/(-1j*omega)`,
  which is `omega_n^2 * (1j/4) besselh(0,1,-k R)`, with `omega_n` their
  normalized frequency.
- So CSI's model incident field is `Enor * omega_n^2` times the unit Green
  function `(1j/4) besselh(0,1,-kR)`. The `omega_n^2` belongs to their
  internal units only and cancels inside their model.

Our factor is the same ratio taken against our own unit Green function
(`PointSourceAcquisition`, strength 1, `i H0^(1)(kr)/4`):

```text
c[s,f] = conj(Finc[cal(s), s, f]) / G_ours(k_f, |r_cal(s) - x_s|)
```

This equals `conj(Enor * omega_n^2)`: same receiver, same ratio, no fitted
amplitude. Check in step 2: compare `c` with CSI's saved factors in
`results/csi/fresnel/2026-11-17_diel_tm/source_calibration.csv` (factor times
its `normalized_omega` squared, conjugated). Pass if they agree to 1e-10
relative for all 288 rows. On the simulated circle the pipeline note
predicts `c = 1` for every source; I check that too.

The data our fit reads are then `d[s,r] = conj(Etot - Einc)[s,r] / c[s,f]`:
CSI's scattered field (their subtraction), per source divided by the factor.

### Conjugation

CSI uses exp(+jωt); `besselh(0,1,-x)` on MATLAB's branch is `-H0^(2)(x)`,
so their unit field `(1j/4) besselh(0,1,-kR)` is `conj(i H0^(1)(kR)/4)`.
We use exp(-iωt). Every complex number from the file is conjugated once,
total and incident alike, before the factor above. Real permittivity needs
no change. Check in step 2: on the simulated circle the file's incident
column is CSI's unit field, so `conj(Finc)` must equal our `G_ours` at every
measured pair, to about 1e-12. That one check proves the conjugation, the
positions, the angles and the speed of light together.

### Mask and row order

- Sources: index i → angle `10(i-1) - 2.5`°, radius 0.72 m. Receivers:
  index j → angle `5(j-1)`°, radius 0.76 m. Positions `r(cos, sin)`. These
  are the shipped first-opus driver's rules, as in the
  [frame note](../../csi_adaptation/03_prepare_simulated_tg002_cases/frame.md).
  No rotation or shift of the frame.
- One `PointSourceAcquisition(sources 36, receivers 72, paired=False,
  mask)`. `mask[i-1, j-1]` is True for each (source, receiver) row present.
- I checked both files: the mask is the same at all eight frequencies, 49
  receivers per source, 1764 pairs.
- File rows are **not** in our order: within a source the receivers wrap
  round the ring (for example 61..72 then 1..37). Our masked vector is in C
  order (source, then receiver ascending). The adapter applies an explicit
  permutation and saves it; a test reverses it to the file order.
- The calibration row is chosen in file order before the permutation.

### Vacuum constants and units

- `c0 = 299792458` m/s, as in MaxwellFDFD's `PhysC.c0`. k = 2πf/c0, real.
  Background is vacuum, relative permittivity 1.
- TM `E_z` with a non-magnetic dielectric is our `equal_density_homogeneous`
  material; contrast is the relative permittivity (cylinder 3, circle 4).
- Length unit as the default: `length_unit_m = 0.05`. Positions are divided
  by it; k is multiplied by it (1.048 per GHz). Origin `origin_m = 0`, the
  acquisition centre. Bounds as the default's: ±0.3 m round the origin,
  well inside the 0.72 m source ring.
- Data are dimensionless (unit-source Green function), so no length factor
  enters them.

### The start and settings

The default method, unchanged:

- Start: `FourierCurve.circle(1.3, 0)`, a 65 mm circle at the acquisition
  centre. It covers the cylinder (nominal centre (0, +30) mm, radius 15 mm)
  and the circle truth (centroid (18.0, 12.6) mm, radius 50 mm).
- `modal_muller` + `slider`, localization none, no warm-up, real data only
  (`damped=None`), recovered contrast with the comparison's weak start
  (`MaterialUnknown`, solve at 1 + 1e-3 at the lowest frequency, 1 GHz).
- The solver is told no noise: `sigma_real_imag = 0` everywhere. It stops on
  its step and budget rules.
- Work limit 13,412 units. Wall limit: 120 s on the CPU pass (a fit that
  passes it stops and waits for the GPU pass), 3600 s on the GPU pass.
- One CPU frequency thread, BLAS pinned to one thread, until the GPU path
  exists.

### Frequency rule

From the data's wavenumbers only, fixed now, the same for every CSI case.

TG-002's real-only schedule climbs a ladder to 1.25 GHz, half its top
frequency 2.5 GHz, in four stages, then fits the whole catalog. My rule
copies that shape:

> Ladder stages are catalog prefixes, adding one frequency at a time, up to
> the highest frequency at or below half the catalog's top. Then the whole
> catalog.

On CSI data (1–8 GHz) this gives 1; 1–2; 1–3; 1–4 GHz, then 1–8 GHz. Four
stages, so the default four stage quotas (1000, 1250, 1750, 4000) apply
unchanged, and the last jump doubles the top wavenumber, as in TG-002.

Versus the coordinator's suggestion (1; 1–2; 1–3, then all): mine adds
4 GHz, so the last jump is a factor 2 (TG-002's) rather than 2.7, and it
fills all four default quotas. I recommend mine; either is one line.

Everything else is `RealOnlyPolicy` as it stands: ladder band
`floor(3k)` (3, 6, 9, 12 at 1–4 GHz), whole-catalog bands 11 to 37, then
the measured frontier up to 95, storage 192. Implementation: set
`prefix_frequencies_hz=(1e9, 2e9, 3e9, 4e9)` and switch each fit stage to
`ragged_data=True`, the frequency-block layout that the BRG fit already ran
(a thin subclass in the wrapper, like `BrgPolicy`). With equal weights its
per-frequency relative scaling is the same loss as the default's. No
per-case change.

### Series limit at 8 GHz

k = 167.7 rad/m at 8 GHz. At the default 1e-9 the solver refuses above
k times wave radius 17.7, so above a wave radius of 105.6 mm.

- Cylinder truth: at most 45 mm from the origin (x ≤ 7.5). Passes.
- Start circle: 65 mm (x = 10.9). Passes.
- Simulated shapes reach 96 mm (x about 16.1). Passes on the truth, with
  little margin; a fitted curve that grows past 105.6 mm would be refused.

Expected: 8 GHz passes at 1e-9 on both truths and the start, so no 1e-6.
Step 2 measures it with the solver's own `waves.radius` and loss, since
the solver's radius is coefficient based and may exceed the geometric one.
If a later fit is refused mid-run, that is reported as its outcome, not
rerun.

### Solver edit

None asked for. The CPU table path, masks, the unpaired point-source table,
frequency blocks and the recovered-contrast column already exist. The GPU
pass waits for `bem-gpu`.

## What I will check, and the success criteria

Step 2, forward checks (CPU, true shapes, no fit):

| Check | Pass |
|---|---|
| Our factor vs CSI's saved factors, measured file | ≤ 1e-10 relative, all 288 |
| Simulated circle: conj(Finc) vs our unit field; factor = 1 | ≤ 1e-10 relative |
| Row permutation round trip | exact |
| Circle `circle__c4` truth, ε 4: relative L2 mismatch per frequency | ≤ 1% at every frequency (else stop, coordinator asks the user) |
| Cylinder nominal truth, ε 3: mismatch per frequency | reported only; it holds measurement error and nominal geometry |
| Solver series loss at 8 GHz on both truths and the start | below 1e-9 |

The circle truth comes from `experiments.benchmark.scenes.truth_fixture`,
the frozen TG-002 shape CSI used. Truth is read only in the check and
scoring scripts, never in the fit. The mismatch is saved per frequency and
never passed to a fit.

Step 3, the first fit: measured cylinder, CPU, the settings above. Save raw
outputs and metrics, area and centroid against the nominal truth, scored
with the unedited `experiments/comparison/scoring.py` after the fit.

## Code, outputs, budget

New code, all outside the solver:

| File | Role |
|---|---|
| `experiments/bem_on_baseline_data/csi_data.py` | Read a seven-column table into masked observations, factors and permutation. No truth |
| `experiments/bem_on_baseline_data/csi_forward_check.py` | Step 2 checks on the true cylinder and true circle |
| `experiments/bem_on_baseline_data/csi_fit.py` | One fit per case; resumable at case level; score after the fit |
| `experiments/bem_on_baseline_data/csi_test.py` | A few small tests: permutation, factor, conjugation |

Results: `results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks/`
and `.../first_fit/dielTM_dec8f/`. Each run records the commit, whether
`solvers/bem_inverse/` is dirty, the input SHA-256, peak memory and the
other jobs running. Bulk over about 5 MB stays local with its SHA-256.

Inputs, read only:

- Measured: `~/neural_bem_external/CC-CSI/FresnelData/The_first_opus/dielTM_dec8f.txt`.
- Simulated: `results/csi/tg002/2026-11-17_campaign/<shape>/forward/synthetic_input.txt`,
  the retained file. Never regenerated.

Budget: step 2 is 16 forward solves (two truths, eight frequencies) plus
the start, on one CPU thread; a few minutes. Step 3 is one CPU fit, at most
120 s of fit time, started only with 16 GB available.

Commands (repository root):

```bash
P=/home/drdeng/miniconda3/envs/EMNerf/bin/python
$P experiments/bem_on_baseline_data/csi_forward_check.py --out results/bem/baseline_data/csi_adapter/2026-11-18/forward_checks
$P experiments/bem_on_baseline_data/csi_fit.py --case dielTM_dec8f --device cpu --out results/bem/baseline_data/csi_adapter/2026-11-18/first_fit
```

Step 4 hands `bem-csi-run` the same `csi_fit.py` with `--case` for the
cylinder and each simulated shape, plus `--device cuda` once the GPU path
exists.

## Choices and who made them

- User (coordination file): CSI's own calibration rule and factors, same
  mask, conjugation, no amplitude fit; default method unchanged; no noise
  level; 1% rule on the circle; one frequency rule per dataset from
  wavenumbers only; series limit 1e-9 unless 8 GHz is refused.
- Mine, for review: the frequency rule above; `ragged_data=True` for the
  table stages; length unit, origin and bounds as the default; the 120 s
  CPU wall limit.

## Model limits stated now

- Our model is a lossless, homogeneous dielectric. The measured cylinder's
  small loss and any antenna effects are left in the mismatch.
- The cylinder truth is nominal (about 30 mm offset, ε 3 ± 0.3). Its
  mismatch and scores are not a test of the adapter.
