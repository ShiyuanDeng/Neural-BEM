# Cleaned interfaces

**Question:** How can one cumulative SC/MA inverse retain performance across
all 36 configurations while making continuation stages clear and forward
solvers interchangeable?

Opened 2026-09-30 at the user's request. This track owns the cleanup
requirements and implementation. Existing SC/MA implementations and evidence
remain in their original locations. The subsequent user request authorized
implementation first, with the 36-scene campaign to be run by the user.

## Current handoff

| Item | State |
|---|---|
| Current cycle | Iteration 02 / CI-001 implementation; all-36 validation pending |
| User requirements | [Three requirements and the cumulative-pipeline clarification](iteration_01/02_proposals/01_user_requirements.md) |
| Plan | [CI-001 — restore clean inverse interfaces and verify retention](iteration_01/03_plan.md) |
| SPD integration | [Assessment](iteration_01/02_proposals/02_spd_integration_review.md): preserve SPD-010–015 and integrate SPD-016 grid-plus-assembly through maintained interfaces; field-table extension not selected |
| Approval status | User authorized implementation and focused validation; user will run the 36 configurations |
| Execution status | Maintained package implemented; bounded CPU/CUDA checks executed; no all-36 fits or new benchmark observations generated |
| Implementation | [`experiments/cleaned_interface`](../../../experiments/cleaned_interface/README.md); [current results and limits](iteration_02/01_results.md) |
| Starting evidence | [Current pipeline inventory](../../pipelines/shape_frequency_continuation.md), [SC handoff](../shape_frequency_continuation/README.md), [MA handoff](../modal_atlas/README.md), [SPD handoff](../speedup/README.md) |
| Next validation | Run the two SPD extraction pairs, explicitly augment 16 missing damped catalogs, then run all 36 original starts and inspect every regression |
| Following step | Qualify a modal Müller backend through the interface established by CI-001 |

The target is one maintained cumulative implementation. Historical algorithms
supply regression evidence; they are not separate production paths selected
by scene identity. No all-36 retention result is claimed yet.

## Cycle history

| Cycle | State |
|---|---|
| [01](iteration_01/03_plan.md) | Original requirements and proposed plan, preserved as the pre-implementation record |
| [02](iteration_02/01_results.md) | Implementation and focused checks; reconstruction/runtime retention remains unestablished |

Follow the [shared iteration workflow](../README.md). Iteration 02 records
measured implementation checks separately from the pending inverse campaign.
