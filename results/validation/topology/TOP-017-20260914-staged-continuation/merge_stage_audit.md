# Saved TOP-016 merge audit

Rebuilt from immutable JSON; no inverse or forward reruns. [Full table, starts, gradients and hashes](merge_stage_audit.json).

| Arm/stage | GHz | Boundary mm start → end | IoU end | 0.5 | 0.75 | 1.0 | 1.25 | 1.5 | 2.5 | Same-objective gain | Stop | Solves |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| S 1 | 0.5 | 0.5541558 → 0.5355139 | 0.9934354 | 7.212099e-05 | 0.001003291 | 0.01035753 | 0.03767917 | 0.04295756 | 0.09807181 | 5.03025e-10 | gradient_tolerance | 855 |
| S 2 | 0.5 | 0.5355139 → 0.5355139 | 0.9934354 | 7.212099e-05 | 0.001003291 | 0.01035753 | 0.03767917 | 0.04295756 | 0.09807181 | 0 | gradient_tolerance | 47 |
| S 3 | 0.5 | 0.5355139 → 0.5355139 | 0.9934354 | 7.212099e-05 | 0.001003291 | 0.01035753 | 0.03767917 | 0.04295756 | 0.09807181 | 0 | gradient_tolerance | 47 |
| S 4 | 0.5 | 0.5355139 → 0.5355139 | 0.9934354 | 7.212099e-05 | 0.001003291 | 0.01035753 | 0.03767917 | 0.04295756 | 0.09807181 | 0 | gradient_tolerance | 47 |
| F 1 | 0.5 | 0.5541558 → 0.5355139 | 0.9934354 | 7.212099e-05 | 0.001003291 | 0.01035753 | 0.03767917 | 0.04295756 | 0.09807181 | 5.03025e-10 | gradient_tolerance | 855 |
| F 2 | 0.5,0.75 | 0.5355139 → 0.9211989 | 0.9926456 | 0.0001558695 | 0.0004586966 | 0.003610707 | 0.01286 | 0.02361908 | 0.1536034 | 1.94274e-07 | no_decreasing_step | 624 |
| F 3 | 0.5,0.75,1 | 0.9211989 → 1.365819 | 0.9862959 | 0.0003273554 | 0.0005882005 | 0.001373674 | 0.01190161 | 0.03767848 | 0.1984905 | 1.821963e-06 | no_decreasing_step | 336 |
| F 4 | 0.5,0.75,1,1.25 | 1.365819 → 1.108232 | 0.9878848 | 0.0002128835 | 0.0007034424 | 0.002283245 | 0.008518756 | 0.02651879 | 0.1679487 | 8.208241e-06 | no_decreasing_step | 444 |

Prediction deterioration first appears in the shared stage 1 at 2.5 GHz. Geometric deterioration first appears at F stage 2. Every F stage decreases its own active refined objective; those differently normalized objectives are not compared across stage changes. The adverse inverse result remains in force.
