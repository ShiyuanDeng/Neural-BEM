# GC-001: current geometry runtime, precision and attribution

Validated 279 common moves on 31 TG-002 replay states; zero physics calls.
Numerical source: `97f1a3276faec9b11b5ac315cc46819bf6379d25`. Raw receipts and failures are preserved.

## Repeated geometry timing

Median of per-state medians, 11 states × three repeats; milliseconds. First trial is 1 mm with a fresh
space/cache; subsequent trial is 6 mm in that same space. Sizes differ, so first/subsequent
columns do not isolate cache benefit. All attempts, including refusals, are timed.

| Arm | Preparation ms | First trial ms | Subsequent trial ms |
|---|---:|---:|---:|
| Spline CPU | 1133.405 | 33.843 | 34.618 |
| Spectral CPU, sampled | 2196.996 | 59.504 | 64.557 |
| GPU-prepared spectral, sampled | 41.367 | 65.258 | 65.654 |
| GPU-prepared spectral, certified | 41.463 | 97.601 | 487.105 |

## Precision and native decisions

Refined reference qualified on 278/279 moves. Errors below use only qualified references.

| Map | Median maximum curve error, nm | Worst maximum curve error, nm | Median refinement / sigma0 | Accepted moves |
|---|---:|---:|---:|---:|
| Spline CPU | 0.000736771 | 400.825 | 1.47e-11 | 277/279 |
| Spectral CPU, sampled | 2.85202e-06 | 0.185499 | 5.56e-14 | 277/279 |

Decision disagreements: S/F 0; F/B 0; B/C 0.
Spectral B/C use the same trial projection as F; their changed base-projection arithmetic is measured separately.

## Interpolation attribution: six largest S/F disagreements

Errors are centred trial differences against the qualified refined spectral reference, in nm.
The inverse/position replacements keep the native moved curve and native arclength primitive fixed.
Vector contributions and their interaction are retained; norm reductions are not an additive error budget.

| State / move | Native | Refined inverse only | Fourier position only | Both |
|---|---:|---:|---:|---:|
| aphex_twin__c13.3 / 0.006m-d1 | 400.825 | 400.796 | 400.904 | 400.874 |
| kite__c4 / 0.006m-d2 (reference unresolved) | 111.233 | 111.458 | 111.232 | 111.458 |
| kite__c4 / 0.006m-d1 | 91.0182 | 90.8007 | 91.0163 | 90.7988 |
| kite__c13.3 / 0.006m-d1 | 89.3171 | 89.3388 | 89.3178 | 89.3395 |
| cog__c13.3 / 0.006m-d1 | 119.23 | 121.202 | 119.252 | 121.224 |
| star__c13.3 / 0.006m-d1 | 128.794 | 128.41 | 128.785 | 128.401 |

Rows marked reference unresolved show diagnostic distances only; they are excluded from accuracy rankings.

## Output-grid aliasing attribution

Same six moves, fixed original moved curve. First vary only the final arclength sampling grid
before retained-band FFT cropping; native inverse and position splines stay fixed.
Then vary the integration grid at fixed 8N output, with direct moved-Fourier position evaluation.

| State / move | Native N output, nm | 8N output only, nm | 8N integration and output, direct position, nm |
|---|---:|---:|---:|
| aphex_twin__c13.3 / 0.006m-d1 | 400.825 | 0.906088 | 0.0133587 |
| kite__c4 / 0.006m-d2 (reference unresolved) | 111.233 | 29.0333 | 3.09201 |
| kite__c4 / 0.006m-d1 | 91.0182 | 0.106336 | 0.0584913 |
| kite__c13.3 / 0.006m-d1 | 89.3171 | 0.058219 | 0.000958155 |
| cog__c13.3 / 0.006m-d1 | 119.23 | 1.43806 | 0.000668214 |
| star__c13.3 / 0.006m-d1 | 128.794 | 1.28464 | 0.000800796 |

These adaptive diagnostic results identify output resampling/FFT aliasing as the dominant error
in the qualified large-disagreement probes. Cubic interpolation and integration contribute
smaller residuals. They do not establish inverse recovery gains or authorize a production change.
Main replay: 13.98 min; attribution continuation: 21.19 s.

## Whole-inverse context

These are historical internal runtime fractions, not matched inverse speed comparisons.

| Existing run | Recorded geometry-update share of total | Median case share | Total speedup if all geometry is 2× faster |
|---|---:|---:|---:|
| PC-001/M1 | 19.10% | 15.54% | 1.106× |
| PC-001/N1 | 15.21% | 3.08% | 1.082× |
| PC-002/NS | 19.45% | 15.61% | 1.108× |

Boundary-update counters include preparation, trial construction and validity checks, including audits.
They exclude geometry assembly charged inside physics. Fitting-only geometry fractions cannot be recovered
exactly from those saved counters. Inverse steps/recovery did not run in this experiment.

The detailed interpretation is in [iteration 30](../../../../docs/iterations/cleaned_interfaces/iteration_30/01_results.md).
Paired timing ranges, FD step sweeps, preparation ablations, exclusive component profiles and raw
error vectors are retained in `report.json` and the per-phase directories.
