# Iteration 29 results: SC-049 far circle to C

2026-09-27. **COMPLETE / NOT RECOVERED.** The user requested a complex new
scene, "far circle to c". One accelerated reconstruction ran under the
[fixed contract](../iteration_28/03_sc049_plan.md), starting from the actual
distant circle. No restart, retuning or numerical default change followed.
Owner: Codex; self-review only.

The 65-mm circle is centred at (0.32, 0.62) m, with a 96.13-mm sampled gap
from the original SC-022 C. The unchanged target and noiseless observations
make this a new initialization stress test, not an unseen-shape test.

## Result and obstruction

Seven accepted updates reduce stage-1 loss from 3.7396 to 0.5463 at 0.5 GHz,
while symmetric boundary RMS worsens from **168.76 to 188.37 mm**. The shape
deforms near its incorrect starting location. The next candidate fails
N512/N1024 field agreement: **4.70e-5 versus the unchanged 1e-5 limit**.
The backend returns `NUMERICAL_FAILURE` and no later stage runs.

The initial full-catalog numerical audit passes. At the returned point, the
Jacobian and full-trial directional derivative still qualify, but the
higher-frequency fields fail their 1e-7 refinement requirement (worst 9.77e-7).
All four declared recovery criteria fail. The returned shape is the last
accepted point, not the rejected trial or a truth-selected checkpoint.

Post-stop controls add four CPU forward solves at 0.5/2.5 GHz and N512/1024.
They reproduce the endpoint refinement errors and agree with CUDA predictions
within 3.93e-15. All 24 dense-versus-spatial count comparisons on the eight
saved states also agree. These controls support the endpoint obstruction on
both execution paths; no second full inverse was run.

## Runtime, atlas and interpretation

The failed fit takes **1.61 s**. The main run, including two audits, two
initial/final atlases, scoring and integrity checks, takes **21.43 s / 406
physical units**. Separate post-stop controls take 12.07 s / 4 units, giving
410 units total. This is the cost of an early failed attempt, not the time to
recover a C. All budgets were respected.

Each P48 atlas uses all 19 frequencies and N512/1024, costing 76 units and
about 2.8 s. The initial atlas qualifies; the returned atlas fails the field
gate and is labelled exploratory. It is a sensitivity map, not a controller
or certified observability limit.

The [complete evidence, geometry plot and atlases](../../../../results/validation/shape_continuation/SC-049-far-circle-to-c/README.md)
preserve the failure, accepted states, controls, frozen sources and inputs.
The current local continuation does not recover this distant start. Lower
fitting loss is insufficient evidence of localization. Numerical stopping
precludes a conclusion about eventual convergence at a different grid or
under another policy; neither was tried. A follow-up would need to separate
global localization from quadrature and finite-shape feasibility.

**Timing-scope correction:** SPD-010–014 replay SC-043 continuation suffixes
from saved intermediate shapes. The earlier 6485 s versus 281 s comparison
does not measure full reconstructions from the original circles. SC-049
begins at the actual circle and reports the full attempted path.
