# Reading check before the cylinder run

17 November 2026. Reading completed within the 30-minute limit; the only
MATLAB processes were two checks of about 2.44 seconds, not inversions.
No upstream setting or numerical code was changed.

## Figure 5 MR-CSI settings

Source: Sun, Kooij and Yarovoy, *Inversion of Multi-frequency Data with the
Cross-Correlated Contrast Source Inversion Method*,
[arXiv 1906.10814](https://arxiv.org/pdf/1906.10814), sections 2.2.4 and 4,
Figure 5, and references 13 and 25. The MATLAB files below are in the
pinned CC-CSI checkout; their source snapshot is retained in activity 01.

| Item | Paper | Shipped driver/function | Activity 01 paper wrapper |
|---|---|---|---|
| Constraints | Both methods clip negative real and positive imaginary contrast | `OrthgPro`, called after each contrast update with `bgchi=1`, does exactly this; outer five cells fixed zero | Unchanged |
| Regularization | MF-MR-CSI follows the cited multi-frequency method; no full discrete MR implementation or Figure-5-specific parameter list | `MR_CSI_Brent.m` uses multiplicative TV: half-cell refinement (`intrao=1`), gradient weights including state error `FD`, `nchi=nnz(Einc(:,1))`, TV border mask, polynomial start and Brent minimization (`TolX=1e-9`) | Unchanged, apart from the legacy API fix |
| Start | Equations 20 and 22: common back-propagation sources/contrast for a fair comparison | `Pre_InvFresnel_Conf.m` builds shared initial sources, fields and projected contrast before any method; no preceding method's result feeds MR | Unchanged |
| Iterations | 2048 | Active shipped II example uses 32; early termination is disabled | Set to 2048, termination still disabled |
| Data | Measured FoamTwinDielTM, 7-10 GHz, 18 views, 241 samples/view | Active II example is FoamDielExtTE, 2:2:10 GHz, 8 views | Corrected to paper TM case/frequencies/views; no added noise |
| Grid | 1.5 mm; stated domain [-82.5,82.5] by [-97.5,67.5] mm | Shipped II uses 100 mm half-widths, a different centre | Numerical domain matches the text; native display swaps matrix dimensions |
| Antennas | 1.67 m, source rotation in 20-degree steps | Shipped radius includes the phase-centre correction, giving 1.8140695 m; source offset +0.5 degree; calibration uses one receiver per source/frequency | Shipped correction and calibration retained |

Established differences capable of changing a non-convex result are the
antenna/source convention and the domain interpretation. The discrete TV
details, line search and calibration selection are not specified fully by
this paper, so equality with the authors' Figure 5 code cannot be checked.
These are possible explanations, **not demonstrated causes** of our clean
MR image. Positivity, starting point, frequency set, input case and 2048
iterations do not provide an established discrepancy after the wrapper
changes. The active shipped TE/32-step defaults cannot explain our paper
run because that run's retained executed driver shows the replacements.
No setting is changed to seek the speckled result. The mismatch stays open.

## Patch 0002: explicit old query rule

The coordinator's reading of legacy `interp2(X,n)` is that it used query
coordinates `1:1/2^n:end` without rejecting negative n. At n=-1 these are
the existing nodes `1:2:end`. The new check compares direct sampling with
`interp2(X,1:2:size(X,2),(1:2:size(X,1))','linear')`, not just the
refine/coarsen identity. It covers N=17 and 112, real/complex values, and
both a random refined-size array and `interp2(V,1)`: eight checks.

All eight have maximum absolute difference zero and `isequal=true`.
See [JSON](../../../../results/csi/fresnel/2026-11-17_reading_check_repeat/explicit_interpolation.json)
and [command/log](../../../../results/csi/fresnel/2026-11-17_reading_check_repeat/launch.json).
The first harness failed while appending unlike MATLAB structures; its
log is kept in `2026-11-17_reading_check`. A cell-array result collector
fixed only our check. Both commands had 60-second limits. No baseline ran.

## Truth source and coordinate convention declared before inversion

Belkebir and Saillard (2001), *Special section: Testing inversion algorithms
against experimental data*, Inverse Problems 17, 1565-1571,
[DOI](https://doi.org/10.1088/0266-5611/17/6/301),
[author PDF](https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf).
The bundled `FresnelData/The_first_opus/pdf1.pdf` is this paper and was
read and rendered directly: section 4.2, Figure 6(a), Figure 7, and Table 1.

The nominal radius is 15 mm; relative permittivity is 3 +/- 0.3 (contrast
2 +/- 0.3). Figure 6(a) places the centre 30 mm to the left of the setup
origin; section 4.2 describes the offset as about 30 mm. We declare the
paper-drawing frame with rightward x and upward y, giving nominal centre
(-30,0) mm. Its cross-section drawing does not label numerical axes: that
frame assignment is explicit, not a claim of a printed coordinate pair.
Compare exported numerical coordinates with this fixed declared frame;
do not rotate or shift the truth after seeing the recovered centroid.
Native CSI display places numerical x vertically, so a numerical x offset
will appear vertically in their plot. The position is nominal experimental
truth, not submillimetre metrology.

## Scoring API and budget

Import `experiments.comparison.scoring` using the EMNerf Python environment.
The top-level `score()` opens TG-002 truth/catalog files, so it cannot accept
a Fresnel truth directly. Reuse its `support_rings`, `region` and
`region_scores` functions. Resample the raw unmasked real contrast onto its
fixed protocol-1 201-by-201 physical grid, +/-100 mm, with zeros outside
the saved domain. No fit, shift or rotation to truth. Keep every region and
hole, signed peak and fractions 0.5/0.3/0.7. Report support area/centroid and
the mean susceptibility and relative permittivity over thresholded pixels.
This is a preview; image similarity metrics and a table-C pass/fail cut-off
are not added. No scoring file is edited.

The preflight cost model lists every activity-01 native timing, separates
TM from two-component TE, and assumes linear cell/source/frequency work.
Median measured TM coefficients predict 7044.089 s for the three methods.
With 20%, 120 s setup/export and the full 30-minute reading allowance, the
activity estimate is 10372.907 s (2 h 52 min 53 s), below four hours.
The detached inversion receives 12600 s (3.5 h), leaving 30 minutes for
reading. Source count, sparse solves and line searches limit this model.
The JSON is in the successful reading-check directory.
