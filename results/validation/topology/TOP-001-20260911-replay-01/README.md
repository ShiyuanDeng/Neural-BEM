# Historical replay qualification — 2026-09-11

**Qualification failed for the historical radial event; comparison stopped.**
No perturbed policy arms ran in this bundle.

| Reference | Result |
|---|---|
| [Radial](historical/radial/A/m0-s0/metrics.json) | Pre-event objective matches exactly, but the generated candidate set and winning cut differ. Historical cap 12 was retained. Final geometry remains accurate; that does not pass event-identity qualification |
| [Cartesian](historical/cartesian/A/m0-s0/metrics.json) | Event, final loss and 175.210848-µm sampled Hausdorff reproduce the September 10 audit |

The [amendment](../../../../docs/iterations/topology/iteration_01/04_execution_amendment.md)
records the diagnosis and the subsequent unmodified B0 qualification. Original
manifests, work counts, observations, trials and trajectories remain here.
This directory was produced before the later replay-gauge guard and
`--reference-root` option; its source hash set is the code actually executed.
