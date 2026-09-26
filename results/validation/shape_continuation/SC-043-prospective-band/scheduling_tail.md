# Resource-only scheduling amendment, before any SC-043 solve

2026-09-26, approximately 17:26 UTC. The still-waiting dispatcher was stopped
before any policy directory existed. No policy, numerical source, data,
quota, tolerance or outcome criterion changes.

Retain the six-PDE-worker ceiling and conservative kite memory weight 5
while any lower-resolution path or SC-044 suffix is outstanding. After all
those jobs finish, permit at most two kite paths together, with no other PDE
workers, and only when MemAvailable is at least 28 GiB before admitting the
second. A third kite never overlaps. This avoids serializing the entire
remaining heavy tail on a 64 GB host, while avoiding the earlier combination
of heavy audits and several other workers that coincided with memory pressure.

The first serial kite audit was observed at approximately 17.9 GiB resident
memory before its final allocations; this is a sample, not a certified peak
bound. The admission threshold provides additional headroom. The separate
SC-046 audit remains serial and must terminate before any policy starts.

This amends the one-kite scheduling statement in SC-046's administrative
plan for the later SC-043 queue only. That frozen plan, sources and manifest
remain preserved. Numerical results are not modified; no wall-clock speed
claim is made from the shared host.
