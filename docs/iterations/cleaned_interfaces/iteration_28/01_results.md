# Iteration 28 — PC-001 exposes geometry-reuse and resolution confounds

Opened 2026-10-04 by the user's request for a fresh cleaned-interface iteration
and a plan to make the nodal/spline timing baseline fair.

## Starting evidence

[PC-001's retained report](../../../../results/validation/cleaned_interfaces/PC-001/README.md)
records 30/30 completed runs for both M1 and N1. Each recovers the same 26/30
TG-002 cases (9/10, 9/10, 8/10 by contrast). Their median case times are
31.39 s and 156.68 s, respectively. N1's four failed cases promoted to
N1024/2048 without adding a recovery. These are measurements from PC-001,
not a newly matched timing experiment.

The user stopped N0, nodal Kress plus spline, after 12/30 completed cases to
add geometry reuse across frequencies first. All twelve completed cases
recover; two interrupted case folders remain incomplete. The stopped arm is
neither a completed benchmark nor a numerical failure. Its finished runs,
partial work, and PC-001's original plan remain in place.

## Implementation finding

At checkout `b583f29992489e7b14aea3f60c086ec0bc0bc738`, both physics services
already dispatch independent frequencies through the same ordered executor.
Frequency threading alone is not the missing optimization.

- `bem_inverse.modal_muller.ModalMuller._geometry` retains geometry keyed by
  the exact curve coefficients, workspace, and device.
- `bem_inverse.continuation.forward.solve` and `NodalKress._damped` construct
  nodal geometry for each frequency. CUDA `_difference_blocks` reconstructs
  pair distances, normal projections, normal dot products, and quadrature
  geometry on every assembly.
- SPD-015 caches geometry validation. That does not establish reuse of the
  nodal assembly's dense geometric arrays or acquisition distances.
- Spline `update.prepare` is already outside the audit frequency loop.
  Measure any remaining repeated basis work before changing its execution;
  changing the spline algorithm is not the proposed intervention.

The causal question is whether reuse of frequency-independent nodal geometry
preserves the inverse and materially changes its complete cost. The historical
modal/nodal timings do not answer that question. NU-007a's separate CPU/GPU
certificate comparison remains valid in its original scope.

## User review: the resolution floor is the main additional confound

The user's 2026-10-04 review identifies the nodal minimum resolution of 512 as
the main remaining baseline issue. `Execution` rejects smaller resolutions;
`NodalKress.resolution_profile` uses at least 512 nodes per trace, refined to
1,024. Modal's initial K_trace64 has 129 modes per trace. Total dense system
dimensions are therefore 1,024 versus 258 early on. The dimension-cubed LU
estimate is about 61x, but no measured component or complete-inverse speedup
can be inferred from that arithmetic alone.

Two qualifications are binding: Kress requires an even node count, and
`FourierCurve.nodes`/`FitStage` require nodes >2*K_geometry. A dimension-matched
early seed is N130, not N129. With storage K192, nodal needs at least N386
without changing the stored shape. Smaller profiles need next-finer and
independent-reference qualification; equality of dimensions is not equality
of numerical accuracy.

Device inspection also finds a hybrid asymmetry. Nodal SPD-016's real/damped
CUDA routes use `cuda_assembly.DeviceFactors`: GPU LU and forward/reciprocal
solves, with host-retained factors uploaded for later solves. Modal CUDA
assembly returns to host and uses SciPy CPU LU/solves. Incident/readout and
final Jacobian contraction are on CPU in both. The SciPy import in nodal
`physics.py` belongs to its CPU path and does not prove CPU LU under SPD-016.

The common `certified_spectral` selector routes both to
`DeviceCertifiedUpdate` on CUDA. A read-only check of all 60 PC-001
`fit_result.json` receipts confirms CUDA preparation/certificate settings in
30/30 N1 and 30/30 M1 runs, identical geometry settings in every matched case,
and zero recorded preparation/certificate device fallbacks. This confirms
their shared geometry path; it does not make their physics devices identical.
The four promoted N1 cases are `aphex_twin` at all three contrasts and
`hook__c13.3`, all failed. Keep those cases and their cost separate from the
26 unpromoted recovered cases. M1 has no mid-stage promotion.

## Decision and next contract

Propose amended [PC-002](03_plan.md): first qualify geometry reuse at unchanged
resolution, then accuracy-selected smaller nodal profiles and component-device
routing. Obtain fresh TG-002 comparisons with bounded cache, fixed-floor and
CPU-LU controls, common GPU geometry and independent endpoint audits. PC-001
timings are contextual evidence only. Its N0 arm stays stopped;
the new experiment uses fresh directories and does not fill its missing rows.

**Approval:** plan requested; PC-002 execution not approved. No numerical code
changed and no run launched in this iteration. Results from PC-002, if
approved and executed, open iteration 29.
