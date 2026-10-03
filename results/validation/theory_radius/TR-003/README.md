# TR-003: theory diagnostic evidence

Empirical finite-dimensional diagnostics. No certified convergence radius or new recovery claim.

Execution complete: **False**. Numerical wall time: **111.8 s**. Forward frequency solves: **912**; derivative batches: **720**.

Source/input hashes, source archive, execution settings and concurrent processes are in [manifest.json](manifest.json). Timings with other campaign activity are not matched benchmarks.

| Case | Full data | Qualified | Stationary at 1e-8/mm | Curvature |
|---|---|---|---|---|
| modal__c13.3__development_c | False | True | False | resolved positive curvature |
| modal__c13.3__development_c | True | True | False | resolved positive curvature |
| modal__c4__development_c | False | True | False | resolved positive curvature |
| modal__c4__development_c | True | True | True | resolved positive curvature |

The Hessian includes residual curvature in the affine production-tangent chart. Actual finite production trials and their acceptance margins are recorded separately.

| Case | Branch stop | Accepted steps | Fold candidates | Interpretation |
|---|---|---:|---:|---|

These are bounded, truth-free data-homotopy paths in a fixed low-band chart, not the moving-chart production frequency ladder. Their limits do not establish absence of folds elsewhere or justify complex continuation by themselves.

