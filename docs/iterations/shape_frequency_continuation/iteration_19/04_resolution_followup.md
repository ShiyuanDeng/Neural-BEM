# SC-038 numerical follow-up — finish kite's M ladder on a denser grid

2026-09-25. Within the user's requested C/kite M-release test. This amendment
is recorded after the original kite M=15 numerical stop, before the new fit.
The original contract, attempted path and stopped result remain unchanged.

Kite's first M=15 accepted step reaches 0.278808 mm RMS. Its next candidate
decreases both production and refined losses, but the maximum 512/1024 field
discrepancy is 4.0567e-7, above the existing 1e-7 tolerance. M=19 was therefore
not reached. Test numerical resolution, without relaxing that tolerance.

For **kite only**, rerun stages M=15 and M=19 from its exact saved M=11
endpoint using **768/1536 nodes**. Rerun the corresponding M=9/9 control from
its saved first-stage endpoint on the same denser grid. Keep K=192, all 19
frequencies, weights, projection, optimizer, 22 iterations and 1,500 units per
stage unchanged. Damping resets as usual. Two paths, each at most 3,000 new
units and 1,800 seconds; reserve 6,000 units in addition to the original
18,000 ceiling. Report the original failed attempt as overhead, and charge
the reused SC-035 and SC-038 first-stage prefixes to each dense path.

Before dispatch, qualify all M<=19 derivative columns and a complete-trial
finite difference at 2.5 GHz on each saved start, comparing 768/1536 nodes.
Require 1e-7 field agreement and 1e-3 Jacobian/FD agreement. Original audits
already cover all frequencies on these paths at the lower resolution.
Afterward, audit every frequency's field refinement and the active-space
Jacobian/FD at 2.5 GHz. Reserve 100 audit units and 38 scoring fields.

This is one numerical refinement, not a band or tolerance sweep. Preserve
any further numerical stop rather than claiming the entire ladder completed.
Compare the dense M ladder with its dense M=9 control. The original C run
continues unchanged and retains its own resolution-qualified interpretation.
