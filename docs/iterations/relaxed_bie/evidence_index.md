# Relaxed-BIE evidence index

The active research handoff is [README.md](README.md). All paths below are
historical originals; no source seal, experiment ID or result is renamed.

| Evidence | Original record | What it establishes |
|---|---|---|
| FM-001 design | [Frozen plan](../cleaned_interfaces/iteration_18/03_plan.md) | Full acquisition and a real-frequency relaxed prefix; original gradient froze receiver weights |
| FM-001 outcomes | [Results](../cleaned_interfaces/iteration_18/01_results.md), [bundle](../../../results/validation/cleaned_interfaces/FM-001/README.md) | Ordinary full-acquisition arm recovered 36/36 under full observations; unchanged paired contract passed 32/36. Original relaxed arm recovered 0/4 before its stopping rule ended the arm |
| FM-001 preservation receipt | [Final verification](../../../results/validation/cleaned_interfaces/FM-001/final_verification.json) | Hashes of the original plan, reports, catalogs and run evidence |
| FM-002 design | [Frozen plan](../cleaned_interfaces/iteration_19/03_plan.md) | Complete reduced gradient and predeclared damping × relaxation comparison on three cases |
| Reduced derivative | [Derivation](../cleaned_interfaces/iteration_19/04_derivative.md) | Variable projection, all shape-dependent terms, and the remaining approximate curvature model |
| FM-002 outcomes | [Original results](../cleaned_interfaces/iteration_19/01_results.md), [bundle](../../../results/validation/cleaned_interfaces/FM-002/README.md) | Twelve runs complete; no extra recoveries from relaxation under those settings |
| FM-002 qualification | [Qualification](../../../results/validation/cleaned_interfaces/FM-002/qualification.json), [477-test log](../../../results/validation/cleaned_interfaces/FM-002/qualification_tests.log) | Derivative, refinement, CPU/CUDA and numerical/package regression checks |
| FM-002 comparison | [Machine-readable comparison](../../../results/validation/cleaned_interfaces/FM-002/comparison.json), [endpoint plot](../../../results/validation/cleaned_interfaces/FM-002/endpoints.png) | Endpoint errors, costs, unchanged ordinary controls and all failed arms |
| FM-002 preservation receipts | [Run verification](../../../results/validation/cleaned_interfaces/FM-002/final_verification.json), [reporting verification](../../../results/validation/cleaned_interfaces/FM-002/reporting_verification.json) | Run and reporting hashes, including all three original iteration-19 documents |
| Revised interpretation | [Iteration 01 review](iteration_01/01_results.md) | Fixed-resolution stops do not establish stationary failure; scientific closure remains premature |

## Four stopped trajectories to replay

All four are contrast 13.3, full-matrix observations, nodal Kress physics.
R0 has the ordinary real prefix; R1 has the corrected relaxed real prefix.
The stopped stages themselves all use the ordinary objective.

| Case | Arm | Stopped stage receipt |
|---|---|---|
| Development C | R0 | [fixed_M49](../../../results/validation/cleaned_interfaces/FM-002/runs/modal__c13.3__development_c/R0/fixed_M49.json) |
| Development C | R1 | [release_M11](../../../results/validation/cleaned_interfaces/FM-002/runs/modal__c13.3__development_c/R1/release_M11.json) |
| Shifted star | R0 | [fixed_M49](../../../results/validation/cleaned_interfaces/FM-002/runs/modal__c13.3__shifted_star/R0/fixed_M49.json) |
| Shifted star | R1 | [fixed_M49](../../../results/validation/cleaned_interfaces/FM-002/runs/modal__c13.3__shifted_star/R1/fixed_M49.json) |

Each receipt retains the last accepted coefficients, LM history, failed trial
metadata, and production/refined acceptance check. The rejected candidate's
coefficients are not explicitly saved in the trial record: reconstruct and
qualify that candidate before treating any new replay as the same trial.
