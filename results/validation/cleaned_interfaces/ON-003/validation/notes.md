# ON-003 initial control validation

`initial_tests.log`: 3 passed, 1 failed. The circle near double-layer kernel
was assigned zero at zero separation. Its actual finite trace limit is
r^2*d_R Gnear -> -1/(4pi), independent of k. The 1024/2048 difference was
1/(4*1024)=0.000244140625, diagnosing a missing universal diagonal.
The source now retains -1/(4pi); `corrected_tests.log` passes all four
independent integral, outgoing, Maue, trace/refinement and cutoff checks.
No tolerance was relaxed. This is an implementation correction before the
first grid screen, not a new split/grid or near-repair variant.

The failed universal term would cancel in exterior/interior K differences,
but retaining it is required for individual-medium controls and trace limits.
