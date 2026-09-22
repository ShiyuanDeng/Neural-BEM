# SC-007 — restart and full-Jacobian stage checks

Loads the final SC-005 ellipse endpoint, repeats k=2, and advances to k=2.25
with a fresh explicit budget. Both stages fit without another shape update;
two new forwards bring the cumulative inverse count to 23. All recovery gates
pass. Both fields and full normal Jacobians pass N=128 versus 256 refinement.
The manifest hashes the parent summary, input arrays, and saved endpoint.

Unit controls reject mismatched contrast, changed truth/data fixtures, and
backward frequency restarts. A separate glider control demonstrates why the
new Jacobian check matters: at k=8, fields at N=128/256 agree within 1e-6,
while the normal Jacobian does not. This prevents a converged field from being
used as the sole qualification for derivative accuracy.
